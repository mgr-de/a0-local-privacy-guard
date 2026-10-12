from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers.model_guard import bind

class BindPrivacyModel(Extension):
    def execute(self, data, **kwargs):
        bind(data, self.agent)
