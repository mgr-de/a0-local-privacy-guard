from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers.model_guard import filter_native

class FilterNativePayload(Extension):
    def execute(self, data, **kwargs):
        filter_native(data)
