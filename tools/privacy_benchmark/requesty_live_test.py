"""Opt-in real configured-profile smoke. No settings or credentials are written.
Preflight budget and PII checks cover every transport call and retry.
"""
import asyncio,json,sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/a0'); sys.path.append('/opt/privacybench-venv/lib/python3.12/site-packages')
from agent import Agent,AgentConfig
from helpers import litellm_transport,runtime
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage
from usr.plugins.requesty.helpers import scope,catalog
from usr.plugins.requesty.helpers.runtime_guard import settings
from benchmark import Presidio,VALUES,fixtures
from cost_guard import CostGuard

async def run():
    runtime.args['dockerized']=True
    root=Path('/tmp/privacy-benchmark/requesty-live'); root.mkdir(parents=True,exist_ok=True)
    owner=('', 'agent0'); policy=settings(owner)
    available=catalog.fetch(policy.endpoint,scope.key(owner),refresh=True)
    setup=scope.read(owner,'setup.json')
    a=Agent(0,AgentConfig(profile='agent0',mcp_servers='',knowledge_subdirs=[]))
    adapter=Presidio(root=root/'mapping',profile='agent0',chat=a.context.id)
    ledger=CostGuard(str(root/'budget.sqlite'))
    result={'status':'running','profile_settings_written':False,'calls':[], 'turns':[],
        'budget_limit_eur':5,'price_safety_multiplier':4,
        'scope':'Real Agent chat-model hook path, existing Requesty profile; not UI/monologue'}
    original=litellm_transport.acompletion
    async def capture(**kw):
        name=str(kw.get('model','')).removeprefix('openai/')
        if name not in (setup['models']['chat']['name'],setup['models']['utility']['name']) or kw.get('api_base','').rstrip('/')!=policy.endpoint:
            raise RuntimeError('Unexpected model or route blocked')
        messages=deepcopy(kw.get('messages',[])); encoded=json.dumps(messages,ensure_ascii=False)
        leaked=[v for v in VALUES if v in encoded]
        if leaked: raise RuntimeError('Unmasked synthetic PII blocked before external transport')
        metadata=available[name]; tiers=metadata.get('pricing') or [metadata]
        inp=max(float(t['input_price']) for t in tiers); out=max(float(t['output_price']) for t in tiers)
        # Bound all output tokens, including reasoning, before the provider.
        kw['max_tokens']=512; kw.pop('max_completion_tokens',None); kw['num_retries']=0
        # UTF-8 bytes conservatively bound tokens for these text-only messages.
        bound=len(encoded.encode('utf-8'))+4096
        ticket=ledger.reserve(bound,512,inp*4,out*4)
        result['calls'].append({'model':name,'messages':messages,'reservation_ticket':ticket,
            'input_byte_bound':bound,'max_output_tokens':512,'remaining_full_values':leaked})
        (root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        try: return await original(**kw)
        finally: ledger.settle(ticket) # Charge conservative full reservation, even on failure.
    history=[SystemMessage(content='Track fictional people and changes. Preserve all placeholder tokens exactly. Answer briefly.')]
    with patch.object(litellm_transport,'acompletion',new=capture):
        cases=['Reply with exactly READY.']+[fixtures('en')[i] for i in (0,1,10,20,29,30,39)]
        for n,text in enumerate(cases):
            history.append(HumanMessage(content=adapter.mask(text,'en')))
            try:
                answer,reasoning=await asyncio.wait_for(a.call_chat_model(deepcopy(history),background=True,explicit_caching=False),timeout=150)
                history.append(AIMessage(content=answer))
                result['turns'].append({'turn':n,'answer':answer,'display':adapter.display(answer),'reasoning':reasoning})
                print(n,adapter.display(answer),flush=True)
            except Exception as exc:
                result['turns'].append({'turn':n,'error':str(exc)}); break
            (root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    result['reserved_cost_eur']=sum(float(c or r) for r,c in ledger.db.execute('SELECT reserved,charged FROM calls'))
    result['status']='complete'; (root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
asyncio.run(run())
