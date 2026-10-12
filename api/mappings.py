from helpers.api import ApiHandler
from agent import AgentContext
from usr.plugins.local_privacy_guard.helpers.mapping_cleanup import remove_chat

class Mappings(ApiHandler):
    async def process(self,input,request):
        if input.get('confirmation')!='DELETE_CHAT_MAPPINGS':
            return {'ok':False,'error':'Deleting mappings permanently prevents restoring old placeholders. Confirm deletion for this chat.'}
        context=AgentContext.get(str(input.get('context_id') or ''))
        if context is None:return {'ok':False,'error':'Chat not found.'}
        if context.is_running():return {'ok':False,'error':'Wait until this chat stops before deleting its mappings.'}
        with self.thread_lock:return {'ok':True,'removed':remove_chat(context.id)}
