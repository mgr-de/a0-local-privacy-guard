"""Two live profiles; shared presets and existing memory folders stay unchanged."""
import json
from copy import deepcopy
from pathlib import Path
import pytest

def test_real_framework_profile_embedding_and_memory_isolation(monkeypatch,tmp_path):
    pytest.importorskip("helpers.files")
    # Requires the actual Agent Zero runtime (run with helpers.extension preimported).
    from agent import Agent,AgentConfig
    from helpers import plugins
    from plugins._model_config.helpers import model_config as mc
    from plugins._memory.helpers import memory
    from usr.plugins.local_privacy_guard.helpers import agent_scope
    def selected(project,profile):return tmp_path/project/profile/"config.json"
    monkeypatch.setattr(agent_scope,"selected_path",selected)
    # Dedicated names avoid a saved Requesty setup in a user's agent0 profile
    # suspending the override that this Local Privacy Guard test must exercise.
    alpha_profile = "privacy_test_alpha"
    beta_profile = "privacy_test_beta"
    protected=selected("",alpha_profile);protected.parent.mkdir(parents=True)
    protected.write_text(json.dumps({"enabled":True,"local_embedding":{"enabled":True,"auto_configure":True,
        "model":"sentence-transformers/synthetic-local"},"pii_filter":{"enabled":True},"verification":{"enabled":False}}))
    shared_path=Path(mc._get_presets_path());before=shared_path.read_bytes() if shared_path.exists() else None
    alpha=Agent(0,AgentConfig(profile=alpha_profile,mcp_servers=""))
    beta=Agent(0,AgentConfig(profile=beta_profile,mcp_servers=""))
    native=deepcopy(mc.get_embedding_model_config(beta))
    assert mc.get_embedding_model_config(alpha)["name"]=="sentence-transformers/synthetic-local"
    assert mc.get_embedding_model_config(beta)==native
    assert mc.get_embedding_model_config()==mc.get_config().get("embedding_model")
    assert plugins.get_plugin_config("local_privacy_guard",beta)["enabled"] is False
    assert memory.get_agent_memory_subdir(alpha).startswith("privacy-profiles/")
    assert memory.get_agent_memory_subdir(beta)=="default"
    assert (shared_path.read_bytes() if shared_path.exists() else None)==before
    from helpers.modules import import_module
    Plugins = import_module("api/plugins.py").Plugins
    import threading
    api=Plugins(None,threading.RLock())
    display=api._get_config({"plugin_name":"local_privacy_guard","agent_profile":alpha_profile})
    assert display["data"]["local_embedding"]["model"]=="sentence-transformers/synthetic-local"
    unconfigured=api._get_config({"plugin_name":"local_privacy_guard","agent_profile":beta_profile})
    assert unconfigured["loaded_path"]==""
    # A conflicting named chat preset is blocked without rewriting it.
    alpha.context.set_data("chat_model_override",{"preset_name":"Default"})
    with pytest.raises(ValueError,match="embedding"):
        mc.get_embedding_model_config(alpha)
    assert mc.get_embedding_model_config(beta)==native

def test_filters_are_owned_by_agent_and_rebuilt_after_settings_change():
    from usr.plugins.local_privacy_guard.extensions.python.chat_model_call_before._10_pii_filter import _get_filter,_filter_cache
    class Agent:pass
    alpha=Agent();beta=Agent();config={"use_ner":False,"languages":["en"],"use_regex":True}
    first=_get_filter(alpha,config);other=_get_filter(beta,config)
    assert first is not other
    assert _get_filter(alpha,config) is first
    changed={**config,"use_regex":False}
    assert _get_filter(alpha,changed) is not first
    assert _get_filter(beta,config) is other

def test_profile_storage_rejects_empty_scope_and_path_escape(monkeypatch):
    pytest.importorskip("helpers.files")
    from usr.plugins.local_privacy_guard.helpers.agent_scope import selected_path
    from helpers import plugins
    for profile in ("", "../developer"):
        with pytest.raises(ValueError):selected_path("",profile)
    monkeypatch.setattr(plugins,"determine_plugin_asset_path",lambda *args:"/tmp/outside-profile/config.json")
    with pytest.raises(ValueError):selected_path("","agent0")
