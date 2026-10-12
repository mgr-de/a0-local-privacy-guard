"""Installed-plugin live smoke, synthetic text only, existing shared budget ledger."""
import asyncio,json,sys
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
sys.path.insert(0,'/a0');sys.path.insert(0,'/tmp/privacy-benchmark')
from agent import Agent,AgentConfig
from helpers import litellm_transport,runtime,plugins
from langchain_core.messages import HumanMessage,AIMessage
from usr.plugins.requesty.helpers import scope,catalog
from usr.plugins.requesty.helpers.runtime_guard import settings
from usr.plugins.local_privacy_guard.helpers.model_guard import owner_and_config,mapping_for
from usr.plugins.local_privacy_guard.helpers import agent_scope
from benchmark import fixtures,VALUES
from cost_guard import CostGuard

async def run():
    runtime.args['dockerized']=True
    root=Path('/tmp/privacy-benchmark/requesty-live');root.mkdir(exist_ok=True)
    owner=('', 'agent0');policy=settings(owner);setup=scope.read(owner,'setup.json')
    available=catalog.fetch(policy.endpoint,scope.key(owner),refresh=True)
    # Test-process-only local policy overlay; do not alter the user's saved
    # Agent-0 configuration, which does not currently activate the local plugin.
    config={'enabled':True,'pii_filter':{'enabled':True,'use_regex':True,'use_ner':True,'languages':['en','de'],'action':'redact'},
            'local_embedding':{'enabled':False},'verification':{'enabled':False}}
    local_overlay=patch.object(agent_scope,'configuration',return_value=config)
    local_overlay.start()
    enabled_plugins=plugins.get_enabled_plugins
    plugin_overlay=patch.object(plugins,'get_enabled_plugins',side_effect=lambda agent:list(dict.fromkeys([*enabled_plugins(agent),'local_privacy_guard'])))
    plugin_overlay.start()
    agent=Agent(0,AgentConfig(profile='agent0',mcp_servers='',knowledge_subdirs=[]))
    budget=CostGuard(str(root/'budget.sqlite'))
    result={'calls':[],'turns':[],'status':'running','settings_written':False,'temporary_local_policy_overlay':True,
            'wrapper':type(agent.get_chat_model()).__name__}
    original=litellm_transport.acompletion
    async def capture(**kwargs):
        name=str(kwargs.get('model','')).removeprefix('openai/')
        if kwargs.get('api_base','').rstrip('/')!=policy.endpoint or name not in available:
            raise RuntimeError('Unapproved test route')
        payload=deepcopy(kwargs.get('messages',[]))
        leaked=[value for value in VALUES if value in json.dumps(payload,ensure_ascii=False)]
        if leaked:
            result['blocked_payload']={'known_synthetic_values':leaked,'messages':payload}
            raise RuntimeError('Synthetic PII stopped before external transport')
        metadata=available[name];prices=metadata.get('pricing') or [metadata]
        inp=max(float(p['input_price']) for p in prices);out=max(float(p['output_price']) for p in prices)
        kwargs['max_tokens']=256;kwargs['num_retries']=0
        ticket=budget.reserve(len(json.dumps(payload,ensure_ascii=False).encode())+4096,kwargs['max_tokens'],inp*4,out*4)
        result['calls'].append({'model':name,'messages':payload,'reservation_id':ticket})
        return await original(**kwargs)
    history=[]
    with patch.object(litellm_transport,'acompletion',side_effect=capture):
        for text in (fixtures('en')[0],fixtures('en')[1],fixtures('en')[39]):
            history.append(HumanMessage(content=text))
            try:
                answer,reasoning=await agent.call_chat_model(deepcopy(history),background=True,explicit_caching=False)
                history.append(AIMessage(content=answer))
                result['turns'].append({'answer':answer,'display':mapping_for(agent).restore(answer),'reasoning':reasoning})
            except Exception as exc:
                result['turns'].append({'error':str(exc)});break
    result['reserved_cost_eur']=sum(float(charged or reserved) for reserved,charged in budget.db.execute('SELECT reserved,charged FROM calls'))
    result['status']='complete';(root/'standard-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'wrapper':result['wrapper'],'blocked_synthetic_values':result.get('blocked_payload',{}).get('known_synthetic_values'),
        'calls':len(result['calls']),'reserved_cost_eur':result['reserved_cost_eur'],'errors':[r['error'] for r in result['turns'] if 'error' in r]}))
    local_overlay.stop()
    plugin_overlay.stop()

asyncio.run(run())
