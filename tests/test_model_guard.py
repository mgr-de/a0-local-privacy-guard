"""Actual wrapper transport boundaries, scope persistence and structured payloads."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import AsyncMock
import pytest
pytest.importorskip('agent',reason='Native model and history regressions require Agent Zero 2.13')


@pytest.fixture
def environment(monkeypatch,tmp_path):
    from usr.plugins.local_privacy_guard.helpers import model_guard as guard
    from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
    from agent import Agent,AgentConfig
    agent=Agent(0,AgentConfig(profile="privacy_unit",mcp_servers=""))
    config={"enabled":True,"pii_filter":{"enabled":True,"use_ner":False,"use_regex":True,"action":"redact"}}
    monkeypatch.setattr(guard,"owner_and_config",lambda a:(a,config))
    monkeypatch.setattr(guard,"mapping_for",lambda a:Mapping(("",a.config.profile),a.context.id,tmp_path))
    return guard,agent,config


def test_unique_persistent_mapping_and_foreign_decoder(tmp_path):
    from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
    a=Mapping(("","A"),"chat",tmp_path)
    first=a.token("PERSON","Anna Weber");second=a.token("PERSON","Ben Fischer")
    assert first!=second
    assert Mapping(("","A"),"chat",tmp_path).restore(first+" / "+second)=="Anna Weber / Ben Fischer"
    assert Mapping(("","B"),"chat",tmp_path).restore(first)==first
    assert a.token("PERSON","Anna Weber")==first


def test_ner_cannot_wrap_existing_placeholder(environment,monkeypatch):
    guard,agent,config=environment
    from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIDetection
    pipeline=guard.PayloadFilter(agent,config,False)
    token=pipeline.mapping.token('PERSON','Anna Weber')
    source='Contact '+token+' today'
    monkeypatch.setattr(pipeline.filter,'filter',lambda text:SimpleNamespace(detections=[
        PIIDetection('PERSON',text,0,len(text),'<PERSON>','ner')]))
    assert pipeline.text(source)==source
    assert pipeline.mapping.restore(source)=='Contact Anna Weber today'

def test_complete_known_values_and_tokens_do_not_rerun_detection(environment,monkeypatch):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    token=pipeline.mapping.token('PERSON','Anna Weber')
    def unexpected(text):raise AssertionError('Known complete values must not be detected again')
    monkeypatch.setattr(pipeline.filter,'filter',unexpected)
    assert pipeline.text('Anna Weber')==token or pipeline.mapping.restore(pipeline.text('Anna Weber'))=='Anna Weber'
    assert pipeline.text(token)==token


def test_old_masked_browser_identifier_is_recovered_as_protocol(environment):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    token=pipeline.mapping.token('PERSON','browser')
    result=pipeline.value({'tool_name':token,'tool_args':{'text':'anna@example.com'}})
    assert result['tool_name']=='browser'
    assert 'anna@example.com' not in str(result)


def test_every_text_block_and_system_tool_payload_preserved(environment):
    guard,agent,config=environment
    from langchain_core.messages import HumanMessage,SystemMessage,ToolMessage
    source=[SystemMessage(content="Contact anna@example.com"),HumanMessage(content=[
        {"type":"text","text":"First anna@example.com"},{"type":"text","text":"Second ben@example.com"},
        {"type":"image_url","image_url":{"url":"data:image/png;base64,AA=="}}]),
        ToolMessage(content="Result clara@example.com",tool_call_id="id1")]
    before=deepcopy(source)
    pipeline=guard.PayloadFilter(agent,config,True)
    result=pipeline.value(source)
    assert source==before
    assert all(mail not in str(result) for mail in ("anna@example.com","ben@example.com","clara@example.com"))
    assert result[1].content[2]==source[1].content[2]
    assert len(result[1].content)==3
    assert pipeline.value(result)==result
    assert agent.context.get_data("local_privacy_media") is True


def test_iban_phone_overlap_roundtrip(environment):
    guard,agent,config=environment
    text="Anna: +49 30 55501001; IBAN DE10500105179000000000; anna@example.com"
    pipeline=guard.PayloadFilter(agent,config,False)
    masked=pipeline.text(text)
    assert pipeline.mapping.restore(masked)==text
    assert "DE10500105179000000000" not in masked


@pytest.mark.parametrize("source",[
    'password="LongSyntheticPassword999"', '{"api_key":"LongSyntheticCredential999"}',
    "-----BEGIN PRIVATE KEY-----", "https://account:LongSyntheticPassword999@example.com",
    "ghp_"+"A"*32,
])
def test_secret_blocks_without_exposing_value(environment,source):
    guard,agent,config=environment
    with pytest.raises(ValueError) as error:guard.PayloadFilter(agent,config,False).text(source)
    assert source not in str(error.value)


def test_short_password_and_native_secret_reference(environment):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    with pytest.raises(ValueError):pipeline.text('password="hunter2"')
    reference='api_key=§§secret(MY_API_KEY)'
    assert pipeline.text(reference)==reference


def test_invalid_filter_pattern_stops_payload_processing(environment):
    guard,agent,config=environment
    config['pii_filter']['custom_patterns']=[{'name':'private-example','regex':'['}]
    with pytest.raises(ValueError,match='filter pattern is invalid'):
        guard.PayloadFilter(agent,config,True)


def test_credential_cannot_be_hidden_in_a_sampling_parameter(environment):
    guard,agent,config=environment
    import models
    inner=models.LiteLLMChatWrapper(model='synthetic',provider='openai',api_key='OpaqueManagedCredential999')
    data={'result':inner};guard.bind(data,agent)
    with pytest.raises(ValueError,match='managed credential'):
        asyncio.run(data['result'].unified_call(user_message='Hello',reasoning_effort='OpaqueManagedCredential999'))


def test_custom_rule_name_does_not_become_a_public_placeholder_label(environment):
    guard,agent,config=environment
    config['pii_filter']['custom_patterns']=[{'name':'PRIVATE_PROJECT_LABEL','regex':'internal-example'}]
    pipeline=guard.PayloadFilter(agent,config,False)
    masked=pipeline.text('internal-example')
    assert 'PRIVATE_PROJECT_LABEL' not in masked and '_CUSTOM_' in masked
    assert pipeline.mapping.restore(masked)=='internal-example'


def test_missing_ner_blocks_external_but_local_still_works(environment,monkeypatch):
    guard,agent,config=environment
    config["pii_filter"]["use_ner"]=True
    monkeypatch.setattr(guard.PIIFilter,"get_loaded_languages",lambda self:[])
    with pytest.raises(ValueError,match="Name detection unavailable"):guard.PayloadFilter(agent,config,True)
    guard.PayloadFilter(agent,config,False)


def test_direct_unified_filters_before_inner(environment):
    guard,agent,config=environment
    import models
    from langchain_core.messages import HumanMessage
    inner=models.LiteLLMChatWrapper(model="synthetic",provider="openai")
    captured=[]
    async def reply(*args,**kwargs):
        captured.append((args,kwargs));return "canonical [placeholder]","reasoning"
    inner.unified_call=reply
    # A real method signature is required for positional-argument normalization.
    async def call(system_message="",user_message="",messages=None,**kwargs):
        return await reply(system_message=system_message,user_message=user_message,messages=messages,**kwargs)
    inner.unified_call=call
    data={"result":inner};guard.bind(data,agent)
    wrapper=data["result"]
    result=asyncio.run(wrapper.unified_call("anna@example.com","ben@example.com",messages=[HumanMessage(content="clara@example.com")]))
    assert result==( "canonical [placeholder]","reasoning")
    encoded=str(captured)
    assert all(mail not in encoded for mail in ("anna@example.com","ben@example.com","clara@example.com"))
    assert "[LPG_" in encoded


def test_forwarding_provider_subclass_cannot_bypass_payload_filter(environment):
    guard,agent,config=environment
    import models
    captured=[]
    class Forwarding(models.LiteLLMChatWrapper):
        async def unified_call(self,*args,**kwargs):
            captured.append(kwargs);return "READY",""
    inner=Forwarding(model="synthetic",provider="openai")
    data={"result":inner};guard.bind(data,agent)
    asyncio.run(data['result'].unified_call(user_message="anna@example.com"))
    assert "anna@example.com" not in str(captured)
    assert "[LPG_" in str(captured)


def test_alias_variants_keep_identity_and_exact_spelling(environment):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    main=pipeline.mapping.token('PERSON','David Berger')
    text="David's contact is unchanged. Davids Telefonnummer bleibt gleich."
    masked=pipeline.text(text)
    assert pipeline.mapping.restore(masked)==text
    assert main[:-1]+'_V' in masked
    assert 'David' not in masked


def test_known_first_name_does_not_leave_new_contact_address_or_surname_unmasked(environment,monkeypatch):
    guard,agent,config=environment
    from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIDetection
    pipeline=guard.PayloadFilter(agent,config,False)
    pipeline.mapping.token('PERSON','Anna Weber')
    pipeline.text('Anna')  # Create the persistent short-name variant first.
    source='Anna now uses anna.new@example.com'
    masked=pipeline.text(source)
    assert 'anna.new@example.com' not in masked and '.new@example.com' not in masked
    assert pipeline.mapping.restore(masked)==source
    new_name='Anna Fischer'
    monkeypatch.setattr(pipeline.filter,'filter',lambda text:SimpleNamespace(detections=[
        PIIDetection('PERSON',new_name,0,len(new_name),'<PERSON>','ner')]))
    masked=pipeline.text(new_name)
    assert 'Fischer' not in masked
    assert pipeline.mapping.restore(masked)==new_name


def test_ner_genitive_extension_keeps_known_person_family(environment,monkeypatch):
    guard,agent,config=environment
    from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIDetection
    pipeline=guard.PayloadFilter(agent,config,False)
    main=pipeline.mapping.token('PERSON','David Berger')
    monkeypatch.setattr(pipeline.filter,'filter',lambda text:SimpleNamespace(detections=[
        PIIDetection('PERSON','Davids',0,6,'<PERSON>','ner')]))
    masked=pipeline.text('Davids Schwester')
    assert main[:-1]+'_V' in masked
    assert pipeline.mapping.restore(masked)=='Davids Schwester'


def test_stream_callbacks_receive_only_complete_checked_output(environment):
    guard,agent,config=environment
    import models
    from langchain_core.messages import HumanMessage
    class Streaming(models.LiteLLMChatWrapper):
        async def unified_call(self,*args,**kwargs):
            callback=kwargs['response_callback']
            await callback('anna@','anna@')
            await callback('example.com','anna@example.com')
            await kwargs['tokens_callback']('anna@example.com',5)
            return 'anna@example.com',''
    inner=Streaming(model='synthetic',provider='openai')
    data={'result':inner};guard.bind(data,agent)
    delivered=[]
    counts=[]
    async def callback(delta,full):delivered.append((delta,full))
    async def tokens(delta,count):counts.append((delta,count))
    answer,_=asyncio.run(data['result'].unified_call(messages=[HumanMessage(content='Hello')],response_callback=callback,tokens_callback=tokens))
    assert len(delivered)==1
    assert 'anna@example.com' not in str(delivered)
    assert answer==delivered[0][1]
    assert guard.mapping_for(agent).restore(answer)=='anna@example.com'
    assert counts==[('',5)]


def test_managed_transport_key_is_checked_only_in_content(environment):
    guard,agent,config=environment
    import models
    inner=models.LiteLLMChatWrapper(model='synthetic',provider='openai',api_key='OpaqueManagedCredential999')
    data={'result':inner};guard.bind(data,agent)
    with pytest.raises(ValueError,match='managed credential'):
        asyncio.run(data['result'].unified_call(user_message='OpaqueManagedCredential999'))


def test_preset_tool_and_schema_text_are_filtered(environment):
    guard,agent,config=environment
    import models
    captured=[]
    class Forwarding(models.LiteLLMChatWrapper):
        async def unified_call(self,*args,**kwargs):captured.append(kwargs);return 'READY',''
    inner=Forwarding(model='synthetic',provider='openai',tools=[{'type':'function','function':{
        'name':'contact_lookup','description':'Contact anna@example.com','parameters':{'type':'object','properties':{}}}}],
        response_format={'type':'json_schema','json_schema':{'name':'answer','description':'ben@example.com'}})
    data={'result':inner};guard.bind(data,agent)
    asyncio.run(data['result'].unified_call(user_message='Hello'))
    assert 'anna@example.com' not in str(captured) and 'ben@example.com' not in str(captured)
    assert captured[0]['tools'][0]['function']['name']=='contact_lookup'


def test_langchain_sync_and_async_streams_buffer_output(environment):
    guard,agent,config=environment
    import models
    from langchain_core.messages import HumanMessage,AIMessageChunk
    from langchain_core.outputs import ChatGenerationChunk
    captured=[]
    class Streaming(models.LiteLLMChatWrapper):
        def _call(self,messages,**kwargs):
            captured.append(messages);return 'anna@example.com'
        def _stream(self,messages,**kwargs):
            captured.append(messages)
            for text in ('anna@','example.com'):
                yield ChatGenerationChunk(message=AIMessageChunk(content=text))
        async def _astream(self,messages,**kwargs):
            for chunk in self._stream(messages,**kwargs):yield chunk
    data={'result':Streaming(model='synthetic',provider='openai')};guard.bind(data,agent)
    wrapper=data['result'];messages=[HumanMessage(content='ben@example.com')]
    assert 'anna@example.com' not in wrapper._call(messages)
    chunks=list(wrapper._stream(messages))
    async def collect():return [chunk async for chunk in wrapper._astream(messages)]
    async_chunks=asyncio.run(collect())
    assert len(chunks)==len(async_chunks)==1
    assert 'anna@example.com' not in str(chunks+async_chunks)
    assert 'ben@example.com' not in str(captured)


def test_direct_tool_call_masks_positional_args_and_callbacks(environment):
    guard,agent,config=environment
    import models
    wrapper=models.LiteLLMChatWrapper(model='synthetic',provider='openai')
    delivered=[]
    async def callback(delta,full):delivered.append(full)
    marker=guard.tool_agent.set(agent)
    try:
        data={'args':(wrapper,'anna@example.com','ben@example.com'),
              'kwargs':{'response_callback':callback}}
        guard.filter_native(data)
        assert 'anna@example.com' not in str(data['kwargs'])
        assert 'ben@example.com' not in str(data['kwargs'])
        asyncio.run(data['kwargs']['response_callback']('clara@','clara@'))
        assert not delivered
        data['result']=('clara@example.com','')
        asyncio.run(guard.filter_native_result(data))
        assert len(delivered)==1 and 'clara@example.com' not in delivered[0]
        assert guard.mapping_for(agent).restore(delivered[0])=='clara@example.com'
    finally:guard.tool_agent.reset(marker)


def test_secret_in_file_tool_and_error_text_blocks(environment):
    guard,agent,config=environment
    from langchain_core.messages import ToolMessage,SystemMessage
    secret='ghp_'+'Z'*32
    for message in (ToolMessage(content='File contents: '+secret,tool_call_id='file'),
                    ToolMessage(content='Tool output: '+secret,tool_call_id='tool'),
                    SystemMessage(content='Error text: '+secret)):
        with pytest.raises(ValueError):guard.PayloadFilter(agent,config,True).value([message])


def test_local_gate_delegates_active_requesty_even_with_stale_frontend_hook(environment,monkeypatch):
    guard,agent,config=environment
    from usr.plugins.local_privacy_guard.api.model_status import ModelStatus
    scope=pytest.importorskip('usr.plugins.requesty.helpers.scope')
    from usr.plugins.requesty.api.model_status import ModelConfigGet
    setup={'active':True,'models':{'chat':{'provider':'requesty_guarded','name':'synthetic/approved'},
                                  'utility':{'provider':'requesty_guarded','name':'synthetic/utility'}}}
    monkeypatch.setattr(scope,'read',lambda *a,**kw:setup)
    monkeypatch.setattr(scope,'enabled',lambda *a:True)
    monkeypatch.setattr(scope,'key',lambda *a:'synthetic-hidden-key')
    monkeypatch.setattr(ModelConfigGet,'process',AsyncMock(return_value={'config':{},'model_configured':False}))
    result=asyncio.run(ModelStatus(None,None).process({'context_id':agent.context.id},None))
    assert result['model_configured'] is True
    assert result['config']['chat_model']['name']=='synthetic/approved'
    assert 'synthetic-hidden-key' not in str(result)


def test_native_separate_subordinate_uses_parent_filter_and_mapping(monkeypatch,tmp_path):
    from agent import Agent,AgentConfig
    from usr.plugins.local_privacy_guard.helpers import model_guard as guard,agent_scope
    parent=Agent(0,AgentConfig(profile='parent-A',mcp_servers=''))
    child=Agent(1,AgentConfig(profile='child-B',mcp_servers=''))
    child.context.set_output_data('parent_context_id',parent.context.id)
    def path(project,profile):return tmp_path/(profile+'.json')
    path('','parent-A').write_text(json.dumps({'enabled':True,'pii_filter':{'enabled':True}}))
    path('','child-B').write_text(json.dumps({'enabled':False}))
    monkeypatch.setattr(agent_scope,'selected_path',path)
    assert agent_scope.configuration(child)['enabled'] is True
    assert guard.owning_agent(child) is parent
    assert guard.mapping_for(child).namespace==guard.mapping_for(parent).namespace
    independent=Agent(0,AgentConfig(profile='child-B',mcp_servers=''))
    assert agent_scope.configuration(independent)['enabled'] is False
    child.context.set_output_data('parent_context_id','unavailable-parent')
    with pytest.raises(ValueError,match='parent privacy context'):agent_scope.configuration(child)


def test_canonical_history_hook_masks_user_and_tool_contents(environment):
    guard,agent,config=environment
    from usr.plugins.local_privacy_guard.extensions.python.hist_add_before._99_canonical_privacy_history import CanonicalPrivacyHistory
    hook=CanonicalPrivacyHistory(agent)
    original='Contact anna@example.com'
    data={'content':original}
    hook.execute(data,ai=False)
    assert 'anna@example.com' not in str(data)
    assert guard.mapping_for(agent).restore(data['content'])==original
    tool={'content':{'tool':'browser','result':'Contact ben@example.com'}}
    hook.execute(tool,ai=False)
    assert 'ben@example.com' not in str(tool)


def test_fenced_json_and_dynamic_contact_keys_are_masked_without_schema_damage(environment):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    data={'married':False,'partners':True,'debt_eur':125,'siblings':True,
          'anna@example.com':'ben@example.com'}
    result=pipeline.text('```json\n'+json.dumps(data)+'\n```')
    parsed=json.loads(result.split('\n',1)[1].rsplit('\n',1)[0])
    assert parsed['married'] is False and parsed['debt_eur']==125
    assert 'anna@example.com' not in result and 'ben@example.com' not in result


def test_credentials_in_media_urls_are_blocked_without_claiming_pixel_scanning(environment):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,True)
    with pytest.raises(ValueError):pipeline.value({'type':'image_url','image_url':{
        'url':'https://account:LongSyntheticPassword999@example.com/photo.png'}})
    original={'type':'image_url','image_url':{'url':'data:image/png;base64,AA=='}}
    assert pipeline.value(original)==original


@pytest.fixture
def native_test_profiles(monkeypatch,tmp_path):
    from tempfile import TemporaryDirectory
    from helpers import files
    from usr.plugins.local_privacy_guard.helpers import model_guard
    root=Path(files.get_abs_path('usr','agents'))
    root.mkdir(parents=True,exist_ok=True)
    mapping=model_guard.Mapping
    monkeypatch.setattr(model_guard,'Mapping',lambda owner,chat:mapping(owner,chat,root=tmp_path/'mappings'))
    with TemporaryDirectory(prefix='privacy-unit-parent-',dir=root) as parent, TemporaryDirectory(prefix='privacy-unit-child-',dir=root) as child:
        yield Path(parent).name,Path(child).name


def test_native_disabled_child_plugins_still_enforce_parent_without_changing_independent_chat(monkeypatch,native_test_profiles):
    from agent import Agent,AgentConfig
    from helpers import plugins,extension,cache
    from usr.plugins.local_privacy_guard.helpers import inherited_bridge as local_bridge
    requesty_bridge=pytest.importorskip('usr.plugins.requesty.helpers.inherited_bridge')
    from usr.plugins.requesty.helpers import scope
    from usr.plugins.requesty.helpers.policy import PolicyError
    from usr.plugins.local_privacy_guard.helpers.model_guard import PrivacyWrapper
    parent_profile,child_profile=native_test_profiles
    for name in ('requesty','local_privacy_guard'):
        plugins.toggle_plugin(name,True,agent_profile=parent_profile)
        plugins.toggle_plugin(name,False,agent_profile=child_profile)
    config={'enabled':True,'pii_filter':{'enabled':True,'use_ner':False,'use_regex':True},
            'local_embedding':{'enabled':False},'verification':{'enabled':False}}
    plugins.save_plugin_config('local_privacy_guard','',parent_profile,config)
    setup={'active':True,'models':{'chat':{'provider':'requesty_guarded','name':'synthetic/eu'},
                                  'utility':{'provider':'requesty_guarded','name':'synthetic/eu'}}}
    monkeypatch.setattr(scope,'read',lambda identity,name,default=None:setup if name=='setup.json' and identity[1]==parent_profile else {})
    monkeypatch.setattr(scope,'key',lambda identity:'synthetic-owned-key')
    local_bridge.manage(Path(local_bridge.__file__).parents[1])
    requesty_bridge.manage(Path(requesty_bridge.__file__).parents[1])
    cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)
    parent=Agent(0,AgentConfig(profile=parent_profile,mcp_servers=''))
    child=Agent(1,AgentConfig(profile=child_profile,mcp_servers=''))
    child.context.set_output_data('parent_context_id',parent.context.id)
    assert 'requesty' not in plugins.get_enabled_plugins(child)
    wrapper=child.get_chat_model()
    assert isinstance(wrapper,PrivacyWrapper)
    assert wrapper._privacy_inner._requesty_scope==('',parent_profile)
    msg=child.hist_add_message(False,'Contact anna@example.com')
    assert 'anna@example.com' not in str(msg.content)
    with pytest.raises(ValueError,match='credential'):
        asyncio.run(wrapper.unified_call(user_message='password="LongSyntheticPassword999"'))
    independent=Agent(0,AgentConfig(profile=child_profile,mcp_servers=''))
    assert not isinstance(independent.get_chat_model(),PrivacyWrapper)
    import models
    direct=models.LiteLLMChatWrapper(model='synthetic',provider='openai',
        model_config=models.ModelConfig(type=models.ModelType.CHAT,provider='openrouter',name='synthetic'))
    async def direct_tool_call():
        await extension.call_extensions_async('tool_execute_before',child,tool_name='vision_load',tool_args={})
        try:
            with pytest.raises(PolicyError,match='bypasses Requesty'):
                await direct.unified_call(user_message='anna@example.com')
        finally:await extension.call_extensions_async('tool_execute_after',child)
    asyncio.run(direct_tool_call())
    # Instance-level discovery can be off while the parent profile is enabled.
    # The owned native adapters must still filter direct tool-model payloads.
    from helpers import litellm_transport
    from litellm import ModelResponse
    real_enabled=plugins.get_enabled_plugins;captured=[]
    async def transport(**kwargs):
        captured.append(kwargs.get('messages'))
        return ModelResponse(choices=[{'message':{'role':'assistant','content':'clara@example.com'},'finish_reason':'stop'}])
    with monkeypatch.context() as limited:
        limited.setattr(plugins,'get_enabled_plugins',lambda a:[name for name in real_enabled(a)
            if a is not None or name not in {'requesty','local_privacy_guard'}])
        limited.setattr(litellm_transport,'acompletion',transport)
        cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)
        local=models.LiteLLMChatWrapper(model='synthetic',provider='openai',
            model_config=models.ModelConfig(type=models.ModelType.CHAT,provider='openai',name='synthetic'),
            api_base='http://host.docker.internal:8080/v1')
        async def local_tool_call():
            await extension.call_extensions_async('tool_execute_before',child,tool_name='vision_load',tool_args={})
            try:return await local.unified_call(user_message='anna@example.com')
            finally:await extension.call_extensions_async('tool_execute_after',child)
        result=asyncio.run(local_tool_call())
        assert 'anna@example.com' not in str(captured)
        assert 'clara@example.com' not in str(result)
        assert getattr(local,'_requesty_scope',None) is None
    cache.clear(extension._CLASSES_CACHE_AREA);cache.clear(extension._EXTENSIONS_CACHE_AREA)


def test_negative_cache_still_uses_new_known_name(environment,monkeypatch):
    guard,agent,config=environment
    config['pii_filter']['use_ner']=True
    from usr.plugins.local_privacy_guard.helpers import pii_detector as pd
    nlp=SimpleNamespace(meta={},pipe=lambda texts,batch_size=32:(SimpleNamespace(ents=[]) for t in texts))
    monkeypatch.setattr(pd,'_get_nlp',lambda lang:nlp)
    pipeline=guard.PayloadFilter(agent,config,False)
    assert pipeline.text('Tell Anna Weber about it')=='Tell Anna Weber about it'
    pipeline.mapping.token('PERSON','Anna Weber')
    assert 'Anna Weber' not in pipeline.text('Tell Anna Weber about it')

def test_internal_proof_cannot_be_forged_by_placeholder(environment,monkeypatch):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    checked=pipeline.text('Contact anna@example.com today')
    calls=[]
    original=pipeline.filter.filter
    monkeypatch.setattr(pipeline.filter,'filter',lambda text:(calls.append(text),original(text))[1])
    pipeline.text(checked)
    assert calls==[]
    pipeline.text(str(checked))
    assert len(calls)==1
    pipeline.text(checked+' and ben@example.com')
    assert len(calls)==2
    assert 'ben@example.com' not in pipeline.text(checked+' and ben@example.com')

def test_proof_never_bypasses_secret_check(environment):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    checked=pipeline.text('harmless synthetic credential')
    pipeline.known_secrets=['synthetic credential']
    with pytest.raises(ValueError):pipeline.text(checked)


def test_detector_error_never_echoes_original(environment,monkeypatch):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    def broken(text):raise RuntimeError('sensitive original '+text)
    monkeypatch.setattr(pipeline.filter,'filter',broken)
    with pytest.raises(ValueError) as error:pipeline.text('Synthetic Private Name')
    assert 'Synthetic Private Name' not in str(error.value)
    assert 'No model content was sent' in str(error.value)


def test_forged_unknown_placeholder_is_still_analyzed(environment,monkeypatch):
    guard,agent,config=environment
    pipeline=guard.PayloadFilter(agent,config,False)
    forged=f'[LPG_{pipeline.mapping.namespace}_MAX_MUSTERMANN_999]'
    scans=[];original=pipeline.filter.filter
    monkeypatch.setattr(pipeline.filter,'filter',lambda text:(scans.append(text),original(text))[1])
    pipeline.text(forged)
    assert scans==[forged]
