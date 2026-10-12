"""Test-profile only: capture supported calls after the privacy filter.
Reject non-local wrappers before any LLM call. Never serializes credentials.
"""
import json
from pathlib import Path
from helpers.extension import Extension

class BrowserTestCapture(Extension):
    async def execute(self,call_data=None,**kwargs):
        if not self.agent or self.agent.config.profile!='privacy_bench_browser' or not call_data:
            return
        model=call_data.get('model')
        name=str(getattr(model,'model_name',''))
        options=getattr(model,'kwargs',{})
        if not name.startswith(('ollama/','ollama_chat/')) or options.get('api_base','').rstrip('/')!='http://host.docker.internal:11434':
            raise RuntimeError('Browser benchmark permits only local Ollama calls')
        messages=call_data.get('messages')
        record={'context':self.agent.context.id,'profile':self.agent.config.profile,'model':name,
            'messages':[{'type':m.type,'content':m.content} for m in messages] if messages is not None else None,
            'system':call_data.get('system'),'message':call_data.get('message')}
        root=Path('/tmp/privacy-benchmark/browser-live');root.mkdir(parents=True,exist_ok=True)
        with (root/'calls.jsonl').open('a',encoding='utf-8') as out:
            out.write(json.dumps(record,ensure_ascii=False)+'\n')
