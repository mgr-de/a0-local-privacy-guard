"""Tests for the extension wiring: agent_init dispatch (sync, once per
context), PII filters for chat and utility calls, and helper utilities."""

import asyncio
import inspect
import types
import yaml

import usr.plugins.local_privacy_guard.extensions.python.agent_init._10_privacy_init as init_ext
import usr.plugins.local_privacy_guard.extensions.python.chat_model_call_before._10_pii_filter as chat_ext
import usr.plugins.local_privacy_guard.extensions.python.util_model_call_before._10_pii_filter as util_ext
from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter

LOCAL = init_ext.PLUGIN_NAME


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, msg): self.lines.append(("info", msg))
    def warning(self, msg): self.lines.append(("warning", msg))
    def error(self, msg): self.lines.append(("error", msg))


class FakeContext:
    def __init__(self, id="ctx-1"):
        self.id = id


class FakeAgent:
    def __init__(self, id="ctx-1"):
        self.log = FakeLog()
        self.context = FakeContext(id)


def _config(enabled=True, auto=True, verify=True):
    return {
        "enabled": enabled,
        "local_embedding": {"enabled": True, "auto_configure": auto, "model": "sentence-transformers/X"},
        "verification": {"enabled": verify, "check_components": ["embedding", "requesty"]},
    }


def _install_config(monkeypatch, cfg):
    """Patch get_plugin_config on the shared helpers.plugins stub module that
    all three extension modules already imported."""
    monkeypatch.setattr(
        "helpers.plugins.get_plugin_config", lambda name, agent=None: cfg
    )


def test_agent_init_execute_is_sync(monkeypatch):
    """agent_init is dispatched synchronously; a coroutine would crash it."""
    sig = inspect.signature(init_ext.LocalPrivacyGuardInitExtension.execute)
    assert inspect.iscoroutinefunction(init_ext.LocalPrivacyGuardInitExtension.execute) is False


def test_agent_init_runs_once_per_context(monkeypatch, tmp_path):
    p = tmp_path / "presets.yaml"
    p.write_text(yaml.safe_dump([
        {"name": "Default", "embedding": {"provider": "openai", "name": "old"}}
    ]), encoding="utf-8")

    import usr.plugins.local_privacy_guard.helpers.embedding_config as ec
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)
    _install_config(monkeypatch, _config())
    init_ext._initialized_contexts.clear()

    agent = FakeAgent()
    ext = init_ext.LocalPrivacyGuardInitExtension(agent=agent)
    ext.execute()
    first_log = list(agent.log.lines)

    # second agent in the same context: must not re-run the config pass
    agent2 = FakeAgent()
    ext2 = init_ext.LocalPrivacyGuardInitExtension(agent=agent2)
    ext2.execute()
    assert agent2.log.lines == []

    # presets were rewritten to local once
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data[0]["embedding"]["name"] == "sentence-transformers/X"
    assert any("Configured local embedding" in m for _, m in first_log)


def test_agent_init_disabled_plugin_noop(monkeypatch, tmp_path):
    _install_config(monkeypatch, _config(enabled=False))
    init_ext._initialized_contexts.clear()
    agent = FakeAgent()
    ext = init_ext.LocalPrivacyGuardInitExtension(agent=agent)
    ext.execute()
    assert any("disabled" in m for _, m in agent.log.lines)


def test_agent_init_respects_auto_configure_off(monkeypatch, tmp_path):
    p = tmp_path / "presets.yaml"
    p.write_text(yaml.safe_dump([
        {"name": "Default", "embedding": {"provider": "openai", "name": "old"}}
    ]), encoding="utf-8")

    import usr.plugins.local_privacy_guard.helpers.embedding_config as ec
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)
    _install_config(monkeypatch, _config(auto=False))
    init_ext._initialized_contexts.clear()

    ext = init_ext.LocalPrivacyGuardInitExtension(agent=FakeAgent())
    ext.execute()

    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data[0]["embedding"]["name"] == "old"  # untouched


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_chat_filter_redacts_pii(monkeypatch):
    class Msg:
        def __init__(self, content):
            self.content = content

    class HumanMsg(Msg): pass
    class SystemMsg(Msg): pass

    agent = FakeAgent()
    config = {
        "enabled": True,
        "pii_filter": {
            "enabled": True, "action": "redact", "use_regex": True, "use_ner": False,
            "log_detections": True, "languages": ["en"], "skip_roles": ["system"],
        },
    }
    _install_config(monkeypatch, config)
    chat_ext._filter_cache.clear()

    msgs = [
        SystemMsg("You are a helpful assistant. mail@example.com"),
        HumanMsg("Contact me at john.doe@example.com please"),
    ]
    ext = chat_ext.LocalPrivacyPIIFilterExtension(agent=agent)
    _run(ext.execute(call_data={"messages": msgs}))

    assert "john.doe@example.com" not in msgs[1].content
    assert "<EMAIL>" in msgs[1].content
    assert "mail@example.com" in msgs[0].content  # system role skipped


def test_util_filter_redacts_strings(monkeypatch):
    agent = FakeAgent()
    config = {
        "enabled": True,
        "pii_filter": {
            "enabled": True, "action": "redact", "use_regex": True, "use_ner": False,
            "log_detections": True, "languages": ["en"],
        },
    }
    _install_config(monkeypatch, config)
    chat_ext._filter_cache.clear()

    call_data = {"system": "Summarize the chat", "message": "My IBAN is DE02120300000000202051"}
    ext = util_ext.LocalPrivacyPIIUtilFilterExtension(agent=agent)
    _run(ext.execute(call_data=call_data))

    assert "DE02120300000000202051" not in call_data["message"]
    assert "<IBAN>" in call_data["message"]
    assert call_data["system"] == "Summarize the chat"


def test_util_filter_block_mode(monkeypatch):
    agent = FakeAgent()
    config = {
        "enabled": True,
        "pii_filter": {
            "enabled": True, "action": "block", "use_regex": True, "use_ner": False,
            "log_detections": True, "languages": ["en"],
        },
    }
    _install_config(monkeypatch, config)
    chat_ext._filter_cache.clear()

    call_data = {"message": "Email me at a@b.com"}
    ext = util_ext.LocalPrivacyPIIUtilFilterExtension(agent=agent)
    _run(ext.execute(call_data=call_data))
    assert "Blocked" in call_data["message"]


def test_filters_share_cache(monkeypatch):
    """Chat and utility filters must share one filter cache per agent."""
    agent = FakeAgent()
    _install_config(monkeypatch, {
        "enabled": True,
        "pii_filter": {"enabled": True, "action": "redact", "use_regex": True, "use_ner": False, "languages": ["en"]},
    })
    chat_ext._filter_cache.clear()

    class Msg:
        def __init__(self, c): self.content = c

    f1 = _run(chat_ext.LocalPrivacyPIIFilterExtension(agent=agent).execute(call_data={"messages": [Msg("hi there x@y.com")]}))
    f2 = util_ext._get_filter(agent, {})
    assert len(chat_ext._filter_cache) == 1
