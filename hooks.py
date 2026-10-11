"""
Local Privacy Guard - Lifecycle hooks.

Handles installation of spaCy language models based on user configuration
and cleanup on uninstall.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# spaCy model mapping: language code -> model name
SPACY_MODELS = {
    "en": "en_core_web_sm",      # ALWAYS installed (base requirement)
    "de": "de_core_news_sm",
    "fr": "fr_core_news_sm",
    "es": "es_core_news_sm",
    "it": "it_core_news_sm",
    "nl": "nl_core_news_sm",
    "pt": "pt_core_news_sm",
    "pl": "pl_core_news_sm",
}

# English is always required - cannot be disabled
BASE_LANGUAGE = "en"


def _get_configured_languages() -> list[str]:
    """Read configured languages from plugin config."""
    try:
        import yaml
        config_path = Path(__file__).parent / "default_config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
            pii_cfg = config.get("pii_filter", {})
            langs = pii_cfg.get("languages", ["de"])
            # Always include English
            if BASE_LANGUAGE not in langs:
                langs = [BASE_LANGUAGE] + langs
            return langs
    except Exception:
        pass
    # Fallback: English + German
    return [BASE_LANGUAGE, "de"]


def _install_spacy_model(model_name: str) -> dict:
    """Install a spaCy model. Returns status dict."""
    # Check if already installed
    check = subprocess.run(
        [sys.executable, "-m", "spacy", "info", model_name],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return {"model": model_name, "status": "already_installed"}
    
    # Download model
    proc = subprocess.run(
        [sys.executable, "-m", "spacy", "download", model_name],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode == 0:
        return {"model": model_name, "status": "installed"}
    else:
        return {
            "model": model_name,
            "status": "failed",
            "error": proc.stderr[:200] if proc.stderr else "unknown error"
        }


def install() -> dict:
    """
    Install required spaCy language models.
    English (en) is ALWAYS installed. Additional languages are read from config.
    """
    result = {"spacy_models": [], "errors": [], "languages": []}

    languages = _get_configured_languages()
    result["languages"] = languages

    for lang in languages:
        model_name = SPACY_MODELS.get(lang)
        if not model_name:
            result["errors"].append(f"Unknown language '{lang}' - no spaCy model mapping")
            continue
        
        status = _install_spacy_model(model_name)
        result["spacy_models"].append(status)
        if status["status"] == "failed":
            result["errors"].append(
                f"Failed to install {model_name} ({lang}): {status.get('error', 'unknown')}"
            )

    return result


def pre_update() -> dict:
    """Prepare for plugin update - nothing to stop."""
    return {"status": "ok"}


def _load_embedding_config_module():
    """Load embedding_config.py by file path (robust at uninstall time)."""
    import importlib.util

    module_path = Path(__file__).parent / "helpers" / "embedding_config.py"
    spec = importlib.util.spec_from_file_location("_lpg_embedding_config", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def uninstall() -> dict:
    """
    Clean up on uninstall.

    - Stops profile runtime overrides without writing shared presets.
      Legacy embedding backups remain available for manual recovery.
    - spaCy models are preserved: they are shared packages that other
      plugins or agents may use.
    """
    result = {
        "status": "ok",
        "note": "spaCy models preserved (may be used by other plugins)",
        "embedding_restore": None,
    }
    result["note"] += "; shared presets and legacy backups preserved; profile runtime overrides stop when uninstalled"
    return result


def save_plugin_config(settings=None, project_name="", agent_profile="", **kwargs):
    from usr.plugins.local_privacy_guard.helpers.agent_scope import selected_path, embedding
    selected_path(project_name, agent_profile)
    if not isinstance(settings, dict):
        raise ValueError("Privacy settings must be an object.")
    embedding(settings)
    return settings


def get_plugin_config(default=None, agent=None, project_name="", agent_profile="", **kwargs):
    if agent is None:
        from helpers import plugins
        defaults = plugins.get_default_plugin_config("local_privacy_guard")
        if agent_profile:
            from usr.plugins.local_privacy_guard.helpers.agent_scope import selected_path
            import json
            path = selected_path(project_name or "", agent_profile)
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        return defaults
    from usr.plugins.local_privacy_guard.helpers.agent_scope import configuration
    return configuration(agent) or {**(default or {}), "enabled": False}
