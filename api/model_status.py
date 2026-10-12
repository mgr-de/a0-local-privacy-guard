"""Read-only native gate with profile-owned Requesty delegation."""
from helpers.api import ApiHandler
from plugins._model_config.api.model_config_get import ModelConfigGet

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
        return result
