"""Verify an optional local Ollama model without sending conversation data."""
import re
from urllib.parse import urlparse

def confirm(base,model,runner=None):
    if re.search(r'[-:]cloud(?:$|[-:])',str(model).casefold()):
        raise ValueError('Ollama cloud models are external. Select an installed local model or an approved Requesty model.')
    import httpx
    url=urlparse(str(base))
    if url.scheme not in {'http','https'} or url.hostname not in {'localhost','127.0.0.1','::1','host.docker.internal','ollama'} or url.username or url.password or url.query or url.fragment:
        raise ValueError('Choose a direct local Ollama endpoint without alternate routing parameters.')
    endpoint=str(base).rstrip('/')
    if endpoint.endswith('/v1'):endpoint=endpoint[:-3]
    body={'model':model}
    if runner:body['runner']=runner
    try:
        with httpx.Client(timeout=5,follow_redirects=False) as client:
            response=client.post(endpoint+'/api/show',json=body)
            if response.status_code!=200 or len(response.content)>4*1024*1024:raise ValueError()
            metadata=response.json()
    except Exception:
        raise ValueError('Local model verification is unavailable. Start the configured local server and install the selected model, or select Requesty.') from None
    if not isinstance(metadata,dict) or metadata.get('remote_host') or metadata.get('remote_model'):
        raise ValueError('This Ollama model forwards requests to another service. Select a local model or an approved Requesty route.')
    if not isinstance(metadata.get('model_info'),dict) or not metadata['model_info']:
        raise ValueError('The selected model has no verifiable local weights. Choose an installed local model.')
    return True
