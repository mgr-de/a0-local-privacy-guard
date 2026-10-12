import importlib.util,json
from pathlib import Path
import pytest

def load():
    path=Path(__file__).parents[1]/'helpers/local_models.py'
    spec=importlib.util.spec_from_file_location('local_models_tested',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def respond(monkeypatch,metadata,status=200):
    import httpx
    class Client:
        def __enter__(self):return self
        def __exit__(self,*unused):pass
        def post(self,url,json):
            return httpx.Response(status,json=metadata)
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:Client())

def test_local_weights_are_confirmed_without_conversation_data(monkeypatch):
    module=load();respond(monkeypatch,{'model_info':{'general.architecture':'synthetic'}})
    assert module.confirm('http://localhost:11434','synthetic:latest')

@pytest.mark.parametrize('metadata',[{'remote_host':'https://ollama.com','model_info':{'fake':True}},
    {'remote_model':'hosted-model','model_info':{'fake':True}},{}])
def test_remote_alias_or_unknown_locality_is_rejected(monkeypatch,metadata):
    module=load();respond(monkeypatch,metadata)
    with pytest.raises(ValueError):module.confirm('http://localhost:11434','innocent-local-alias')

def test_cloud_tag_is_rejected_before_metadata_request(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:pytest.fail('Cloud tag must not query the server'))
    with pytest.raises(ValueError,match='cloud models are external'):load().confirm('http://localhost:11434','large:cloud')

def test_unavailable_local_server_does_not_become_verified(monkeypatch):
    module=load();respond(monkeypatch,{},404)
    with pytest.raises(ValueError,match='verification is unavailable'):module.confirm('http://localhost:11434','missing-model')
