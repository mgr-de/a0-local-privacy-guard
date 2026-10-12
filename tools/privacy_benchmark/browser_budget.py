"""Test-only gate AFTER Requesty and Local guards, BEFORE native transport."""
import json,sys
from copy import deepcopy
sys.path.insert(0,'/tmp/privacy-benchmark')
from cost_guard import CostGuard
from helpers.extension import Extension
from langchain_core.messages import SystemMessage,HumanMessage
from usr.plugins.requesty.helpers import scope,catalog
from usr.plugins.requesty.helpers.runtime_guard import settings

class BrowserTestBudget(Extension):
    def execute(self,data,**unused):
        wrapper=data['args'][0]
        owner=getattr(wrapper,'_requesty_scope',None)
        if owner!=('', 'privacy_standard_requesty'):return
        if str(getattr(wrapper.a0_model_conf,'provider','')) in {'ollama','ollama_chat'}:
            # Local development continuation is free; runtime_guard already
            # validates its effective local endpoint before this test hook.
            return
        kwargs=data.get('kwargs',{});policy=settings(owner)
        if kwargs.get('api_base')!=policy.endpoint:raise ValueError('Test route is not approved')
        messages=deepcopy(kwargs.get('messages') or [])
        if kwargs.get('system_message'):messages.insert(0,SystemMessage(content=kwargs['system_message']))
        if kwargs.get('user_message'):messages.append(HumanMessage(content=kwargs['user_message']))
        payload=wrapper._convert_messages(messages)
        name=wrapper.model_name.removeprefix('openai/')
        metadata=catalog.fetch(policy.endpoint,scope.key(owner)).get(name)
        policy.check(metadata)
        prices=metadata.get('pricing') or [metadata]
        inp=max(float(p['input_price']) for p in prices);out=max(float(p['output_price']) for p in prices)
        cap=int(kwargs.get('max_tokens',1024))
        budget=CostGuard('/tmp/privacy-benchmark/requesty-live/budget.sqlite')
        ticket=budget.reserve(len(json.dumps(payload,ensure_ascii=False).encode())+4096,cap,inp*4,out*4)
        # Retry limits are checked again here. One reservation per real attempt.
        kwargs.update(a0_retry_attempts=0,num_retries=0,max_tokens=cap)
        data['kwargs']=kwargs
        from pathlib import Path
        path=Path('/tmp/privacy-benchmark/browser-standard-requesty.jsonl')
        with path.open('a') as stream:
            stream.write(json.dumps({'model':name,'reservation_id':ticket,'messages':payload},ensure_ascii=False)+'\n')
