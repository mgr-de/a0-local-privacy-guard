"""
Local Privacy Guard - Utility Model PII Filter Extension.

Intercepts utility model calls (e.g. chat naming, background jobs) before
they are sent to external LLM APIs and applies the same local PII
detection and anonymization as the chat filter.

The filtering happens ENTIRELY locally - no data is sent to external
services for PII detection. Only the anonymized text is sent to the
LLM provider.

``util_model_call_before`` receives ``call_data`` with string fields
``system`` and ``message`` (not a message list like the chat point).
"""

from helpers.extension import Extension
from helpers import plugins

PLUGIN_NAME = "local_privacy_guard"


def _get_config(agent) -> dict:
    """Load plugin config and flatten for PII filter."""
    cfg = plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}
    pii_cfg = cfg.get("pii_filter", {})
    flat = dict(pii_cfg)
    flat["enabled"] = cfg.get("enabled", True) and pii_cfg.get("enabled", True)
    if "languages" not in flat:
        flat["languages"] = ["de"]
    if "en" not in flat["languages"]:
        flat["languages"] = ["en"] + flat["languages"]
    return flat


def _get_filter(agent, config: dict):
    """Get or create a PIIFilter instance for this agent (shared cache)."""
    from usr.plugins.local_privacy_guard.extensions.python.chat_model_call_before._10_pii_filter import (
        _get_filter as _chat_get_filter,
    )
    return _chat_get_filter(agent, config)


def _safe_log(agent, level: str, message: str):
    try:
        log = getattr(agent, "log", None)
        if log is not None and hasattr(log, level):
            getattr(log, level)(message)
            return
    except Exception:
        pass
    try:
        import logging
        getattr(logging.getLogger("local_privacy_guard"), level)(message)
    except Exception:
        pass


class LocalPrivacyPIIUtilFilterExtension(Extension):
    """Filters PII from utility model calls before they reach external APIs."""

    async def execute(self, call_data: dict = None, **kwargs):
        if call_data is None:
            return
        if not self.agent:
            return

        config = _get_config(self.agent)
        if not config.get("enabled", False):
            return

        filt = _get_filter(self.agent, config)
        log_detections = config.get("log_detections", True)

        # Utility calls pass plain string fields, not message objects.
        for field in ("message", "system"):
            original = call_data.get(field)
            if not isinstance(original, str) or not original.strip():
                continue
            result = filt.filter(original)
            if not result.has_pii:
                continue
            if log_detections:
                pii_summary = ", ".join(d.pii_type for d in result.detections[:5])
                _safe_log(self.agent, "info",
                    f"[Local Privacy Guard] Utility call: detected "
                    f"{result.pii_count} PII items: {pii_summary}"
                )
            action = config.get("action", "redact")
            if action == "redact":
                call_data[field] = result.filtered_text
            elif action == "block":
                _safe_log(self.agent, "warning",
                    "[Local Privacy Guard] BLOCKED utility call content due to PII"
                )
                raise ValueError("Local Privacy Guard blocked this profile's helper-model request because personal details were detected.")
            # log_only: pass through unmodified
