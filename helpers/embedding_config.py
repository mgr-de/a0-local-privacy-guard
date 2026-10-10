"""
Local Embedding Configuration Helper.

Configures Agent Zero to use local sentence-transformers models for
memory embeddings instead of external API calls. All embedding
computation happens on the local machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_presets_path() -> Path:
    """Return the path to the user model presets file."""
    return Path("/a0/usr/plugins/_model_config/presets.yaml")


def load_presets(path: Path | None = None) -> Dict[str, Any]:
    """Load the presets YAML file."""
    p = path or get_presets_path()
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_presets(presets: Dict[str, Any], path: Path | None = None) -> None:
    """Save the presets YAML file."""
    p = path or get_presets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(presets, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def configure_local_embedding(model: str = DEFAULT_LOCAL_MODEL, path: Path | None = None) -> Dict[str, Any]:
    """Configure presets.yaml to use a local sentence-transformers embedding model.

    Agent Zero's models.py automatically routes model names starting with
    'sentence-transformers/' to the local LocalSentenceTransformerWrapper,
    so no API key or external endpoint is used for embeddings.

    Returns a dict with status information.
    """
    result: Dict[str, Any] = {"model": model, "changed": False, "backup": None, "errors": []}

    p = path or get_presets_path()
    presets = load_presets(p)

    # Ensure top-level embedding section exists
    embedding = presets.get("embedding")
    if not isinstance(embedding, dict):
        embedding = {}
        presets["embedding"] = embedding

    current_provider = embedding.get("provider", "")
    current_name = embedding.get("name", "")

    # Already configured for local execution?
    if current_provider == "huggingface" and current_name == model:
        result["changed"] = False
        return result

    # Create a backup before modifying
    if p.exists():
        backup_path = p.with_suffix(p.suffix + ".privacy-guard-backup")
        backup_path.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        result["backup"] = str(backup_path)

    # Apply local embedding configuration
    embedding["provider"] = "huggingface"
    embedding["name"] = model
    # Remove any API key that could route embeddings externally
    embedding.pop("api_key", None)
    embedding.pop("api_base", None)

    save_presets(presets, p)
    result["changed"] = True
    return result


def verify_embedding_is_local(path: Path | None = None) -> Dict[str, Any]:
    """Verify that the configured embedding model runs locally.

    Returns a dict with 'is_local' and details.
    """
    presets = load_presets(path)
    embedding = presets.get("embedding", {})
    name = embedding.get("name", "")
    provider = embedding.get("provider", "")

    is_local = bool(name) and name.startswith("sentence-transformers/")
    return {
        "is_local": is_local,
        "provider": provider,
        "model": name,
        "api_base": embedding.get("api_base", ""),
        "api_key_set": bool(embedding.get("api_key")),
    }


def check_sentence_transformers_available() -> bool:
    """Check if sentence-transformers is importable."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False
