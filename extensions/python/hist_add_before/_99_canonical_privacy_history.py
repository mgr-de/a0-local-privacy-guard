from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers import model_guard

class CanonicalPrivacyHistory(Extension):
    def execute(self,content_data,**kwargs):
        owner,config=model_guard.owner_and_config(self.agent)
        if config is None:return
        # Browser logs keep local user input; model history receives tokens.
        # Required detector availability is checked again before external calls.
        pipeline=model_guard.PayloadFilter(owner,config,False)
        content_data['content']=pipeline.value(content_data['content'])
        pipeline.log_summary('Model history')
