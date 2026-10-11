"""Tests for helpers/privacy_verifier.py: no KeyError, requesty checker,
component selection, and error containment."""

import yaml

from usr.plugins.local_privacy_guard.helpers import embedding_config as ec
from usr.plugins.local_privacy_guard.helpers import privacy_verifier as pv

LOCAL = ec.DEFAULT_LOCAL_MODEL


def _write(presets_path, data):
    presets_path.write_text(
        yaml.safe_dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )


def test_verify_embedding_no_keyerror_on_valid_local(tmp_path, monkeypatch):
    p = tmp_path / "presets.yaml"
    _write(p, [{"name": "Default", "embedding": {"provider": "huggingface", "name": LOCAL}}])
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)

    # must not raise KeyError: model
    result = pv.verify_embedding()
    assert result["component"] == "embedding"
    assert LOCAL in result["model"]
    # sentence-transformers is not installed in the test venv -> listed issue
    assert any("sentence-transformers" in i for i in result["issues"]) or result["is_local"]


def test_verify_embedding_reports_nonlocal_sections(tmp_path, monkeypatch):
    p = tmp_path / "presets.yaml"
    _write(p, [
        {"name": "Default", "embedding": {"provider": "openai", "name": "text-embedding-3-small"}},
    ])
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)

    result = pv.verify_embedding()
    assert result["is_local"] is False
    assert any("non-local" in i for i in result["issues"])
    assert "text-embedding-3-small" in result["model"]


def test_verify_requesty_detects_gateway(tmp_path, monkeypatch):
    p = tmp_path / "presets.yaml"
    _write(p, [
        {
            "name": "Default",
            "chat": {"provider": "other", "api_base": "https://router.eu.requesty.ai/v1"},
            "embedding": {"provider": "huggingface", "name": LOCAL},
        },
        {
            "name": "Efficiency",
            "chat": {"provider": "openrouter", "api_base": "https://openrouter.ai/api/v1"},
            "embedding": {"provider": "huggingface", "name": LOCAL},
        },
    ])
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)

    result = pv.verify_requesty()
    assert result["ok"] is False
    assert result["routed"] == [{"preset": "Default", "slot": "chat", "api_base": "https://router.eu.requesty.ai/v1"}]


def test_verify_requesty_clean_when_no_gateway(tmp_path, monkeypatch):
    p = tmp_path / "presets.yaml"
    _write(p, [{"name": "Default", "embedding": {"provider": "huggingface", "name": LOCAL}}])
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)

    result = pv.verify_requesty()
    assert result["ok"] is True
    assert result["issues"] == []


def test_run_verification_requesty_component_known(tmp_path, monkeypatch):
    p = tmp_path / "presets.yaml"
    _write(p, [{"name": "Default", "embedding": {"provider": "huggingface", "name": LOCAL}}])
    monkeypatch.setattr(ec, "get_presets_path", lambda: p)

    report = pv.run_verification({}, components=["requesty"])
    assert report["results"][0]["component"] == "requesty"
    assert report["results"][0]["issues"] != ["unknown component"]


def test_run_verification_unknown_component_flagged():
    report = pv.run_verification({}, components=["nonexistent"])
    assert report["overall_ok"] is False
    assert report["results"][0]["issues"] == ["unknown component"]


def test_run_verification_contains_exceptions_as_issues(tmp_path, monkeypatch):
    def boom():
        raise RuntimeError("exploded")

    monkeypatch.setattr(pv, "verify_memory", boom)
    report = pv.run_verification({}, components=["memory"])
    assert report["overall_ok"] is False
    assert "exploded" in report["results"][0]["issues"]


def test_verify_pii_filter_flags():
    ok = pv.verify_pii_filter({"pii_filter": {"enabled": True, "action": "redact", "store_mapping": False}})
    assert ok["ok"] is True

    bad = pv.verify_pii_filter({"pii_filter": {"enabled": True, "action": "log_only", "store_mapping": True}})
    assert bad["ok"] is False
    assert len(bad["issues"]) == 2
