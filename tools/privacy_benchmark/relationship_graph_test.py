"""40 real local turns with a deterministic relationship-state oracle.

The model must return JSON. A match tests the stated graph fields, not general
semantic correctness or complete PII detection. Every final payload is captured.
"""
import asyncio,json,sys,time
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/a0');sys.path.append('/opt/privacybench-venv/lib/python3.12/site-packages')
from agent import Agent,AgentConfig
from helpers import plugins,runtime,litellm_transport
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage
from benchmark import Presidio,fixtures,PEOPLE,VALUES

def expected(turn):
    return {'married':1<=turn<10,'partners':10<=turn<30,
            'debt_eur':125 if 20<=turn<30 else 0,'siblings':turn>=1}

def decode(answer):
    answer=answer.strip()
    if answer.startswith('```'):
        answer=answer.split('\n',1)[1].rsplit('```',1)[0].strip()
    value=json.loads(answer)
    if not isinstance(value,dict) or set(value)!=set(expected(0)):raise ValueError('Wrong schema')
    if any(type(value[k]) is not bool for k in ('married','partners','siblings')):raise ValueError('Boolean required')
    if type(value['debt_eur']) not in (int,float):raise ValueError('Numeric debt required')
    return value

async def run():
    runtime.args['dockerized']=True
    root=Path('/tmp/privacy-benchmark/graph-live');root.mkdir(parents=True,exist_ok=True)
    profile='privacy_bench_graph'
    for name in ('requesty','local_privacy_guard','_memory'):plugins.toggle_plugin(name,False,agent_profile=profile)
    a=Agent(0,AgentConfig(profile=profile,mcp_servers='',knowledge_subdirs=[]))
    slot={'provider':'ollama_chat','name':'gemma3:4b','api_base':'http://host.docker.internal:11434',
          'ctx_length':16384,'kwargs':{'temperature':0,'max_tokens':160,'num_ctx':16384,'timeout':180}}
    a.context.set_data('chat_model_override',{'chat':deepcopy(slot),'utility':deepcopy(slot),'vision':{}})
    adapter=Presidio(root=root/'mapping',profile=profile,chat=a.context.id)
    sources=fixtures('mixed');initial=adapter.mask(sources[0],'mixed')
    roles={role:next(k for k,v in adapter.mapping.items() if v==person[0]) for role,person in zip('ABCD',PEOPLE)}
    history=[SystemMessage(content='Track the four fictional people: '+json.dumps(roles)+'. After every user message return ONLY JSON with exactly these fields: married (A and B are currently married, boolean), partners (B and C are currently business partners, boolean), debt_eur (the current unpaid debt of D to A, number), siblings (C and D are siblings, boolean). Initially all booleans false and debt 0. An update overrides older facts. Reminders do not create relationships. Payment in full clears the debt. Never infer new debts. No prose, no contact details. Keep state across messages.')]
    result={'status':'running','scope':'Deterministic four-field graph through 40 real local model calls','roles':roles,'turns':[]}
    original=litellm_transport.acompletion;payloads=[]
    async def capture(**kw):
        if kw.get('api_base','').rstrip('/')!='http://host.docker.internal:11434' or not str(kw.get('model','')).startswith('ollama_chat/'):
            raise RuntimeError('External model blocked')
        messages=deepcopy(kw.get('messages',[]));payloads.append(messages)
        return await original(**kw)
    with patch.object(litellm_transport,'acompletion',new=capture):
        for turn,source in enumerate(sources):
            history.append(HumanMessage(content=initial if turn==0 else adapter.mask(source,'mixed')))
            start=len(payloads);started=time.monotonic()
            answer,reasoning=await asyncio.wait_for(a.call_chat_model(deepcopy(history),background=True,explicit_caching=False),timeout=210)
            history.append(AIMessage(content=answer));observed=None;error=None
            try:observed=decode(answer)
            except Exception as exc:error=str(exc)
            row={'turn':turn,'expected':expected(turn),'observed':observed,'answer':answer,
                 'match':observed==expected(turn),'parse_error':error,'reasoning':reasoning,
                 'seconds':round(time.monotonic()-started,2),'payloads':payloads[start:],
                 'remaining_full_values':[v for v in VALUES if v in json.dumps(payloads[start:])]}
            result['turns'].append(row);(root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            print(turn,row['match'],answer,flush=True)
    result['status']='complete';result['exact_graph_matches']=sum(r['match'] for r in result['turns'])
    result['checkpoint_matches']={str(t):result['turns'][t]['match'] for t in (9,19,29,39)}
    (root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':asyncio.run(run())
