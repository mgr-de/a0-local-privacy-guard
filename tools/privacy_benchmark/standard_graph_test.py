"""Production wrapper, deterministic relationship oracle, local dev model only."""
import argparse,asyncio,json,sys
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
sys.path.insert(0,'/a0')
from agent import Agent,AgentConfig
from helpers import plugins,runtime,litellm_transport
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage
from benchmark import fixtures,PEOPLE,VALUES
from relationship_graph_test import expected,decode
from usr.plugins.local_privacy_guard.helpers.model_guard import mapping_for,PayloadFilter

async def run(args):
    runtime.args['dockerized']=True
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    profile='privacy_standard_graph_'+str(args.turns)
    plugins.toggle_plugin('local_privacy_guard',True,agent_profile=profile)
    for name in ('requesty','_memory'):plugins.toggle_plugin(name,False,agent_profile=profile)
    cfg=plugins.get_plugin_config('local_privacy_guard',agent_profile=profile)
    cfg['verification']['enabled']=False;cfg['local_embedding']['enabled']=False
    cfg['pii_filter'].update(use_regex=True,use_ner=True,languages=['en','de'],action='redact')
    plugins.save_plugin_config('local_privacy_guard','',profile,cfg)
    agent=Agent(0,AgentConfig(profile=profile,mcp_servers='',knowledge_subdirs=[]))
    slot={'provider':'ollama_chat','name':'gemma3:4b','ctx_length':32768,
          'kwargs':{'api_base':'http://host.docker.internal:11434','num_ctx':32768,'temperature':0,'max_tokens':256}}
    agent.context.set_data('chat_model_override',{'chat':slot,'utility':slot,'vision':{}})
    sources=fixtures('mixed');pipeline=PayloadFilter(agent,cfg,False);pipeline.text(sources[0])
    roles={role:next(token for token,kind,value in pipeline.mapping.entries() if value==person[0]) for role,person in zip('ABCD',PEOPLE)}
    history=[SystemMessage(content='Track four fictional people: '+json.dumps(roles)+'. Return ONLY JSON with married (A and B currently married, boolean), partners (B and C business partners, boolean), debt_eur (unpaid debt of D to A, number), siblings (C and D siblings, boolean). Initially false and 0. Updates replace old facts. Reminders do not change relationships. Payment clears the debt. Preserve identities. No extra fields. Your entire answer must use this exact shape, with updated values: '+json.dumps(expected(0))) ]
    result={'status':'running','scope':'Installed production wrapper, mixed-language relationship and debt oracle','turns':[]}
    captured=[];original=litellm_transport.acompletion
    async def capture(**kwargs):
        if kwargs.get('api_base','').rstrip('/')!='http://host.docker.internal:11434' or not kwargs['model'].startswith('ollama_chat/'):
            raise ValueError('External route refused by local integration test')
        captured.append(deepcopy(kwargs.get('messages',[])));return await original(**kwargs)
    with patch.object(litellm_transport,'acompletion',new=capture):
        for turn in range(args.turns):
            source=sources[turn] if turn<40 else sources[2+(turn%7)]
            begin=len(captured);history.append(HumanMessage(content=source))
            answer,reasoning=await agent.call_chat_model(messages=deepcopy(history),background=True,explicit_caching=False)
            history[-1]=HumanMessage(content=pipeline.text(source));history.append(AIMessage(content=answer))
            observed=None;error=None
            try:observed=decode(answer)
            except Exception as exc:error=str(exc)
            row={'turn':turn,'expected':expected(min(turn,39)),'observed':observed,'answer':answer,'reasoning':reasoning,
                 'match':observed==expected(min(turn,39)),'parse_error':error,'payloads':captured[begin:],
                 'remaining_full_values':[value for value in VALUES if value in json.dumps(captured[begin:])]}
            result['turns'].append(row);(root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            print(turn,row['match'],flush=True)
    result['status']='complete';result['exact_graph_matches']=sum(row['match'] for row in result['turns'])
    (root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--turns',type=int,default=40);parser.add_argument('--output',required=True)
    asyncio.run(run(parser.parse_args()))
