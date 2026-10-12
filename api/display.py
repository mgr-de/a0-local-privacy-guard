"""Authenticated local display-only decoding; never alter canonical logs."""
from helpers.api import ApiHandler
from agent import AgentContext
from usr.plugins.local_privacy_guard.helpers.model_guard import mapping_for, owner_and_config

class Display(ApiHandler):
    async def process(self, input, request):
        context = AgentContext.get(str(input.get("context_id") or ""))
        texts = input.get("texts", [])
        if not isinstance(texts,list) or len(texts)>500 or any(not isinstance(t,str) for t in texts) or sum(map(len,texts))>500000:
            return {"ok":False,"error":"Display request is too large or invalid."}
        owner,config=owner_and_config(context.agent0) if context and context.agent0 else (None,None)
        if config is None:
            return {"ok":True,"texts":texts,"media":False,"route":None}
        mapping = mapping_for(context.agent0)
        return {"ok":True,"texts":[mapping.restore(t) for t in texts],
            "media":bool(context.get_data("local_privacy_media")), "route":context.get_data("local_privacy_media_route"),
            "protection":{"last_route":context.get_data('local_privacy_route'),
                "owner_profile":owner.config.profile,"inherited":owner.context is not context,
                "text_filter":config.get('pii_filter',{}).get('action','redact') if config.get('pii_filter',{}).get('enabled',True) else 'off',
                "local_embeddings_configured":bool(config.get('local_embedding',{}).get('enabled') and config.get('local_embedding',{}).get('auto_configure'))}}
