"""
Privacy Verification Helper.

Checks that privacy-relevant Agent Zero components are configured to
run locally. Produces a report used by the startup extension for logging
and optional user warnings.
"""

from __future__ import annotations

from typing import Any, Dict, List

from usr.plugins.local_privacy_guard.helpers.embedding_config import (
    verify_embedding_is_local,
    check_sentence_transformers_available,
    load_presets,
)


def verify_pii_filter(config: Dict[str, Any]) -> Dict[str, Any]:
    """Verify PII filter configuration."""
    pii_cfg = (config or {}).get("pii_filter", {})
    issues: List[str] = []
    if not pii_cfg.get("enabled", False):
        issues.append("PII filter is disabled")
    if pii_cfg.get("action") == "log_only":
        issues.append("PII filter is in log_only mode - PII is sent unmodified")
    if pii_cfg.get("store_mapping", False):
        issues.append("store_mapping is enabled - PII is stored in memory (session only)")
    return {
        "component": "pii_filter",
        "ok": len(issues) == 0,
        "enabled": pii_cfg.get("enabled", False),
        "action": pii_cfg.get("action", "redact"),
        "issues": issues,
    }


def verify_embedding() -> Dict[str, Any]:
    """Verify that memory embeddings run locally."""
    result = verify_embedding_is_local()
    issues: List[str] = []

    sections = result.get("sections") or []
    models = [str(s.get("model", "") or "") for s in sections]
    model_summary = ", ".join(m for m in models if m) or "(none configured)"

    for section in sections:
        if not section.get("is_local"):
            issues.append(
                f"Preset '{section.get('preset', '')}' uses non-local embedding "
                f"model '{section.get('model', '')}' (provider: {section.get('provider', '')})"
            )
    if result.get("api_key_set"):
        issues.append("Embedding configuration contains an API key")
    if result.get("api_base"):
        issues.append(f"Embedding configuration points to external API: {result['api_base']}")
    if not check_sentence_transformers_available():
        issues.append("sentence-transformers package is not installed")
    return {
        "component": "embedding",
        "ok": len(issues) == 0,
        "is_local": result.get("is_local", False),
        "model": model_summary,
        "sections": sections,
        "issues": issues,
    }


def verify_memory() -> Dict[str, Any]:
    """Verify memory storage is local (FAISS files under the user dir)."""
    from pathlib import Path

    issues: List[str] = []
    try:
        from usr.plugins.local_privacy_guard.helpers.embedding_config import (
            get_presets_path,
        )

        # presets live under <root>/usr/plugins/_model_config; memory lives
        # under <root>/usr/memory in the same user tree.
        memory_dir = get_presets_path().parent.parent.parent / "memory"
    except Exception:
        memory_dir = Path("/a0/usr/memory")
    if not memory_dir.exists():
        issues.append("Memory directory does not exist yet (will be created on first use)")
    return {
        "component": "memory",
        "ok": True,  # memory plugin is local by design
        "storage": str(memory_dir),
        "issues": issues,
    }


def verify_requesty() -> Dict[str, Any]:
    """Verify whether any preset routes chat/utility calls through Requesty.

    Requesty is an external gateway: calls routed through it leave the
    local machine even when the PII filter is active. This check reports
    which presets reference it so the user can decide.
    """
    issues: List[str] = []
    routed: List[Dict[str, str]] = []
    try:
        presets = load_presets()
    except Exception as exc:
        return {
            "component": "requesty",
            "ok": False,
            "issues": [f"presets could not be read: {exc}"],
        }

    entries = presets if isinstance(presets, list) else [presets] if presets else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "legacy")
        for slot in ("chat", "utility", "embedding"):
            section = entry.get(slot)
            if not isinstance(section, dict):
                continue
            api_base = str(section.get("api_base", "") or "")
            provider = str(section.get("provider", "") or "")
            if "requesty" in api_base.lower() or "requesty" in provider.lower():
                routed.append({"preset": name, "slot": slot, "api_base": api_base})
                issues.append(
                    f"Preset '{name}' routes {slot} through external Requesty gateway"
                )

    return {
        "component": "requesty",
        "ok": len(routed) == 0,
        "routed": routed,
        "issues": issues,
    }


def run_verification(config: Dict[str, Any], components: List[str] | None = None, agent=None) -> Dict[str, Any]:
    """Run privacy verification for the given components.

    Returns a report dict with per-component results and an overall status.
    """
    checkers = {
        "pii_filter": lambda: verify_pii_filter(config),
        "embedding": verify_embedding,
        "memory": verify_memory,
        "requesty": verify_requesty,
    }
    if agent is not None:
        from plugins._model_config.helpers import model_config as mc
        from plugins._memory.helpers import memory
        def profile_embedding():
            effective = mc.get_embedding_model_config(agent)
            local = effective.get("provider") == "huggingface" and str(effective.get("name", "")).startswith("sentence-transformers/")
            return {"component":"embedding", "ok":local, "model":effective.get("name", ""),
                    "issues":[] if local else ["This profile does not resolve to a local sentence-transformers embedding."]}
        def profile_memory():
            return {"component":"memory", "ok":True, "storage":memory.get_agent_memory_subdir(agent), "issues":[]}
        def profile_requesty():
            providers = [getattr(agent.get_chat_model().a0_model_conf, "provider", ""),
                         getattr(agent.get_utility_model().a0_model_conf, "provider", "")]
            external = any("requesty" in str(provider).lower() for provider in providers)
            return {"component":"requesty", "ok":not external,
                    "issues":["This profile uses the external Requesty gateway."] if external else []}
        checkers.update(embedding=profile_embedding, memory=profile_memory, requesty=profile_requesty)
    wanted = [c for c in (components or list(checkers.keys())) if c]

    results = []
    for name in wanted:
        checker = checkers.get(name)
        if checker is None:
            results.append({"component": name, "ok": False, "issues": ["unknown component"]})
            continue
        try:
            results.append(checker())
        except Exception as exc:
            results.append({"component": name, "ok": False, "issues": [str(exc)]})

    return {
        "overall_ok": all(r.get("ok", False) for r in results),
        "results": results,
    }


# Alias for backward compatibility
verify_all = run_verification
