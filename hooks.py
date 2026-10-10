"""Local Privacy Guard - Lifecycle Hooks.

Handles installation of dependencies (spaCy models) and cleanup on uninstall.
All operations are local - no network calls during setup.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def install() -> dict:
    """Install required spaCy language models locally."""
    result = {"spacy_models": [], "errors": []}

    models = ["de_core_news_sm", "en_core_web_sm"]
    for model in models:
        try:
            # Check if model is already installed
            check = subprocess.run(
                [sys.executable, "-m", "spacy", "info", model],
                capture_output=True,
                text=True,
            )
            if check.returncode == 0:
                result["spacy_models"].append({"model": model, "status": "already_installed"})
                continue

            # Download model
            proc = subprocess.run(
                [sys.executable, "-m", "spacy", "download", model],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if proc.returncode == 0:
                result["spacy_models"].append({"model": model, "status": "installed"})
            else:
                result["errors"].append(f"Failed to install {model}: {proc.stderr[:200]}")
        except Exception as exc:
            result["errors"].append(f"Error installing {model}: {str(exc)[:200]}")

    return result


def pre_update() -> None:
    """Prepare for update - no special action needed."""
    pass


def uninstall() -> None:
    """Cleanup on uninstall. spaCy models are shared, so we don't remove them."""
    # spaCy models may be used by other plugins, so we leave them installed
    pass


def get_plugin_config(default=None, **kwargs):
    """Return plugin config unchanged (no secrets to redact)."""
    return default


def save_plugin_config(settings=None, **kwargs):
    """Return settings unchanged."""
    return settings
