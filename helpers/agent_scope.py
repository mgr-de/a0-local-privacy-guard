"""Opt in by saving settings for an explicit profile, never by inheritance."""
import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

def selected_path(project, profile):
    from helpers import plugins, files
    if not profile or any(not isinstance(v, str) or v in (".", "..") or not re.fullmatch(r"[\w .-]*", v) for v in (project, profile)):
        raise ValueError("Choose one valid agent profile in the settings toolbar first.")
    target = Path(plugins.determine_plugin_asset_path("local_privacy_guard", project, profile, "config.json")).resolve()
    if not target.is_relative_to(Path(files.get_abs_path(files.USER_DIR)).resolve()):
        raise ValueError("Profile configuration is outside the user directory.")
    return target

def configuration(agent):
    from helpers import projects
    from usr.plugins.local_privacy_guard.helpers.instance import manager
    instance=manager()
    if instance is not None and agent is not None:
        return instance.local_config(agent)
    if agent is None:
        return None
    from agent import AgentContext
    from plugins._agent_editor.helpers.editor import EditorAgent
    editing=isinstance(agent,EditorAgent)
    visited=set()
    ancestor=agent
    while True:
        if editing:break
        identity=getattr(ancestor.context,'id',None)
        if not identity:break # Native EditorAgent has no live chat context.
        if identity in visited:raise ValueError('Cyclic subordinate privacy context.')
        visited.add(identity)
        getter=getattr(ancestor.context,'get_output_data',None)
        parent_id=getter('parent_context_id') if getter else None
        if not parent_id:break
        parent=AgentContext.get(parent_id)
        if parent is None or parent.agent0 is None:
            raise ValueError('The parent privacy context is unavailable. Restore the parent chat before continuing this subordinate.')
        ancestor=parent.agent0
    if ancestor is not agent:
        inherited=configuration(ancestor)
        if inherited and inherited.get('enabled'):return inherited
    root = None if editing else getattr(agent.context, "agent0", None)
    if root is not None and root is not agent:
        inherited = configuration(root)
        if inherited and inherited.get("enabled"):
            return inherited
    project = projects.get_context_project_name(agent.context) or ""
    path = selected_path(project, agent.config.profile)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Profile privacy settings cannot be read safely.")
    return value

def embedding(config):
    section = config.get("local_embedding", {})
    if not config.get("enabled") or not section.get("enabled") or not section.get("auto_configure"):
        return None
    model = section.get("model", "")
    if not isinstance(model, str) or not model.startswith("sentence-transformers/") or not model.removeprefix("sentence-transformers/"):
        raise ValueError("Local embeddings require a sentence-transformers model.")
    return {"provider": "huggingface", "name": model, "kwargs": {}}

def apply(data, agent):
    args = data.get("args", ())
    name = args[0] if args else data.get("kwargs", {}).get("plugin_name")
    if agent is None or name not in ("_model_config", "_memory") or not isinstance(data.get("result"), dict):
        return
    config = configuration(agent)
    if not config or not config.get("enabled"):
        return
    local = embedding(config)
    result = deepcopy(data["result"])
    if name == "_model_config" and local:
        # Named chat presets are resolved after this hook by the framework.
        # Reject a conflicting override rather than permit a remote embedding.
        override = agent.context.get_data("chat_model_override")
        if isinstance(override, dict):
            from plugins._model_config.helpers import model_config as mc
            preset = mc.resolve_preset(override["preset_name"]) if override.get("preset_name") else override
            candidate = (preset or {}).get("embedding", {})
            if candidate and (candidate.get("provider") != local["provider"] or candidate.get("name") != local["name"]
                    or candidate.get('kwargs') not in (None,{}) or any(candidate.get(field) for field in ('api_base','api_key','base_url'))):
                raise ValueError("This chat preset conflicts with profile-local embeddings. Clear the chat model override or use matching local embeddings.")
            if override.get("preset_name") and not candidate:
                raise ValueError("The chat preset must explicitly use the profile-local embedding model.")
        result["embedding_model"] = local
    elif name == "_memory":
        from helpers import projects
        identity = [projects.get_context_project_name(agent.context) or "", agent.config.profile, local]
        result["project_memory_isolation"] = False
        result["agent_memory_subdir"] = "privacy-profiles/" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:32]
    data["result"] = result
