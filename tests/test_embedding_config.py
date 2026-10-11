"""Tests for helpers/embedding_config.py: journal-based backup, restore,
legacy backup migration, atomic writes, and path resolution."""

import yaml
from pathlib import Path

from usr.plugins.local_privacy_guard.helpers import embedding_config as ec

LOCAL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _write(presets_path, data):
    presets_path.write_text(
        yaml.safe_dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )


def _read(presets_path):
    return yaml.safe_load(presets_path.read_text(encoding="utf-8"))


def _entry(name="Default", provider="openai", model="text-embedding-3-small"):
    return {
        "name": name,
        "chat": {"provider": "openai", "name": "gpt-x"},
        "embedding": {"provider": provider, "name": model, "api_base": "https://x", "api_key": "K"},
    }


def _presets(name="Default", provider="openai", model="text-embedding-3-small"):
    return [_entry(name, provider, model)]


def test_configure_writes_local_embedding_and_journal(tmp_path):
    p = tmp_path / "presets.yaml"
    _write(p, _presets())

    result = ec.configure_local_embedding(path=p)

    assert result["changed"] is True
    data = _read(p)
    emb = data[0]["embedding"]
    assert emb["provider"] == "huggingface"
    assert emb["name"] == LOCAL
    assert "api_key" not in emb and "api_base" not in emb

    journal = ec._load_journal(p)
    assert journal is not None
    orig = journal["Default"]["original"]
    assert orig["provider"] == "openai"
    assert orig["name"] == "text-embedding-3-small"
    assert journal["Default"]["plugin_model"] == LOCAL


def test_generation_safety_a_to_b_to_c_restores_a(tmp_path):
    """A -> local B -> local C: uninstall must restore A, not B."""
    p = tmp_path / "presets.yaml"
    _write(p, _presets())

    ec.configure_local_embedding("sentence-transformers/B", path=p)
    # user changes nothing between the two plugin generations
    ec.configure_local_embedding("sentence-transformers/C", path=p)

    result = ec.restore_embedding_backup(path=p)

    assert result["restored"] is True
    data = _read(p)
    emb = data[0]["embedding"]
    assert emb["provider"] == "openai"
    assert emb["name"] == "text-embedding-3-small"


def test_journal_consumed_after_restore_no_replay(tmp_path):
    """After a successful uninstall restore, a later install that changes
    nothing must not replay a stale journal on its uninstall."""
    p = tmp_path / "presets.yaml"
    _write(p, _presets())
    ec.configure_local_embedding(path=p)
    ec.restore_embedding_backup(path=p)

    # simulate: reinstall, change nothing, uninstall again
    result = ec.restore_embedding_backup(path=p)
    assert result["restored"] is False
    assert "no backup" in result["note"]


def test_restore_preserves_user_changes(tmp_path):
    """If the user edits a section the plugin wrote, restore keeps the edit."""
    p = tmp_path / "presets.yaml"
    _write(p, _presets())
    ec.configure_local_embedding(path=p)

    # user switches embedding to their own model
    data = _read(p)
    data[0]["embedding"] = {"provider": "ollama", "name": "nomic-embed"}
    _write(p, data)

    result = ec.restore_embedding_backup(path=p)
    data = _read(p)
    assert data[0]["embedding"]["provider"] == "ollama"
    assert "Default" in result["skipped_user_modified"]


def test_restore_never_resurrects_removed_presets(tmp_path):
    """A preset removed by the user (or by Requesty cleanup) must not be
    resurrected from the backup."""
    p = tmp_path / "presets.yaml"
    _write(p, [_entry("Default"), _entry("Requesty", provider="requesty_guarded")])
    ec.configure_local_embedding(path=p)

    # user/Requesty cleanup removes the Requesty preset entirely
    data = _read(p)
    data = [e for e in data if e["name"] != "Requesty"]
    _write(p, data)

    result = ec.restore_embedding_backup(path=p)
    names = [e["name"] for e in _read(p)]
    assert "Requesty" not in names
    assert "Requesty" in result["missing_presets"]


def test_user_change_between_generations_is_recorded(tmp_path):
    """If the user changes the section while the plugin is installed, the
    uninstall restores the user's value, not the pre-install original."""
    p = tmp_path / "presets.yaml"
    _write(p, _presets())
    ec.configure_local_embedding("sentence-transformers/B", path=p)

    data = _read(p)
    data[0]["embedding"] = {"provider": "openai", "name": "text-embedding-3-large"}
    _write(p, data)

    # plugin update switches to model C: user's value must be journaled
    ec.configure_local_embedding("sentence-transformers/C", path=p)

    result = ec.restore_embedding_backup(path=p)
    data = _read(p)
    emb = data[0]["embedding"]
    assert emb["name"] == "text-embedding-3-large"


def test_legacy_full_file_backup_restores_sectionwise(tmp_path):
    """Legacy .privacy-guard-backup from <=1.0.x is restored per section
    with the same safety rules and is removed afterwards."""
    p = tmp_path / "presets.yaml"
    original = [_entry("Default"), _entry("Efficiency")]
    backup = tmp_path / "presets.yaml.privacy-guard-backup"
    backup.write_text(yaml.safe_dump(original, default_flow_style=False), encoding="utf-8")

    # current file: plugin-owned sections + a preset not in the backup
    current = [_entry("Default", provider="huggingface", model=LOCAL), _entry("New")]
    _write(p, current)

    result = ec.restore_embedding_backup(path=p)
    data = _read(p)

    # Default restored from backup, New untouched, Efficiency not resurrected
    assert data[0]["embedding"]["provider"] == "openai"
    names = [e["name"] for e in data]
    assert "Efficiency" not in names
    assert "New" in names
    assert result["restored"] is True
    assert not backup.exists()


def test_atomic_write_leaves_no_temp_files(tmp_path):
    p = tmp_path / "presets.yaml"
    _write(p, _presets())
    ec.save_presets(_read(p), p)
    leftovers = [f for f in tmp_path.iterdir() if f.name.startswith("presets.yaml.tmp-")]
    assert leftovers == []


def test_presets_path_resolution_overridable(tmp_path, monkeypatch):
    """Path resolution falls back to $A0_ROOT when the framework helpers
    are unavailable (isolated test env) and honors A0_ROOT."""
    monkeypatch.setenv("A0_ROOT", str(tmp_path))
    # hide any importable helpers module
    monkeypatch.setitem(__import__("sys").modules, "helpers", None)
    resolved = ec.get_presets_path()
    assert str(tmp_path) in str(resolved)
    assert resolved.name == "presets.yaml"


def test_verify_embedding_is_local_sections(tmp_path):
    p = tmp_path / "presets.yaml"
    _write(p, [_entry("A"), _entry("B")])
    result = ec.verify_embedding_is_local(path=p)
    assert result["is_local"] is False
    assert len(result["sections"]) == 2
    assert result["sections"][0]["preset"] == "A"
    assert result["api_key_set"] is True

    local_entry = _entry("A", provider="huggingface", model=LOCAL)
    local_entry["embedding"].pop("api_key")
    local_entry["embedding"].pop("api_base")
    _write(p, [local_entry])
    result = ec.verify_embedding_is_local(path=p)
    assert result["is_local"] is True
    assert result["api_key_set"] is False


def test_dict_layout_supported(tmp_path):
    p = tmp_path / "presets.yaml"
    _write(p, {"embedding": {"provider": "openai", "name": "x"}})
    result = ec.configure_local_embedding(path=p)
    assert result["changed"] is True
    data = _read(p)
    assert data["embedding"]["name"] == LOCAL
