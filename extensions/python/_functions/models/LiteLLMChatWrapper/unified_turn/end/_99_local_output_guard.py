from helpers.extension import Extension
from usr.plugins.local_privacy_guard.helpers.model_guard import filter_native_result

class FilterNativeOutput(Extension):
    async def execute(self, data, **kwargs):
        await filter_native_result(data)
