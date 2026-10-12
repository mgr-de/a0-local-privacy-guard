"""Real isolated FAISS memory, persisted chat, utility and profile tests.
Run prepare and resume in separate Python processes.
"""
import argparse,asyncio,hashlib,json,sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/a0')
from agent import Agent,AgentConfig,UserMessage
from helpers import runtime,plugins,persist_chat,litellm_transport
from plugins._memory.helpers.memory import Memory,get_agent_memory_subdir
from plugins._model_config.helpers import model_config as mc
runtime.args['dockerized']=True
ROOT=Path('/tmp/privacy-benchmark/memory-live'); ROOT.mkdir(parents=True,exist_ok=True)
MARKER='PRIVACY_BENCH_MEMORY_20261011_ABCD'
SOURCE=MARKER+' Anna Weber is married to Ben Fischer; anna.weber@example.com; +49 30 55501001; DE10500105179000000000.'
def fingerprints():
    paths=[Path('/a0/usr/agents/agent0/plugins/requesty/setup.json'),Path('/a0/usr/agents/agent0/plugins/requesty/config.json')]
    paths+=list(Path('/a0/usr').glob('**/model_presets*.json'))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
def agent(profile):
    plugins.toggle_plugin('requesty',False,agent_profile=profile)
    plugins.toggle_plugin('local_privacy_guard',True,agent_profile=profile)
    c=plugins.get_plugin_config('local_privacy_guard',agent_profile=profile)
    c['verification']['enabled']=False
    plugins.save_plugin_config('local_privacy_guard','',profile,c)
    a=Agent(0,AgentConfig(profile=profile,mcp_servers='',knowledge_subdirs=[]))
    slot={'provider':'ollama','name':'gemma3:4b','api_base':'http://host.docker.internal:11434',
          'ctx_length':8192,'kwargs':{'temperature':0,'max_tokens':256,'num_ctx':8192,'timeout':120}}
    a.context.set_data('chat_model_override',{'chat':deepcopy(slot),'utility':deepcopy(slot),'vision':{}})
    return a
async def run(phase):
    before=fingerprints(); a=agent('privacy_bench_memory_a'); b=agent('privacy_bench_memory_b')
    ma=await Memory.get(a); mb=await Memory.get(b)
    result={'phase':phase,'memory_a':get_agent_memory_subdir(a),'memory_b':get_agent_memory_subdir(b),
            'embedding_a':mc.get_embedding_model_config(a),'embedding_b':mc.get_embedding_model_config(b)}
    if phase=='prepare':
        ids=await ma.insert_text(SOURCE,metadata={'area':'main'})
        a.hist_add_user_message(UserMessage(message='Keep this fictional relationship: '+SOURCE))
        a.context.name='Privacy memory restart test';persist_chat.save_tmp_chat(a.context)
        (ROOT/'state.json').write_text(json.dumps({'context':a.context.id,'fingerprints':before}))
        result['inserted_ids']=ids
    else:
        state=json.loads((ROOT/'state.json').read_text())
        data=json.loads(Path('/a0/usr/chats',state['context'],'chat.json').read_text())
        restored=persist_chat._deserialize_context(data)
        result['restored_profile']=restored.agent0.config.profile
        result['restored_override']=restored.get_data('chat_model_override')
        result['chat_history_restored']=MARKER in str(restored.agent0.history.serialize())
        result['previous_user_settings_unchanged']=fingerprints()==state['fingerprints']
        recalled=await ma.search_similarity_threshold(query=MARKER,limit=5,threshold=0)
        result['memory_search_recovered_marker']=any(MARKER in d.page_content for d in recalled)
        original=litellm_transport.acompletion; payloads=[]
        async def capture(**kw):
            if kw.get('api_base','').rstrip('/')!='http://host.docker.internal:11434' or not str(kw.get('model','')).startswith(('ollama/','ollama_chat/')):
                raise RuntimeError('External utility call refused')
            payloads.append(deepcopy(kw.get('messages',[])))
            return await original(**kw)
        with patch.object(litellm_transport,'acompletion',new=capture):
            response=await a.call_utility_model(system='Summarize this fictional memory in one sentence.',message=SOURCE,background=True)
        result['utility_response']=response;result['utility_payloads']=payloads
    result['a_contains_marker']=any(MARKER in d.page_content for d in ma.db.get_all_docs().values())
    result['b_contains_marker']=any(MARKER in d.page_content for d in mb.db.get_all_docs().values())
    result['distinct_storage']=result['memory_a']!=result['memory_b']
    result['user_settings_unchanged']=before==fingerprints()
    (ROOT/(phase+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    print(json.dumps(result,ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','resume']);args=p.parse_args();asyncio.run(run(args.phase))
