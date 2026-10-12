"""Report this profile's configuration without changing any shared presets."""
from helpers.extension import Extension
from helpers import plugins
from usr.plugins.local_privacy_guard.extensions.python.chat_model_call_before._10_pii_filter import _safe_log

PLUGIN_NAME = "local_privacy_guard"

class LocalPrivacyGuardInitExtension(Extension):
    def execute(self, **kwargs):
        if not self.agent:
            return
        config = plugins.get_plugin_config(PLUGIN_NAME, agent=self.agent) or {}
        if not config.get("enabled", False):
            return
        _safe_log(self.agent, "info", "[Local Privacy Guard] Profile privacy settings loaded; shared presets are unchanged.")
        if config.get("verification", {}).get("enabled", True):
            from usr.plugins.local_privacy_guard.helpers.privacy_verifier import verify_all
            components = config.get("verification", {}).get("check_components") or ["pii_filter", "embedding", "memory", "requesty"]
            if not config.get("local_embedding", {}).get("verify_local", True):
                components = [component for component in components if component != "embedding"]
            report = verify_all(config, components, agent=self.agent)
            for component in report["results"]:
                for issue in component.get("issues", []):
                    _safe_log(self.agent, "warning", "[Local Privacy Guard] " + issue)
