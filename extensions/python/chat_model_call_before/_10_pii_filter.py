"""
Local Privacy Guard - PII Filter Extension.

Intercepts all messages before they are sent to the LLM API
and applies local PII detection and anonymization.

The filtering happens ENTIRELY locally - no data is sent to external
services for PII detection. Only the anonymized text is sent to the
LLM provider.
"""

from helpers.extension import Extension
from helpers import plugins

PLUGIN_NAME = "local_privacy_guard"

# Cache filter instances per agent context
_filter_cache: dict = {}


def _get_config(agent) -> dict:
    """Load plugin configuration for the agent."""
    cfg = plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}
    # Flatten nested config: pii_filter sub-dict becomes the filter config
    pii_cfg = cfg.get("pii_filter", {})
    flat = dict(pii_cfg)
    flat["enabled"] = cfg.get("enabled", True) and pii_cfg.get("enabled", True)
    return flat


def _get_filter(agent, config: dict):
    """Get or create a PIIFilter instance for this agent."""
    ctx_id = getattr(getattr(agent, "context", None), "id", "default") if agent else "default"
    cache_key = f"{ctx_id}_{id(agent)}"
    if cache_key not in _filter_cache:
        from usr.plugins.local_privacy_guard.helpers.pii_detector import create_filter
        _filter_cache[cache_key] = create_filter(config)
    return _filter_cache[cache_key]


def _get_message_role(message) -> str:
    """Get the role/type of a langchain message."""
    msg_type = type(message).__name__.lower()
    if "system" in msg_type:
        return "system"
    elif "human" in msg_type:
        return "user"
    elif "ai" in msg_type:
        return "ai"
    elif "tool" in msg_type:
        return "tool"
    return msg_type


def _get_message_content(message) -> str:
    """Extract text content from a message."""
    content = getattr(message, "content", "")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    parts.append("[IMAGE]")
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content) if content else ""


def _set_message_content(message, new_content: str):
    """Set text content on a message (preserving type)."""
    if isinstance(getattr(message, "content", None), list):
        content_list = message.content
        for item in content_list:
            if isinstance(item, dict) and item.get("type") == "text":
                item["text"] = new_content
                return
        content_list.insert(0, {"type": "text", "text": new_content})
    else:
        message.content = new_content


class LocalPrivacyPIIFilterExtension(Extension):
    """Filters PII from messages before they are sent to the LLM API."""

    async def execute(self, call_data: dict = None, **kwargs):
        if call_data is None:
            return
        if not self.agent:
            return

        config = _get_config(self.agent)

        if not config.get("enabled", False):
            return

        skip_roles = config.get("skip_roles", ["system"])

        # call_data contains 'messages' (list of langchain messages)
        messages = call_data.get("messages")
        if not messages:
            return

        filt = _get_filter(self.agent, config)
        log_detections = config.get("log_detections", True)
        action = config.get("action", "redact")

        total_detections = 0

        for message in messages:
            role = _get_message_role(message)
            if role in skip_roles:
                continue

            original = _get_message_content(message)
            if not original.strip():
                continue

            result = filt.filter(original)

            if not result.has_pii:
                continue

            total_detections += result.pii_count

            if log_detections:
                pii_summary = ", ".join(
                    f"{d.pii_type}({d.source})" for d in result.detections[:5]
                )
                if len(result.detections) > 5:
                    pii_summary += f", ... +{len(result.detections) - 5} more"
                self.agent.log.info(
                    f"[Local Privacy Guard] Detected {result.pii_count} PII items: {pii_summary}"
                )

            if action == "redact":
                _set_message_content(message, result.filtered_text)
            elif action == "block":
                self.agent.log.warning(
                    f"[Local Privacy Guard] BLOCKED message with {result.pii_count} PII items"
                )
                _set_message_content(message, "[Message blocked by Local Privacy Guard due to PII detection]")
            # log_only: do nothing, message passes through unmodified

        if total_detections > 0:
            self.agent.log.info(
                f"[Local Privacy Guard] Filtered {total_detections} PII items total"
            )
