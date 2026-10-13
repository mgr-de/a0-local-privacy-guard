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
        try:
            owner,config=owner_and_config(context.agent0) if context and context.agent0 else (None,None)
        except ValueError:
            return {'ok':True,'texts':texts,'media':False,'route':None,
                'protection':{'blocked':True,'owner_profile':context.agent0.config.profile if context and context.agent0 else '',
                    'inherited':False,'text_filter':'blocked','secret_guard':True,
                    'mode_label':'Chat gesperrt · neuen geschützten Chat beginnen',
                    'local_embeddings_configured':False,'last_route':None}}
        if config is None:
            return {"ok":True,"texts":texts,"media":False,"route":None}
        masking=config.get('pii_filter',{}).get('enabled',True)
        mapping = mapping_for(context.agent0) if masking else None
        return {"ok":True,"texts":mapping.restore_many(texts, recover_types=True) if mapping else texts,
            "media":bool(context.get_data("local_privacy_media")), "route":context.get_data("local_privacy_media_route"),
            "protection":{"last_route":context.get_data('local_privacy_route'),
                "owner_profile":owner.config.profile,"inherited":owner.context is not context,
                "text_filter":config.get('pii_filter',{}).get('action','redact') if masking else 'off',
                "secret_guard":True,"mode_label":'PII-Maskierung aktiv · Secret-Prüfung aktiv' if masking else 'PII-Maskierung aus · Secret-Prüfung aktiv',
                "local_embeddings_configured":bool(config.get('local_embedding',{}).get('enabled') and config.get('local_embedding',{}).get('auto_configure'))}}
