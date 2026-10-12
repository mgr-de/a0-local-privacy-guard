from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers.agent_scope import apply

class LocalProfileConfiguration(Extension):
    def execute(self, data, **kwargs):
        apply(data, self.agent)
