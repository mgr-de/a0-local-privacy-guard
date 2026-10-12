import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from usr.plugins.local_privacy_guard.helpers import nym_backend as nym
from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter


def test_missing_bundle_is_fail_closed():
    with pytest.raises(ValueError, match='no fallback'):
        PIIFilter({'backend': 'nym'})


@pytest.mark.parametrize('config', [{'nym_threads': 0}, {'nym_stride': 512}, {'nym_threshold': 2}])
def test_invalid_settings_are_sanitized(config):
    with pytest.raises(ValueError, match='no fallback') as error:
        nym.get_model({'nym_model_dir': '/private-test-path', **config})
    assert '/private-test-path' not in str(error.value)


def test_decode_unicode_bio_and_name_parts():
    text = '🙂 Alina Beispiel!'
    labels = {0: 'O', 1: 'B-GIVEN_NAME', 2: 'B-SURNAME'}
    assert nym.decode(text, [((2, 7), 1, .9), ((8, 16), 2, .8)], labels, .5) == [(2, 16, 'PERSON', .8)]
    assert nym.decode(text, [((2, 7), 1, .4)], labels, .5) == []


def test_orphan_i_and_adjacent_b_entities():
    labels = {0: 'O', 1: 'I-EMAIL', 2: 'B-EMAIL'}
    assert nym.decode('a b', [((0, 1), 1, .9), ((2, 3), 2, .8)], labels, .5) == [
        (0, 1, 'EMAIL', .9), (2, 3, 'EMAIL', .8)]


def test_optional_engine_uses_shared_regex_cache_and_offsets(monkeypatch):
    calls = []
    def detect(text, threshold):
        calls.append(text)
        start = text.find('Alina Beispiel')
        return [(start, start + 14, 'PERSON', .9)] if start >= 0 else []
    fake = SimpleNamespace(identity={'revision': 'synthetic-v1'}, detect=detect)
    monkeypatch.setattr(nym, 'get_model', lambda config: fake)
    cfg = {'backend': 'nym', 'languages': ['de'], '_cache_scope': 'nym-unit'}
    filt = PIIFilter(cfg)
    text = '🙂 Alina Beispiel\nEmail: alina@example.invalid'
    result = filt.filter(text)
    assert any(h.original == 'Alina Beispiel' and h.start == 2 for h in result.detections)
    assert any(h.pii_type == 'EMAIL' and h.source == 'regex' for h in result.detections)
    assert filt.get_loaded_languages() == ['en', 'de']
    count = len(calls); filt.filter(text)
    assert len(calls) == count
    assert filt.metrics['cache_hits'] >= 2
    PIIFilter({**cfg, 'nym_threshold': .6}).filter(text)
    assert len(calls) > count


def test_inference_failure_has_no_text(monkeypatch):
    def fail(*args): raise RuntimeError('sensitive-test-value')
    monkeypatch.setattr(nym, 'get_model', lambda config: SimpleNamespace(identity={}, detect=fail))
    with pytest.raises(ValueError) as error:
        PIIFilter({'backend': 'nym'}).filter('sensitive-test-value')
    assert 'sensitive-test-value' not in str(error.value)


@pytest.mark.skipif(not os.environ.get('NYM_TEST_MODEL_DIR'), reason='verified local model bundle not supplied')
def test_real_onnx_overflow_roundtrip(tmp_path):
    from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
    model = os.environ['NYM_TEST_MODEL_DIR']
    config = {'backend': 'nym', 'nym_model_dir': model, 'nym_max_tokens': 64, 'nym_stride': 16,
              'use_regex': False, 'languages': ['de']}
    source = 'CSS HTML JSON. ' * 100 + 'Meine E-Mail ist alina@example.invalid.'
    result = PIIFilter(config).filter(source)
    expected_start = source.index('alina@example.invalid')
    # Model quality is scored separately: this fixture predicts the trailing dot.
    # Verify overflow reaches the final entity without asserting perfect NER.
    assert any(h.pii_type == 'EMAIL' and h.start <= expected_start and
               h.end >= expected_start + len('alina@example.invalid') for h in result.detections)
    assert all(source[h.start:h.end] == h.original for h in result.detections)
    mapping = Mapping(('', 'synthetic'), 'one', tmp_path)
    masked = source
    for hit in reversed(result.detections):
        masked = masked[:hit.start] + mapping.token(hit.pii_type, hit.original) + masked[hit.end:]
    assert mapping.restore(masked) == source
    assert Mapping(('', 'synthetic'), 'two', tmp_path).restore(masked) == masked


def test_checksum_mismatch(tmp_path):
    import json
    for name in ('model.onnx', 'tokenizer.json', 'config.json'):
        (tmp_path / name).write_text('synthetic')
    (tmp_path / 'manifest.json').write_text(json.dumps({'files': {name: 'wrong' for name in
        ('model.onnx', 'tokenizer.json', 'config.json')}}))
    with pytest.raises(ValueError, match='no fallback'):
        nym.get_model({'nym_model_dir': str(tmp_path)})
