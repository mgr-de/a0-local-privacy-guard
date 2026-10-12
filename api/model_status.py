"""Read-only gate compatibility for native local providers without API keys."""
from helpers.api import ApiHandler
from plugins._model_config.api.model_config_get import ModelConfigGet
from urllib.parse import urlparse

class ModelStatus(ApiHandler):
    async def process(self,input,request):
        # Frontend manifests can retain another profile's hooks. Resolve the
        # owning profile on the server rather than depend on plugin hook order.
        from agent import AgentContext
        context=AgentContext.get(str(input.get('context_id') or ''))
        if context and context.agent0:
            try:
                from usr.plugins.requesty.helpers.call_context import owner
                from usr.plugins.requesty.helpers import scope
                from usr.plugins.requesty.api.model_status import ModelStatus as RequestyStatus
            except ImportError:
                pass
            else:
                identity=owner(context.agent0)
                setup=scope.read(identity,'setup.json')
                if setup and setup.get('active') and scope.enabled(identity):
                    return await RequestyStatus(self.app,self.thread_lock).process(input,request)
        result=await ModelConfigGet(self.app,self.thread_lock).process(input,request)
        config=result.get('config',{}).get('chat_model',{})
        base=config.get('api_base') or config.get('kwargs',{}).get('api_base','')
        if config.get('provider') in {'ollama','ollama_chat'} and urlparse(str(base)).scheme in {'http','https'} and urlparse(str(base)).hostname in {
            'localhost','127.0.0.1','::1','host.docker.internal','ollama'
        } and config.get('name'):
            result['model_configured']=True
        return result
