import asyncio
from helpers.api import ApiHandler
from usr.plugins.local_privacy_guard.helpers.ui_diagnostics import example


class Example(ApiHandler):
    async def process(self, input, request):
        try:
            result = await asyncio.to_thread(example, input.get("config"))
            return {"ok": True, **result}
        except ValueError as error:
            return {"ok": False, "error": str(error)}
