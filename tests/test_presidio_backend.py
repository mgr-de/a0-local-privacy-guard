import importlib.util
import pytest
from usr.plugins.local_privacy_guard.helpers import presidio_backend as backend
from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter

def test_presidio_rejects_unverified_language():
    with pytest.raises(ValueError,match='only for German and English'):PIIFilter({'backend':'presidio','languages':['pl']})

def test_missing_dependency_never_falls_back(monkeypatch):
    def absent(name):raise backend.PackageNotFoundError(name)
    monkeypatch.setattr(backend,'version',absent)
    with pytest.raises(ValueError,match='unavailable'):PIIFilter({'backend':'presidio','languages':['de']})

def test_wrong_dependency_version_rejected(monkeypatch):
    monkeypatch.setattr(backend,'version',lambda name:'unverified')
    with pytest.raises(ValueError,match='tested Presidio'):PIIFilter({'backend':'presidio','languages':['de']})

@pytest.mark.skipif(importlib.util.find_spec('presidio_analyzer') is None,reason='optional Presidio not installed')
@pytest.mark.parametrize('variant',['A','B'])
def test_optional_backend_shared_regex_and_roundtrip(variant):
    filt=PIIFilter({'backend':'presidio','presidio_variant':variant,'languages':['de'],'store_mapping':False})
    source='Ich bin Anna Weber. Meine E-Mail ist anna@example.com.'
    result=filt.filter(source)
    assert any(h.original=='Anna Weber' and h.pii_type=='PERSON' for h in result.detections)
    assert any(h.original=='anna@example.com' and h.source=='regex' for h in result.detections)
    assert 'Anna Weber' not in result.filtered_text
    second=filt.filter(source)
    assert [(h.start,h.end,h.pii_type) for h in result.detections]==[(h.start,h.end,h.pii_type) for h in second.detections]
