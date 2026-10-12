from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers.model_guard import filter_native

class FilterNativePayload(Extension):
    def execute(self, data, **kwargs):
        data['_privacy_method'] = 'unified_turn'
        filter_native(data)
