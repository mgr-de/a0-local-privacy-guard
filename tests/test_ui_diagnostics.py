import pytest
from usr.plugins.local_privacy_guard.helpers import pii_detector as pd
from usr.plugins.local_privacy_guard.helpers.ui_diagnostics import example, SAMPLE


def settings(**changes):
    return {"enabled": True, "pii_filter": {"enabled": True, "use_regex": True,
            "use_ner": False, "action": "redact", "languages": ["de"], **changes}}


def test_example_runs_real_filter_on_only_fixed_data():
    config = settings(store_mapping=True, custom_patterns=[{"regex": ".*", "name": "ANY"}])
    result = example(config)
    assert result["sample"] == SAMPLE
    assert result["output"] == "My email is <EMAIL>."
    assert result["detected"] == 1
    assert "mapping" not in result
    assert config["pii_filter"]["store_mapping"] is True


@pytest.mark.parametrize("action,output,blocked", [
    ("redact", "My email is <EMAIL>.", False), ("log_only", SAMPLE, False), ("block", None, True)])
def test_example_respects_runtime_action(action, output, blocked):
    result = example(settings(action=action))
    assert result["output"] == output
    assert result["blocked"] is blocked


def test_disabled_filter_and_no_methods_send_unchanged():
    for config in (settings(enabled=False), {**settings(), "enabled": False}, settings(use_regex=False)):
        result = example(config)
        assert result["output"] == SAMPLE
        assert result["detected"] == 0


def test_missing_name_models_are_not_hidden_by_regex_success(monkeypatch):
    monkeypatch.setattr(pd, "_get_nlp", lambda lang: None)
    result = example(settings(use_ner=True))
    assert result["output"] == "My email is <EMAIL>."
    assert result["missing_languages"] == ["en", "de"]
    assert result["loaded_languages"] == []


@pytest.mark.parametrize("config", [None, [], {}, settings(action="unknown"),
    settings(languages=["xx"]), settings(languages="de"), settings(use_ner="true")])
def test_invalid_input_rejected(config):
    with pytest.raises(ValueError):
        example(config)
