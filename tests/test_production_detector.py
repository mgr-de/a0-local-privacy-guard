"""Upgrade compatibility without optional detectors or mapping changes."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from usr.plugins.local_privacy_guard.helpers import pii_detector as pd
from usr.plugins.local_privacy_guard.helpers.mapping import Mapping

@pytest.mark.parametrize('backend', ['local', 'presidio', 'nym'])
def test_retired_settings_use_fixed_detector_without_mutating_user_config(monkeypatch, tmp_path, backend):
    entity = SimpleNamespace(start_char=0,end_char=13,text='Anna Beispiel',label_='PERSON')
    nlp = SimpleNamespace(meta={'version':'synthetic'},pipe=lambda texts,batch_size:
        (SimpleNamespace(ents=[entity] if text.startswith('Anna Beispiel') else []) for text in texts))
    monkeypatch.setattr(pd,'_get_nlp',lambda language:nlp)
    config = {'backend':backend,'languages':['en','fr'],'presidio_variant':'B',
              'nym_model_dir':'unavailable-evaluation-artifact','nym_threshold':.9}
    original = deepcopy(config)
    scanner = pd.PIIFilter(config)
    assert config == original and scanner.backend == 'local'
    assert scanner.ner_languages == ['en','fr']
    assert not any(k.startswith(('nym_', 'presidio_')) for k in scanner.config)
    source = 'Anna Beispiel: anna@example.invalid'
    result = scanner.filter(source)
    assert {hit.pii_type for hit in result.detections} == {'PERSON','EMAIL'}
    mapping = Mapping(('', 'test'),'upgrade',tmp_path)
    existing = mapping.token('PERSON','Anna Beispiel')
    masked = source
    for hit in reversed(result.detections):
        token = mapping.token(hit.pii_type,hit.original)
        masked = masked[:hit.start]+token+masked[hit.end:]
    assert existing in masked
    assert Mapping(('', 'test'),'upgrade',tmp_path).restore(masked) == source

def test_unknown_backend_does_not_silently_enable_processing():
    with pytest.raises(ValueError,match='Unknown'):
        pd.PIIFilter({'backend':'untrusted-engine'})

def test_product_excludes_evaluation_runtime_and_selection():
    root = Path(__file__).parents[1]
    for name in ('helpers/presidio_backend.py','helpers/nym_backend.py','api/presidio_setup.py'):
        assert not (root/name).exists()
    html = (root/'webui/config.html').read_text(encoding='utf-8')
    assert 'local-backend' not in html and 'setupPresidio' not in html
    assert 'spaCy' in html and 'Regex' in html
