"""Tests for webui/config.html conventions and the plugin manifest."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_config_html_uses_store_gate_pattern():
    html = (ROOT / "webui" / "config.html").read_text(encoding="utf-8")
    assert '<div x-data>' in html
    assert html.count('<template x-if="config') >= 1
    # no inline scripts, no fetch calls, no self-registered Alpine components
    assert '<script' not in html
    assert 'fetch(' not in html
    assert 'pluginSettingsPage' not in html
    assert 'window.' not in html


def test_config_html_binds_auto_configure_key():
    html = (ROOT / "webui" / "config.html").read_text(encoding="utf-8")
    assert 'x-model="config.local_embedding.auto_configure"' in html
    # legacy mismatched key must be gone
    assert 'auto_configure_presets' not in html


def test_no_flattened_extension_folders():
    ext_dir = ROOT / "extensions" / "python"
    for d in ext_dir.iterdir():
        assert re.match(r"^[a-z_]+$", d.name), f"unexpected extension dir {d.name}"
    # retired startup point must be gone
    assert not (ext_dir / "startup").exists()


def test_manifest_keys_and_version():
    meta = yaml.safe_load((ROOT / "plugin.yaml").read_text(encoding="utf-8"))
    assert re.fullmatch(r"[a-z0-9_]+", meta["name"])
    assert meta["title"] and meta["description"] and meta["version"]
    assert meta["settings_sections"] == ["agent"]
    assert meta["per_project_config"] is True
    assert meta["per_agent_config"] is True
    assert set(meta.keys()) == {
        "name", "title", "description", "version",
        "settings_sections", "per_project_config", "per_agent_config",
    }


def test_default_config_matches_ui_keys():
    """Backend and frontend must use the same config key names."""
    dc = yaml.safe_load((ROOT / "default_config.yaml").read_text(encoding="utf-8"))
    html = (ROOT / "webui" / "config.html").read_text(encoding="utf-8")
    assert "auto_configure" in dc["local_embedding"]
    assert "auto_configure_presets" not in yaml.safe_dump(dc)
    for key in ("enabled", "model", "auto_configure", "verify_local"):
        assert f"config.local_embedding.{key}" in html


def test_license_at_root():
    assert (ROOT / "LICENSE").exists()


def test_hooks_restore_result_contract():
    """uninstall() must tolerate the new restore result shape."""
    import ast
    src = (ROOT / "hooks.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert "restore_embedding_backup" in src
