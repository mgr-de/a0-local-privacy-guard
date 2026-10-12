from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers.model_guard import tool_agent

class PrivacyCallOwner(Extension):
    def execute(self, **kwargs):
        tool_agent.set(self.agent)
