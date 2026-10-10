"""
Local Embedding Configuration Helper.

Configures Agent Zero to use local sentence-transformers models for
memory embeddings instead of external API calls. All embedding
computation happens on the local machine.

Supports both preset file layouts:
- legacy dict layout:  {embedding: {...}}
- current list layout: [{name: Default, embedding: {...}}, ...]

Handles list-form presets safely: local embedding is applied to every
preset entry, and the original layout of the file is preserved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import yaml


DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_presets_path() -> Path:
    """Return the path to the user model presets file."""
    return Path("/a0/usr/plugins/_model_config/presets.yaml")


def load_presets(path: Path | None = None) -> Any:
    """Load the presets YAML file. Returns dict (legacy) or list (current)."""
    p = path or get_presets_path()
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def save_presets(presets: Any, path: Path | None = None) -> None:
    """Save the presets YAML file, preserving the original layout."""
    p = path or get_presets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(presets, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _iter_preset_entries(presets: Any) -> Iterable[Tuple[dict, str]]:
    """Yield (container, key) for every editable embedding section.

    dict layout: a single top-level 'embedding' section.
    list layout: one 'embedding' section per preset entry.
    """
    if isinstance(presets, dict):
        yield presets, "embedding"
    elif isinstance(presets, list):
        for entry in presets:
            if isinstance(entry, dict):
                yield entry, "embedding"


def _backup_file(path: Path) -> str | None:
    """Create a safety backup of path. Returns backup path or None."""
    if not path.exists():
        return None
    backup_path = path.with_suffix(path.suffix + ".privacy-guard-backup")
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return str(backup_path)


def _entry_name(container: dict) -> str:
    return str(container.get("name") or "legacy")


def configure_local_embedding(model: str = DEFAULT_LOCAL_MODEL, path: Path | None = None) -> Dict[str, Any]:
    """Configure all presets to use a local sentence-transformers embedding model.

    Agent Zero's models.py automatically routes model names starting with
    'sentence-transformers/' to the local LocalSentenceTransformerWrapper,
    so no API key or external endpoint is used for embeddings.

    Returns a dict with status information.
    """
    result: Dict[str, Any] = {
        "model": model,
        "changed": False,
        "backup": None,
        "errors": [],
        "presets_updated": [],
    }

    p = path or get_presets_path()
    try:
        presets = load_presets(p)
    except Exception as exc:
        result["errors"].append(f"presets could not be read: {exc}")
        return result

    changed_any = False
    for container, key in _iter_preset_entries(presets):
        embedding = container.get(key)
        if not isinstance(embedding, dict):
            embedding = {}
            container[key] = embedding

        current_provider = embedding.get("provider", "")
        current_name = embedding.get("name", "")

        if current_provider == "huggingface" and current_name == model:
            continue

        if not changed_any:
            result["backup"] = _backup_file(p)

        embedding["provider"] = "huggingface"
        embedding["name"] = model
        # Remove any API key that could route embeddings externally
        embedding.pop("api_key", None)
        embedding.pop("api_base", None)
        changed_any = True
        result["presets_updated"].append(_entry_name(container))

    if changed_any:
        try:
            save_presets(presets, p)
            result["changed"] = True
        except Exception as exc:
            result["errors"].append(f"presets could not be saved: {exc}")
    return result


def restore_embedding_backup(path: Path | None = None) -> Dict[str, Any]:
    """Restore presets.yaml from the .privacy-guard-backup if it exists.

    Called during uninstall so the presets file returns to the state before
    the plugin configured local embeddings. No-op when no backup exists.
    """
    result: Dict[str, Any] = {"restored": False, "backup": None, "note": ""}
    p = path or get_presets_path()
    backup_path = p.with_suffix(p.suffix + ".privacy-guard-backup")
    if not backup_path.exists():
        result["note"] = "no backup found, nothing to restore"
        return result
    try:
        # Sanity check: backup must be parseable YAML with a real presets
        # structure before it replaces anything: a list of preset entries,
        # or a dict containing an embedding section.
        with open(backup_path, "r", encoding="utf-8") as f:
            parsed = yaml.safe_load(f)
        valid = isinstance(parsed, list) and all(isinstance(e, dict) for e in parsed)
        valid = valid or (isinstance(parsed, dict) and "embedding" in parsed)
        if not valid:
            raise ValueError("backup is not a presets structure")
        p.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")
        result["restored"] = True
        result["backup"] = str(backup_path)
    except Exception as exc:
        result["note"] = f"restore failed: {exc}"
    return result


def verify_embedding_is_local(path: Path | None = None) -> Dict[str, Any]:
    """Verify that the configured embedding models run locally.

    Returns a dict with 'is_local' (True only when every embedding section
    uses a sentence-transformers model) and per-section details.
    """
    presets = load_presets(path)
    sections: list = []
    for container, _key in _iter_preset_entries(presets):
        emb = container.get("embedding", {})
        sections.append(emb if isinstance(emb, dict) else {})
    if not sections:
        sections = [{}]

    details = []
    all_local = True
    for emb in sections:
        name = emb.get("name", "")
        provider = emb.get("provider", "")
        is_local = bool(name) and name.startswith("sentence-transformers/")
        all_local = all_local and is_local
        details.append({"provider": provider, "model": name, "is_local": is_local})

    return {
        "is_local": all_local,
        "sections": details,
        "api_base": (sections[0].get("api_base") if isinstance(sections[0], dict) else "") or "",
        "api_key_set": any(isinstance(s, dict) and s.get("api_key") for s in sections),
    }


def check_sentence_transformers_available() -> bool:
    """Check if sentence-transformers is importable."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False
