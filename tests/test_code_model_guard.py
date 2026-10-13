"""Persistent mappings and real native wrapper calls with source payloads."""
import ast
import asyncio
import json
import pytest
pytest.importorskip('agent')
from test_model_guard import environment


def test_prior_name_mapping_does_not_rename_source_identifier(environment):
    guard, agent, config = environment
    first = guard.PayloadFilter(agent,config,False)
    first.mapping.token('PERSON','Anna Muster')
    pipeline = guard.PayloadFilter(agent,config,False)
    source = 'class Anna:\n    email = "anna@example.invalid"\n    # Anna Muster\n'
    masked = pipeline.text(source)
    assert 'class Anna:' in masked and 'Anna Muster' not in masked
    assert 'anna@example.invalid' not in masked
    ast.parse(masked)
    assert pipeline.mapping.restore(masked) == source
    assert pipeline.text(masked) == masked


def test_source_payload_retains_native_dispatch_and_serialized_references(environment):
    guard, agent, config = environment
    pipeline = guard.PayloadFilter(agent,config,False)
    source = 'class CustomerService:\n    api_key = os.getenv("API_KEY")\n    email = "anna@example.invalid"\n'
    payload = {'tool_name':'response','tool_args':{'filename':'customer.py','code':source}}
    masked = pipeline.value(payload)
    assert masked['tool_name'] == 'response'
    assert 'class CustomerService:' in masked['tool_args']['code']
    assert 'os.getenv("API_KEY")' in masked['tool_args']['code']
    assert 'anna@example.invalid' not in json.dumps(masked)
    assert pipeline.mapping.restore(masked['tool_args']['code']) == source


def test_native_model_receives_masked_source_and_exact_roundtrip(environment):
    guard, agent, config = environment
    import models
    inner = models.LiteLLMChatWrapper(model='synthetic',provider='openai')
    captured = []
    async def call(system_message='',user_message='',messages=None,**kwargs):
        captured.append(user_message)
        return user_message, ''
    inner.unified_call = call
    data = {'result':inner}
    guard.bind(data,agent)
    source = 'class CustomerService:\n    PORT = 59022\n    email = "anna@example.invalid"\n'
    result = asyncio.run(data['result'].unified_call(user_message=source))
    assert 'class CustomerService:' in captured[0] and 'PORT = 59022' in captured[0]
    assert 'anna@example.invalid' not in captured[0]
    ast.parse(captured[0])
    assert guard.mapping_for(agent).restore(result[0]) == source
