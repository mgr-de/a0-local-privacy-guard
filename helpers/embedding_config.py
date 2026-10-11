"""
Local Embedding Configuration Helper.

Configures Agent Zero to use local sentence-transformers models for
memory embeddings instead of external API calls. All embedding
computation happens on the local machine.

Supports both preset file layouts:
- legacy dict layout:  {embedding: {...}}
- current list layout: [{name: Default, embedding: {...}}, ...]

Backup semantics (generation-safe since v1.1.0):
- Every change records the pre-change embedding sections in a JSON journal
  (``presets.yaml.privacy-guard-backup.json``). The journal keeps the
  original state of a section across repeated plugin changes (A -> B -> C
  still restores A), and records the user's own value whenever the plugin
  re-writes a section the user had changed in the meantime.
- Restore only touches presets that still exist and still contain exactly
  the values this plugin wrote. Removed or user-modified presets are left
  alone, so user changes are preserved and no removed presets (e.g. old
  Requesty presets) are resurrected.
- Legacy full-file backups (``.privacy-guard-backup``) from plugin versions
  <= 1.0.x are restored section-by-section with the same safety rules and
  are removed after a successful restore.
- All file writes are atomic (temp file + os.replace) so an aborted write
  can never leave a truncated presets file behind.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import yaml

DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

PLUGIN_EMBEDDING_PROVIDER = "huggingface"
JOURNAL_SUFFIX = ".privacy-guard-backup.json"
LEGACY_BACKUP_SUFFIX = ".privacy-guard-backup"


def get_presets_path() -> Path:
    """Return the path to the user model presets file.

    The path is resolved through the Agent Zero framework so it works on
    any install root (Docker, native Windows, custom launcher directories).
    Falls back to ``$A0_ROOT`` (default ``/a0``) when the framework helpers
    are not importable, e.g. in isolated test environments.
    """
    try:
        from helpers import files as framework_files

        return Path(
            framework_files.get_abs_path(
                framework_files.USER_DIR,
                framework_files.PLUGINS_DIR,
                "_model_config",
                "presets.yaml",
            )
        )
    except Exception:
        root = Path(os.environ.get("A0_ROOT", "/a0"))
        return root / "usr" / "plugins" / "_model_config" / "presets.yaml"


def load_presets(path: Path | None = None) -> Any:
    """Load the presets YAML file. Returns dict (legacy) or list (current)."""
    p = path or get_presets_path()
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text to path atomically (temp file + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def save_presets(presets: Any, path: Path | None = None) -> None:
    """Save the presets YAML file atomically, preserving the layout."""
    p = path or get_presets_path()
    content = yaml.safe_dump(
        presets, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    _atomic_write_text(p, content)


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


def _entry_name(container: dict) -> str:
    return str(container.get("name") or "legacy")


def _journal_path(presets_path: Path) -> Path:
    return presets_path.with_name(presets_path.name + JOURNAL_SUFFIX)


def _legacy_backup_path(presets_path: Path) -> Path:
    return presets_path.with_name(presets_path.name + LEGACY_BACKUP_SUFFIX)


def _load_journal(presets_path: Path) -> Dict[str, dict] | None:
    """Load the change journal. Returns None when no journal exists.

    A corrupt journal raises ValueError so callers can decide not to
    destroy potentially recoverable data.
    """
    jp = _journal_path(presets_path)
    if not jp.exists():
        return None
    try:
        data = yaml.safe_load(jp.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"backup journal is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("backup journal is not a mapping")
    entries: Dict[str, dict] = {}
    for name, entry in data.items():
        if not isinstance(entry, dict) or "original" not in entry:
            raise ValueError(f"backup journal entry '{name}' is malformed")
        entries[str(name)] = entry
    return entries


def _save_journal(presets_path: Path, journal: Dict[str, dict]) -> None:
    _atomic_write_text(
        _journal_path(presets_path),
        yaml.safe_dump(journal, default_flow_style=False, allow_unicode=True, sort_keys=False),
    )


def _is_plugin_owned(embedding: Any, plugin_model: str | None = None) -> bool:
    """True when the embedding section contains values written by this plugin."""
    if not isinstance(embedding, dict):
        return False
    if embedding.get("provider") != PLUGIN_EMBEDDING_PROVIDER:
        return False
    name = str(embedding.get("name", "") or "")
    if plugin_model is not None:
        return name == plugin_model
    return name.startswith("sentence-transformers/")


def configure_local_embedding(
    model: str = DEFAULT_LOCAL_MODEL, path: Path | None = None
) -> Dict[str, Any]:
    """Configure all presets to use a local sentence-transformers embedding model.

    Agent Zero's models.py automatically routes model names starting with
    'sentence-transformers/' to the local LocalSentenceTransformerWrapper,
    so no API key or external endpoint is used for embeddings.

    The pre-change state of every modified section is recorded in the JSON
    journal (first change wins per preset unless the user modified the
    section in the meantime, in which case the user's value is recorded).

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

    try:
        journal = _load_journal(p)
    except ValueError as exc:
        # Keep the (possibly user-recoverable) journal intact and refuse to
        # touch the presets file rather than risk an unrestorable change.
        result["errors"].append(f"existing backup journal is invalid: {exc}")
        return result

    changed_any = False
    for container, key in _iter_preset_entries(presets):
        embedding = container.get(key)
        if not isinstance(embedding, dict):
            embedding = {}
            container[key] = embedding

        entry_name = _entry_name(container)
        current_provider = embedding.get("provider", "")
        current_name = embedding.get("name", "")

        if current_provider == PLUGIN_EMBEDDING_PROVIDER and current_name == model:
            continue  # already configured by us with the wanted model

        if journal is None:
            journal = {}

        if current_provider != PLUGIN_EMBEDDING_PROVIDER:
            # User (or framework) changed this section since our last write:
            # record the user's value so a later restore preserves it.
            journal[entry_name] = {
                "original": dict(embedding),
                "plugin_model": model,
            }
        elif entry_name not in journal:
            # First time we touch this preset: keep the true original state.
            journal[entry_name] = {
                "original": dict(embedding),
                "plugin_model": model,
            }
        else:
            # Re-writing a preset we already own (e.g. plugin update switched
            # the local model B -> C): keep the original, update the model tag.
            journal[entry_name]["plugin_model"] = model

        embedding["provider"] = PLUGIN_EMBEDDING_PROVIDER
        embedding["name"] = model
        # Remove any API key that could route embeddings externally
        embedding.pop("api_key", None)
        embedding.pop("api_base", None)
        changed_any = True
        result["presets_updated"].append(entry_name)

    if changed_any:
        try:
            save_presets(presets, p)
            if journal:
                _save_journal(p, journal)
                result["backup"] = str(_journal_path(p))
            result["changed"] = True
        except Exception as exc:
            result["errors"].append(f"presets could not be saved: {exc}")
    return result


def _find_container(presets: Any, entry_name: str) -> dict | None:
    """Find the preset container by name in either layout."""
    if isinstance(presets, dict):
        return presets if entry_name == "legacy" else None
    if isinstance(presets, list):
        for entry in presets:
            if isinstance(entry, dict) and _entry_name(entry) == entry_name:
                return entry
    return None


def _restore_from_journal(p: Path, journal: Dict[str, dict], result: Dict[str, Any]) -> None:
    try:
        presets = load_presets(p)
    except Exception as exc:
        result["note"] = f"restore failed: presets could not be read: {exc}"
        return

    restored: list[str] = []
    for entry_name, entry in journal.items():
        container = _find_container(presets, entry_name)
        if container is None:
            # Preset was removed by the user meanwhile: never resurrect it.
            result["missing_presets"].append(entry_name)
            continue
        current = container.get("embedding")
        if not _is_plugin_owned(current):
            # User changed this section after us: keep the user's value.
            result["skipped_user_modified"].append(entry_name)
            continue
        original = entry.get("original") or {}
        if original:
            container["embedding"] = dict(original)
        else:
            container.pop("embedding", None)
        restored.append(entry_name)

    if restored:
        try:
            save_presets(presets, p)
        except Exception as exc:
            result["note"] = f"restore failed: presets could not be saved: {exc}"
            return
    result["restored_presets"] = restored
    result["restored"] = bool(restored)
    # Journal is consumed; remove it so a later install that changes nothing
    # cannot replay a stale state on uninstall.
    try:
        _journal_path(p).unlink()
    except FileNotFoundError:
        pass


def _restore_from_legacy_backup(p: Path, result: Dict[str, Any]) -> None:
    """Section-level restore for full-file backups from plugin versions <= 1.0.x."""
    bp = _legacy_backup_path(p)
    try:
        with open(bp, "r", encoding="utf-8") as f:
            parsed = yaml.safe_load(f)
    except Exception as exc:
        result["note"] = f"restore failed: backup unreadable: {exc}"
        return

    valid = isinstance(parsed, list) and all(isinstance(e, dict) for e in parsed)
    valid = valid or (isinstance(parsed, dict) and "embedding" in parsed)
    if not valid:
        result["note"] = "restore failed: backup is not a presets structure"
        return

    try:
        presets = load_presets(p)
    except Exception as exc:
        result["note"] = f"restore failed: presets could not be read: {exc}"
        return

    restored: list[str] = []
    if isinstance(parsed, list):
        backup_entries: list[tuple[str, dict]] = [
            (_entry_name(e), e) for e in parsed if isinstance(e, dict)
        ]
    else:
        backup_entries = [("legacy", parsed)]

    for entry_name, backup_entry in backup_entries:
        container = _find_container(presets, entry_name)
        if container is None:
            # Preset no longer exists: never resurrect removed presets.
            result["missing_presets"].append(entry_name)
            continue
        current = container.get("embedding")
        if not _is_plugin_owned(current):
            # Only revert sections that still look like ours; keep user edits.
            result["skipped_user_modified"].append(entry_name)
            continue
        backup_emb = backup_entry.get("embedding")
        if isinstance(backup_emb, dict) and backup_emb:
            container["embedding"] = dict(backup_emb)
        else:
            container.pop("embedding", None)
        restored.append(entry_name)

    if restored:
        try:
            save_presets(presets, p)
        except Exception as exc:
            result["note"] = f"restore failed: presets could not be saved: {exc}"
            return
    result["restored_presets"] = restored
    result["restored"] = bool(restored)
    result["backup"] = str(bp)
    # Remove the consumed legacy backup so it cannot be replayed later.
    try:
        bp.unlink()
    except FileNotFoundError:
        pass


def restore_embedding_backup(path: Path | None = None) -> Dict[str, Any]:
    """Restore embedding sections this plugin modified from its backup.

    Called during uninstall. Only sections that still contain exactly the
    values written by this plugin are reverted; user changes and removed
    presets are preserved. No-op when no backup exists.
    """
    result: Dict[str, Any] = {
        "restored": False,
        "restored_presets": [],
        "skipped_user_modified": [],
        "missing_presets": [],
        "backup": None,
        "note": "",
    }
    p = path or get_presets_path()

    if _journal_path(p).exists():
        try:
            journal = _load_journal(p)
        except ValueError as exc:
            result["note"] = f"restore failed: {exc}"
            return result
        if journal is None:
            result["note"] = "backup journal is empty, nothing to restore"
            return result
        result["backup"] = str(_journal_path(p))
        _restore_from_journal(p, journal, result)
        return result

    if _legacy_backup_path(p).exists():
        _restore_from_legacy_backup(p, result)
        return result

    result["note"] = "no backup found, nothing to restore"
    return result


def verify_embedding_is_local(path: Path | None = None) -> Dict[str, Any]:
    """Verify that the configured embedding models run locally.

    Returns a dict with 'is_local' (True only when every embedding section
    uses a sentence-transformers model) and per-section details including
    the owning preset name.
    """
    presets = load_presets(path)
    entries: list[tuple[dict, Any]] = []
    for container, _key in _iter_preset_entries(presets):
        entries.append((container, container.get("embedding", {})))
    if not entries:
        entries = [({}, {})]

    details = []
    all_local = True
    api_base = ""
    api_key_set = False
    for container, emb in entries:
        emb = emb if isinstance(emb, dict) else {}
        name = emb.get("name", "")
        provider = emb.get("provider", "")
        is_local = bool(name) and name.startswith("sentence-transformers/")
        all_local = all_local and is_local
        if not api_base:
            api_base = emb.get("api_base") or ""
        if emb.get("api_key"):
            api_key_set = True
        details.append(
            {
                "preset": _entry_name(container) if container else "",
                "provider": provider,
                "model": name,
                "is_local": is_local,
            }
        )

    return {
        "is_local": all_local,
        "sections": details,
        "api_base": api_base,
        "api_key_set": api_key_set,
    }


def check_sentence_transformers_available() -> bool:
    """Check if sentence-transformers is importable."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False
