from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers.model_guard import mapping_for, owner_and_config

class RestoreLocalArguments(Extension):
    def execute(self, tool_args=None, tool_name="", **kwargs):
        if not self.agent or not tool_args or owner_and_config(self.agent)[1] is None:
            return
        if not owner_and_config(self.agent)[1].get('pii_filter',{}).get('enabled',True):
            return
        if tool_name == "response":
            return  # Canonical response remains masked; browser display restores it.
        mapping = mapping_for(self.agent)
        def restore(value):
            if isinstance(value,str):return mapping.restore(value)
            if isinstance(value,list):return [restore(v) for v in value]
            if isinstance(value,dict):return {k:restore(v) for k,v in value.items()}
            return value
        tool_args.update(restore(tool_args))
