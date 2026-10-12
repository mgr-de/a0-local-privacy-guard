"""Tests for the extension wiring: agent_init dispatch (sync, once per
context), PII filters for chat and utility calls, and helper utilities."""

import asyncio
import inspect
import types
import yaml
import pytest

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


def test_agent_init_never_writes_shared_presets(monkeypatch, tmp_path):
    import usr.plugins.local_privacy_guard.helpers.embedding_config as ec
    p = tmp_path / "presets.yaml"
    p.write_text("shared sentinel", encoding="utf-8")
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)
    monkeypatch.setattr(ec, "configure_local_embedding", lambda *a, **k: (_ for _ in ()).throw(AssertionError("global mutation")))
    _install_config(monkeypatch, _config(verify=False))
    init_ext.LocalPrivacyGuardInitExtension(agent=FakeAgent()).execute()
    assert p.read_text() == "shared sentinel"

def test_agent_init_disabled_plugin_noop(monkeypatch):
    _install_config(monkeypatch, _config(enabled=False))
    agent=FakeAgent()
    init_ext.LocalPrivacyGuardInitExtension(agent=agent).execute()
    assert agent.log.lines == []

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
    with pytest.raises(ValueError,match="blocked this profile"):
        _run(ext.execute(call_data=call_data))


def test_chat_block_stops_only_protected_agent_call(monkeypatch):
    alpha=FakeAgent();beta=FakeAgent()
    protected={"enabled":True,"pii_filter":{"enabled":True,"action":"block","use_regex":True,"use_ner":False,"languages":["en"]}}
    monkeypatch.setattr("helpers.plugins.get_plugin_config",lambda name,agent=None:protected if agent is alpha else {"enabled":False})
    class HumanMessage:
        def __init__(self):self.content="synthetic@example.com"
    with pytest.raises(ValueError,match="blocked this profile"):
        _run(chat_ext.LocalPrivacyPIIFilterExtension(agent=alpha).execute(call_data={"messages":[HumanMessage()]}))
    other=HumanMessage()
    _run(chat_ext.LocalPrivacyPIIFilterExtension(agent=beta).execute(call_data={"messages":[other]}))
    assert other.content=="synthetic@example.com"


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
    f2 = util_ext._get_filter(agent, chat_ext._get_config(agent))
    assert len(chat_ext._filter_cache) == 1
