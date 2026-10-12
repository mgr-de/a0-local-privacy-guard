"""Opt-in local integration tests. Never permits an external provider call.

Long conversations use real Agent model calls; the smoke test additionally
uses the native monologue and response tool. Memory is explicitly disabled
for that smoke test, and is not claimed as covered by it.
"""
import argparse, asyncio, json, sys, time
import subprocess
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, '/a0')
sys.path.insert(0, '/a0/usr/plugins/local_privacy_guard/helpers')
sys.path.append('/opt/privacybench-venv/lib/python3.12/site-packages')
from agent import Agent, AgentConfig, UserMessage
from helpers import plugins, litellm_transport, runtime
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from benchmark import Presidio, Local, fixtures, VALUES

class LLMGuardProcess:
    def __init__(self,**kwargs):
        self.process=subprocess.Popen(['/opt/privacybench-venv/bin/python','-u','/tmp/privacy-benchmark/llm_guard_worker.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        self.mapping={}
    def invoke(self,op,text):
        self.process.stdin.write(json.dumps({'op':op,'text':text})+'\n');self.process.stdin.flush()
        while True:
            line=self.process.stdout.readline()
            if not line:raise RuntimeError('LLM Guard worker stopped')
            if line.startswith('PRIVACY_RESULT:'):
                data=json.loads(line.split(':',1)[1])
                if 'error' in data:raise RuntimeError(data['error'])
                self.mapping=data['mapping'];return data['value']
    def mask(self,text,language):
        if language!='en':raise ValueError('Native LLM Guard DE/mixed unsupported')
        return self.invoke('mask',text)
    def display(self,text):return self.invoke('display',text)
    def close(self):
        self.process.terminate();self.process.wait(timeout=10)

async def run(args):
    # This standalone process runs inside the container, like run_ui.py.
    # Without the native runtime flag Agent Zero assumes remote development.
    runtime.args['dockerized'] = True
    root = Path(args.output); root.mkdir(parents=True, exist_ok=True)
    report = {'status':'running','external_calls':0,'model':args.model,
              'conversations':[], 'monologue':{}, 'limitations':[
        'Prototype adapters, not a production Presidio integration',
        'Memory disabled in monologue smoke; memory integration still needs a separate test',
        'No browser UI or server-process restart covered by this script']}
    original = litellm_transport.acompletion
    sent = []
    async def capture(**kw):
        if kw.get('api_base','').rstrip('/') != 'http://host.docker.internal:11434' or not str(kw.get('model','')).startswith(('ollama/','ollama_chat/')):
            raise RuntimeError('External call blocked before transport')
        messages = deepcopy(kw.get('messages', []))
        sent.append({'model':kw['model'],'messages':messages,
            'remaining_full_values':[v for v in VALUES if v in json.dumps(messages,ensure_ascii=False)]})
        return await original(**kw)
    def save():
        (root/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def make_agent(profile):
        # Toggle only newly named benchmark profiles, never Agent 0/global.
        for plugin in ('requesty','local_privacy_guard','_memory'):
            plugins.toggle_plugin(plugin,False,agent_profile=profile)
        a = Agent(0,AgentConfig(profile=profile,mcp_servers='',knowledge_subdirs=[]))
        slot = {'provider':args.provider,'name':args.model,'api_base':'http://host.docker.internal:11434',
            'ctx_length':16384,'kwargs':{'temperature':0,'max_tokens':512,'num_ctx':16384,'timeout':180}}
        a.context.set_data('chat_model_override',{'chat':deepcopy(slot),'utility':deepcopy(slot),'vision':{}})
        return a
    with patch.object(litellm_transport,'acompletion',new=capture):
        if args.monologue:
            a=make_agent('privacy-bench-e2e-smoke')
            adapter=Presidio(root=root/'mapping',profile=a.config.profile,chat=a.context.id)
            source='Anna Weber is married to Ben Fischer. Who is Anna Weber married to? Use the response tool to return only the spouse name. Preserve placeholder tokens exactly.'
            a.hist_add_user_message(UserMessage(message=adapter.mask(source,'en')))
            start=len(sent)
            try:
                answer=await asyncio.wait_for(a.monologue(),timeout=240)
                report['monologue']={'answer':str(answer),'display':adapter.display(str(answer)),
                    'payloads':sent[start:],'completed_native_response_tool':True}
            except Exception as exc:
                report['monologue']={'error':str(exc),'payloads':sent[start:],'completed_native_response_tool':False}
            save(); print('monologue',report['monologue'].get('display',report['monologue'].get('error')),flush=True)
        for variant in args.variants.split(','):
            for language in args.languages.split(','):
                a=make_agent('privacy-bench-long-'+variant+'-'+language)
                factory={'local':Local,'presidio':Presidio,'llm_guard':LLMGuardProcess}[variant]
                adapter=factory(root=root/'mapping',profile=a.config.profile,chat=a.context.id)
                history=[SystemMessage(content='Track this fictional address book through all updates. Answer in one short sentence. Keep placeholders exactly as given. Never invent original names. On summary requests list current marriages, sibling relations, partnerships and outstanding debts, and contacts if known.')]
                conversation={'variant':variant,'language':language,'profile':a.config.profile,'turns':[]}
                report['conversations'].append(conversation)
                for turn,source in enumerate(fixtures(language)[:args.turns]):
                    # Recreate the persistent adapter halfway through; local
                    # variant has no persisted map and intentionally loses it.
                    if turn==20:
                        if hasattr(adapter,'close'):adapter.close()
                        adapter=factory(root=root/'mapping',profile=a.config.profile,chat=a.context.id)
                    masked=adapter.mask(source,language)
                    history.append(HumanMessage(content=masked))
                    start=len(sent); t=time.monotonic()
                    try:
                        answer,reasoning=await asyncio.wait_for(a.call_chat_model(deepcopy(history),background=True,explicit_caching=False),timeout=210)
                        history.append(AIMessage(content=answer))
                        display=adapter.display(answer)
                        row={'turn':turn,'source':source,'masked':masked,'answer':answer,'display':display,
                            'reasoning':reasoning,'roundtrip':adapter.display(masked)==source,
                            'payloads':sent[start:],'seconds':round(time.monotonic()-t,2)}
                        if turn in (9,19,29,39): row['relationship_checkpoint']=True
                        if turn==20: row['adapter_recreated']=True
                    except Exception as exc:
                        row={'turn':turn,'error':str(exc),'payloads':sent[start:]}
                    conversation['turns'].append(row); save()
                    print(variant,language,turn,row.get('display',row.get('error')),flush=True)
                    if 'error' in row: break
                # Wrong profile cannot restore any token from this mapping.
                if variant=='presidio':
                    foreign=Presidio(root=root/'mapping',profile=a.config.profile+'-other',chat=a.context.id)
                    probe=' '.join(adapter.mapping) if hasattr(adapter,'mapping') else ''
                    conversation['foreign_profile_does_not_decode']=foreign.display(probe)==probe
                else:
                    conversation['foreign_profile_does_not_decode']=None
                    conversation['scope_test_note']='Native decoder isolation is covered by benchmark.py lifecycle tests, not by a foreign Presidio decoder.'
                if hasattr(adapter,'close'):adapter.close()
                save()
    report['status']='complete'; save()

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--output',required=True)
    p.add_argument('--model',default='gemma3:4b'); p.add_argument('--turns',type=int,default=40)
    p.add_argument('--provider',choices=['ollama','ollama_chat'],default='ollama')
    p.add_argument('--languages',default='de,en,mixed'); p.add_argument('--variants',default='presidio,local')
    p.add_argument('--monologue',action='store_true'); asyncio.run(run(p.parse_args()))
