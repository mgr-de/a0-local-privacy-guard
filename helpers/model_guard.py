"""Bind a guarded instance to every native model getter, including Vision.

Copy payloads before masking; canonical model outputs stay masked. The wrapper
delegates to the original provider wrapper, retaining Requesty's live checks.
"""
from copy import deepcopy
import inspect
import time
from usr.plugins.local_privacy_guard.helpers.detection_cache import fingerprint, configuration, spans
import re
import weakref
import json
from pathlib import Path
from urllib.parse import urlparse
from pydantic import PrivateAttr
from contextvars import ContextVar
from models import LiteLLMChatWrapper
from usr.plugins.local_privacy_guard.helpers import agent_scope
from usr.plugins.local_privacy_guard.helpers.mapping import Mapping, TOKEN
from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter, PIIDetection, UNIVERSAL_PATTERNS, LANGUAGE_PATTERNS, LABEL_MAPS
from usr.plugins.local_privacy_guard.helpers.secrets import check
from usr.plugins.local_privacy_guard.helpers.code_regions import analysis_text, POLICY_VERSION

tool_agent = ContextVar("local_privacy_tool_agent", default=None)
filtered_call = ContextVar('local_privacy_filtered_call',default=None)
INSTANCE_API_VERSION=2
CONTENT_OPTIONS=('tools','response_format','a0_responses_function_tools','responses_input_items',
                 'responses_local_input_items','responses_prompt_replacements')
SAFE_KINDS=set(UNIVERSAL_PATTERNS)|{key for patterns in LANGUAGE_PATTERNS.values() for key in patterns}|{
    kind for mapping in LABEL_MAPS.values() for kind in mapping.values()}|{'CUSTOM','MISC','CARDINAL','MONEY'}


def owning_agent(agent):
    from agent import AgentContext
    seen=set()
    current=agent
    while True:
        if current.context.id in seen:
            raise ValueError('Cyclic subordinate privacy context.')
        seen.add(current.context.id)
        parent_id=current.context.get_output_data('parent_context_id')
        if not parent_id:break
        parent=AgentContext.get(parent_id)
        if parent is None or parent.agent0 is None:
            raise ValueError('The parent privacy context is unavailable. Restore the parent chat before continuing this subordinate.')
        current=parent.agent0
    if current is not agent and agent_scope.configuration(current):
        config=agent_scope.configuration(current)
        if config.get('enabled'):return current
    root = getattr(agent.context, "agent0", None)
    if root is not None:
        cfg = agent_scope.configuration(root)
        if cfg and cfg.get("enabled"):
            return root
    return agent


def owner_and_config(agent):
    from helpers import projects, plugins
    owner = owning_agent(agent)
    from usr.plugins.local_privacy_guard.helpers.instance import manager
    instance=manager()
    if instance is not None:return owner,instance.local_config(owner)
    if owner.context.get_data('privacy_agent_chat_policy') is not None:
        raise ValueError('Restore central privacy protection before continuing this Developer chat.')
    if not (Path(__file__).parents[1]/'plugin.yaml').is_file() or 'local_privacy_guard' not in plugins.get_enabled_plugins(owner):
        return owner,None
    cfg = agent_scope.configuration(owner)
    if not cfg or not cfg.get("enabled") or plugins.get_plugin_config("local_privacy_guard", owner).get("enabled") is not True:
        return owner, None
    return owner, cfg


def mapping_for(agent):
    from helpers import projects
    owner = owning_agent(agent)
    from usr.plugins.local_privacy_guard.helpers.instance import manager
    instance=manager()
    identity=instance.mapping_identity(owner) if instance is not None else (projects.get_context_project_name(owner.context) or "", owner.config.profile)
    return Mapping(identity, owner.context.id)


def is_local(wrapper, overrides=None):
    options = {**wrapper.kwargs, **(overrides or {})}
    base = options.get("api_base") or getattr(wrapper.a0_model_conf, "api_base", "")
    url = urlparse(str(base))
    secondary={'base_url','api_url','custom_llm_provider','fallbacks','context_window_fallbacks',
               'model_list','router','client','aclient','http_client','extra_body','extra_headers','headers','proxy'}
    return not secondary.intersection(options) and not url.username and not url.password and url.scheme in {"http", "https"} and url.hostname in {
        "localhost", "127.0.0.1", "::1", "host.docker.internal"
    }


def route_host(value):
    parsed=urlparse(str(value))
    try:port=parsed.port
    except ValueError:port=None
    return (parsed.hostname or "") + (":"+str(port) if port else "")


def include_transport_credentials(pipeline,wrapper,overrides=None):
    for key in ("api_key","azure_ad_token"):
        value=(overrides or {}).get(key) or wrapper.kwargs.get(key) or getattr(wrapper.a0_model_conf,key,"")
        if isinstance(value,str) and len(value)>=4 and value not in {"None","NA"}:
            pipeline.known_secrets.append(value)

def inspect_control_options(pipeline,options):
    # Authentication belongs to the transport. Other request parameters must
    # not become a second channel for accidentally pasted credentials.
    transport={'api_key','azure_ad_token','api_base','base_url','headers','extra_headers','client','aclient','http_client'}
    for key,value in options.items():
        if key not in transport:
            check(json.dumps({key:value},ensure_ascii=False,default=str),pipeline.known_secrets)


_seal=object()
class _CheckedText(str):
    """Only internally produced strings carry proof; serialization removes it."""
    def __new__(cls,value,scope,signature):
        obj=str.__new__(cls,value)
        obj._proof=(_seal,scope,signature,fingerprint(value))
        return obj
    def __getnewargs__(self):return (str(self),self._proof[1],self._proof[2])

class PayloadFilter:
    def __init__(self, agent, config, external, *, _mapping=None):
        self.agent = agent
        self.config = deepcopy(config)
        self.external = external
        self.settings = config.get("pii_filter", {})
        if self.settings.get('action','redact') not in {'redact','block','log_only'}:
            raise ValueError('Invalid text filter action. Choose replacement, blocking or logging only in privacy settings.')
        self.detected_count=0
        self.started=time.perf_counter()
        if _mapping is not None:
            self.mapping=_mapping
        elif self.settings.get('enabled',True):
            self.mapping = mapping_for(agent)
        else:
            # Do not read historical mappings for a Secret-only call.
            class NoMapping:
                namespace=configuration({'chat':agent.context.id,'policy':config.get('_privacy_policy',{})})[:16]
                metrics={'database_seconds':0,'sql_statements':0}
                def snapshot(self):return (0,[])
            self.mapping = NoMapping()
        self.snapshot = self.mapping.snapshot()
        detector_settings=dict(self.settings if self.settings.get('enabled',True) else {'use_regex':False,'use_ner':False})
        detector_settings['_cache_scope']=self.mapping.namespace
        self.filter = PIIFilter(detector_settings)
        self._patterns={}
        self.blocks=0
        if external and self.settings.get("enabled", True) and self.settings.get("use_ner", True):
            missing = set(self.filter.ner_languages) - set(self.filter.get_loaded_languages())
            if missing:
                raise ValueError("Name detection unavailable for " + ", ".join(sorted(missing)) + ". Install the selected spaCy models in Agent Zero's Python environment or select local processing.")
        from usr.plugins.local_privacy_guard.helpers import pii_detector
        model_identity={}
        if self.filter.use_ner:
            for language in self.filter.ner_languages:
                model=pii_detector._get_nlp(language)
                model_identity[language]={'identity':id(model),'meta':getattr(model,'meta',{})}
        self.signature=configuration({'settings':self.settings,'models':model_identity,'cache_generation':spans.generation,'code_policy':POLICY_VERSION})
        self.known_secrets = []
        try:
            from usr.plugins.requesty.helpers import scope
            self.known_secrets = [scope.key(scope.from_agent(agent))]
        except (ImportError, ValueError):
            pass

    def for_output(self):
        # Refresh known input tokens while retaining the admitted PII mode.
        result=PayloadFilter(self.agent,self.config,False,_mapping=self.mapping)
        result.known_secrets=list(dict.fromkeys([*self.known_secrets,*result.known_secrets]))
        return result

    def log_summary(self,phase):
        if not self.settings.get('log_detections',False):return
        action=self.settings.get('action','redact')
        description='detected; contents unchanged' if action=='log_only' else 'masked locally'
        self.agent.context.log.log(type='info',heading='Local Privacy Guard',
            content=f'{phase}: {self.detected_count} replacements across the full model context ({description}); repeated occurrences are counted. Preparation {time.perf_counter()-self.started:.3f}s; NER {self.filter.metrics["ner_seconds"]:.3f}s, regex {self.filter.metrics["regex_seconds"]:.3f}s; cached units {self.filter.metrics["cache_hits"]}, new units {self.filter.metrics["ner_units"]}; database {self.mapping.metrics["database_seconds"]:.3f}s / {self.mapping.metrics["sql_statements"]} statements; {self.blocks} text blocks. Detection can miss details.')

    def text(self, text, *, code_hint=''):
        self.blocks+=1
        check(text, self.known_secrets)
        trusted=isinstance(text,_CheckedText) and getattr(text,'_proof',None)==(_seal,self.mapping.namespace,self.signature,fingerprint(text))
        if not self.settings.get("enabled", True):
            return text
        fenced=re.fullmatch(r'(\s*```(?:json)?\s*\n)(.*?)(\n```\s*)',text,re.DOTALL)
        if fenced:
            try:structured=json.loads(fenced[2])
            except ValueError:structured=None
            if isinstance(structured,(dict,list)):
                return fenced[1]+json.dumps(self.value(structured,_data=True),ensure_ascii=False)+fenced[3]
        # Preserve the native JSON tool envelope; inspect its payload fields.
        try:
            structured=json.loads(text)
        except (ValueError,TypeError):structured=None
        if isinstance(structured,(dict,list)):
            return json.dumps(self.value(structured,_data=True),ensure_ascii=False)
        # Exclude existing tokens from detection; keep offsets unchanged.
        registered={token for token,_,_ in self.snapshot[1]}
        existing=[match for match in TOKEN.finditer(text) if match.group() in registered]
        scan = TOKEN.sub(lambda m: " "*len(m.group()) if m.group() in registered else m.group(),text)
        if not scan.strip():return text
        known_scan = analysis_text(scan, code_hint)
        known = []
        entries = self.snapshot[1]
        aliases = {}
        for token, kind, original in entries:
            if self.filter.is_non_entity(original):
                continue
            values = [original]
            words=original.split()
            if kind == "PERSON" and len(words) > 1 and all(word[:1].isupper() for word in words) and words[0].casefold() not in self.filter.skip_words and words[0].casefold() not in {
                "the","this","that","your","you","use","return","der","die","das","ein","eine","dein","deine"
            }:
                family=re.sub(r"_V\d+(?=\])", "", token)
                aliases.setdefault(original.split()[0].casefold(), []).append((family, original))
            for value in values:
                pattern=self._patterns.get(value)
                if pattern is None:
                    pattern=re.compile(r"(?<!\w)"+re.escape(value)+r"(?!\w)",re.IGNORECASE);self._patterns[value]=pattern
                for match in pattern.finditer(known_scan):
                    if scan[match.start():match.end()] == match.group():
                        known.append(PIIDetection(kind, match.group(), match.start(), match.end(), token, "known"))
        for alias, people in aliases.items():
            if len(set(token for token, _ in people)) == 1:
                for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?=\b|'s\b|’s\b|s\b)", known_scan, re.IGNORECASE):
                    if scan[match.start():match.end()] == match.group():
                        known.append(PIIDetection("PERSON", match.group(), match.start(), match.end(), people[0][0], "known"))
        # A complete known value cannot contain a larger new overlapping
        # identity. Reuse its mapping instead of rerunning NER on every repeat.
        complete_known=any(hit.start==0 and hit.end==len(scan) for hit in known)
        try:
            detected = [] if complete_known or trusted else (
                self.filter.filter(scan, code_hint=code_hint) if code_hint else self.filter.filter(scan)).detections
        except Exception:
            raise ValueError('Local text detection failed. No model content was sent. Check the selected engine and installed models.') from None
        def larger_complete_value(detection,known_hit):
            if detection.start>known_hit.start or detection.end<known_hit.end or detection.end-detection.start<=known_hit.end-known_hit.start:
                return False
            if detection.source=='regex':return True
            if detection.pii_type=='PERSON' and known_hit.pii_type=='PERSON' and detection.start==known_hit.start and detection.original.casefold() in {
                known_hit.original.casefold()+suffix for suffix in ('s',"'s",'’s')
            }:return False  # Possessive/genitive keeps the known identity.
            if detection.pii_type=='DATUM' and known_hit.pii_type=='DATUM':return True
            if detection.pii_type in {'PERSON','ORGANISATION','ORT'}:
                words=detection.original.split()
                if any(word.casefold() in {'and','und','with','mit','is','ist','et','y'} for word in words):return False
                return len(known_hit.original.split())==1 or all(word[:1].isupper() for word in words)
            return False
        # A known first name must not mask only the prefix of a NEW email or
        # full name. Whole recognized values take precedence over such hits.
        known=[hit for hit in known if not any(larger_complete_value(detection,hit) for detection in detected)]
        selected = []
        for hit in sorted(known + detected, key=lambda h: (h.source != "known", -(h.end-h.start), h.start)):
            if any(hit.start < token.end() and token.start() < hit.end for token in existing):
                continue
            if not any(hit.start < x.end and x.start < hit.end for x in selected):
                selected.append(hit)
        action = self.settings.get("action", "redact")
        self.detected_count+=len(selected)
        if action == "block" and selected:
            raise ValueError("Local Privacy Guard blocked a model request containing personal details.")
        if action == "log_only":
            return text
        ordered=sorted(selected,key=lambda h:h.start,reverse=True)
        requests=[(h.pii_type if h.pii_type in SAFE_KINDS else 'CUSTOM',text[h.start:h.end],h.replacement if h.source=='known' else None) for h in ordered]
        lookup={(kind,original):token for token,kind,original in self.snapshot[1]}
        missing=list(dict.fromkeys(r for r in requests if (r[0],r[1]) not in lookup))
        if missing:
            for request,token in zip(missing,self.mapping.token_many(missing),strict=True):lookup[request[:2]]=token
        for hit,request in zip(ordered,requests,strict=True):
            text=text[:hit.start]+lookup[request[:2]]+text[hit.end:]
        return _CheckedText(text,self.mapping.namespace,self.signature)

    def _native_tool_id(self,value):
        if not isinstance(value,str) or not re.fullmatch(r'[a-z][a-z0-9_]*',value):return False
        try:
            from helpers import subagents
            return bool(subagents.get_paths(self.agent,'tools',value+'.py'))
        except (ImportError,AttributeError,ValueError):return False

    def value(self, value, *, _data=False, code_hint=''):
        if isinstance(value, str):
            return self.text(value, code_hint=code_hint)
        if isinstance(value, list):
            return [self.value(part,_data=_data,code_hint=code_hint) for part in value]
        if isinstance(value, dict):
            kind = value.get("type", "")
            # Never pretend that image bytes/URLs were protected by text scanning.
            if not _data and kind in {"image_url", "input_image", "image", "file", "input_file"}:
                def scan_media_urls(item):
                    if isinstance(item,str) and not item.startswith('data:'):
                        check(item,self.known_secrets)
                    elif isinstance(item,dict):
                        for part in item.values():scan_media_urls(part)
                    elif isinstance(item,list):
                        for part in item:scan_media_urls(part)
                scan_media_urls(value)
                if self.external:
                    self.agent.context.set_data("local_privacy_media", True)
                    self.agent.context.set_data("local_privacy_media_route", self.agent.context.get_data("local_privacy_route"))
                return deepcopy(value)
            check(json.dumps(value, ensure_ascii=False, default=str), self.known_secrets)
            identifiers={"type","role","id","tool_call_id","tool_name"}
            if value.get("type") in {"function","function_call"} or "parameters" in value:
                identifiers.add("name")
            # Protocol privileges come from the adapter, never from JSON
            # entered as text. Only registered tool IDs retain routing semantics.
            result={}
            from usr.plugins.local_privacy_guard.helpers.code_regions import PYTHON, JAVASCRIPT, SUFFIXES
            hint = code_hint
            for field in ('language', 'filename', 'file_path', 'path'):
                candidate = value.get(field)
                if isinstance(candidate, str) and (candidate.lower() in PYTHON | JAVASCRIPT or any(candidate.lower().endswith(suffix) for suffix in SUFFIXES)):
                    hint = candidate
                    break
            for key,item in value.items():
                safe_key=key if not isinstance(key,str) or re.fullmatch(r'[a-z_][A-Za-z0-9_]*',key) else self.text(key)
                if (not _data and key in identifiers) or (key=='tool_name' and self._native_tool_id(item)):
                    result[safe_key]=deepcopy(item)
                else:
                    result[safe_key]=self.value(item,_data=_data or key in {'args','arguments','output'},
                        code_hint=hint if key in {'code','source','content','text'} else '')
            if self.settings.get('enabled',True) and isinstance(result.get('tool_name'),str):
                candidate=self.mapping.restore(result['tool_name'])
                if self._native_tool_id(candidate):result['tool_name']=candidate
            return result
        if hasattr(value, "content"):
            result = deepcopy(value)
            result.content = self.value(value.content)
            if getattr(value, "tool_calls", None):
                result.tool_calls = self.value(value.tool_calls)
            if getattr(value, "additional_kwargs", None):
                result.additional_kwargs = self.value(value.additional_kwargs)
            if getattr(value, "response_metadata", None):
                result.response_metadata = self.value(value.response_metadata)
            return result
        return deepcopy(value)


def prepare(wrapper, args, kwargs, method, *, _with_pipeline=False):
    agent = wrapper._privacy_agent()
    if agent is None:
        raise ValueError("The privacy owner is unavailable; rebuild the model.")
    owner, config = owner_and_config(agent)
    if config is None:
        raise ValueError("Privacy configuration changed; rebuild the model before continuing.")
    pipeline = PayloadFilter(owner, config, external=not is_local(wrapper._privacy_inner, kwargs))
    include_transport_credentials(pipeline,wrapper._privacy_inner,kwargs)
    check(wrapper.model_name,pipeline.known_secrets)
    inspect_control_options(pipeline,{**wrapper._privacy_inner.kwargs,**kwargs})
    owner.context.set_data("local_privacy_route", {"model":wrapper.model_name, "local":is_local(wrapper._privacy_inner, kwargs),
        "endpoint":route_host(wrapper.kwargs.get("api_base", ""))})
    if method in {"unified_call", "unified_turn"}:
        # Provider subclasses may expose only *args/**kwargs. Normalize against
        # the native public contract, not their forwarding method signature.
        signature = inspect.signature(getattr(LiteLLMChatWrapper, method))
        bound = signature.bind_partial(wrapper._privacy_inner, *args, **kwargs)
        for key in ("system_message", "user_message", "messages"):
            if key in bound.arguments:
                bound.arguments[key] = pipeline.value(bound.arguments[key])
        messages=bound.arguments.get("messages")
        if pipeline.settings.get('enabled',True) and messages and any("_V" in token for token,_,_ in pipeline.snapshot[1]):
            from langchain_core.messages import SystemMessage
            messages.insert(0,SystemMessage(content="Privacy placeholder tokens sharing a namespace, type and numeric ID denote the same identity. A trailing _V number only preserves a spelling or short-name variant. Preserve exact tokens in replies."))
        extras = bound.arguments.get("kwargs", {})
        for key in CONTENT_OPTIONS:
            if key in extras or key in wrapper._privacy_inner.kwargs:
                extras[key] = pipeline.value(extras.get(key,wrapper._privacy_inner.kwargs.get(key)))
        # Normalize positional callbacks too, so buffering cannot be bypassed.
        normalized={k:v for k,v in bound.arguments.items() if k not in {"kwargs","self"}}
        pipeline.log_summary('Model input')
        result=((), {**extras,**normalized})
        return (*result,pipeline,config) if _with_pipeline else result
    copied = dict(kwargs)
    for key in CONTENT_OPTIONS:
        if key in copied or key in wrapper._privacy_inner.kwargs:
            copied[key]=pipeline.value(copied.get(key,wrapper._privacy_inner.kwargs.get(key)))
    messages=pipeline.value(args[0]);pipeline.log_summary('Model input')
    result=((messages, *args[1:]), copied)
    return (*result,pipeline,config) if _with_pipeline else result


class PrivacyWrapper(LiteLLMChatWrapper):
    _privacy_inner: object = PrivateAttr()
    _privacy_agent: object = PrivateAttr()

    def output_filter(self):
        agent=self._privacy_agent()
        if agent is None:raise ValueError("The privacy owner is unavailable.")
        owner,config=owner_and_config(agent)
        if config is None:raise ValueError("Privacy configuration changed during the model call.")
        pipeline=PayloadFilter(owner,config,False)
        include_transport_credentials(pipeline,self._privacy_inner)
        return pipeline

    async def buffered_call(self, method, args, kwargs):
        agent=self._privacy_agent()
        progress=None
        def status(message):
            nonlocal progress
            if agent is None:return
            if progress is None:progress=agent.context.log.log(type='info',heading='Local Privacy Guard',content=message)
            elif hasattr(progress,'update'):progress.update(content=message)
        status('Checking model input locally.')
        args, kwargs, pipeline, config = prepare(self, args, kwargs, method,_with_pipeline=True)
        from usr.plugins.local_privacy_guard.helpers import transport_admission
        transport_admission.install()
        admission=transport_admission.receipt.set(transport_admission.capture(pipeline.agent,config))
        status('Input checked. The selected model is processing the request.')
        model_started=time.perf_counter()
        callbacks={key:kwargs.get(key) for key in ("response_callback","reasoning_callback")}
        async def buffer(*unused):return None
        # Avoid committing partial original values or broken tokens to logs.
        # Token-count callbacks remain intact; display receives one checked batch.
        for key,callback in callbacks.items():
            if callback:kwargs[key]=buffer
        tokens_callback=kwargs.get('tokens_callback')
        if tokens_callback:
            async def count_only(delta,count):return await tokens_callback('',count)
            kwargs['tokens_callback']=count_only
        marker=filtered_call.set((self._privacy_inner,self._privacy_agent()))
        try:result=await getattr(self._privacy_inner,method)(*args,**kwargs)
        finally:
            filtered_call.reset(marker)
            transport_admission.receipt.reset(admission)
        model_seconds=time.perf_counter()-model_started
        status(f'Model processing finished ({model_seconds:.3f}s). Checking the response locally.')
        # An admitted request keeps its original mode even after a revocation.
        pipeline=pipeline.for_output()
        if method=="unified_call":
            response,reasoning=result
            response,reasoning=pipeline.text(response),pipeline.text(reasoning)
            result=(response,reasoning)
        else:
            result=deepcopy(result)
            result.response=pipeline.text(result.response);result.reasoning=pipeline.text(result.reasoning)
            result.input_items=pipeline.value(result.input_items)
            for item in result.output_items:item.data=pipeline.value(item.data)
            result.raw=pipeline.value(result.raw)
            response,reasoning=result.response,result.reasoning
        pipeline.log_summary('Model output')
        status(f'Input and response checked locally. Model processing {model_seconds:.3f}s; output preparation {time.perf_counter()-pipeline.started:.3f}s.')
        if callbacks['reasoning_callback'] and reasoning:
            await callbacks['reasoning_callback'](reasoning,reasoning)
        if callbacks['response_callback'] and response:
            stopped=await callbacks['response_callback'](response,response)
            if stopped is not None:
                response=pipeline.text(stopped)
                if method=="unified_call":result=(response,reasoning)
                else:result.response=response
        return result

    async def unified_call(self, *args, **kwargs):
        return await self.buffered_call("unified_call",args,kwargs)

    async def unified_turn(self, *args, **kwargs):
        return await self.buffered_call("unified_turn",args,kwargs)

    def _call(self, messages, stop=None, run_manager=None, **kwargs):
        args, kwargs, pipeline, config = prepare(self, (messages,), kwargs, "_call",_with_pipeline=True)
        from usr.plugins.local_privacy_guard.helpers import transport_admission
        transport_admission.install()
        admission=transport_admission.receipt.set(transport_admission.capture(pipeline.agent,config))
        marker=filtered_call.set((self._privacy_inner,self._privacy_agent()))
        try:result=self._privacy_inner._call(*args, stop=stop, run_manager=run_manager, **kwargs)
        finally:
            filtered_call.reset(marker)
            transport_admission.receipt.reset(admission)
        return pipeline.for_output().text(result)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        args, kwargs, pipeline, config = prepare(self, (messages,), kwargs, "_stream",_with_pipeline=True)
        from usr.plugins.local_privacy_guard.helpers import transport_admission
        transport_admission.install()
        admission=transport_admission.receipt.set(transport_admission.capture(pipeline.agent,config))
        result=None
        marker=filtered_call.set((self._privacy_inner,self._privacy_agent()))
        try:
            for chunk in self._privacy_inner._stream(*args, stop=stop, run_manager=None, **kwargs):
                result=chunk if result is None else result+chunk
        finally:
            filtered_call.reset(marker)
            transport_admission.receipt.reset(admission)
        if result is not None:
            pipeline=pipeline.for_output()
            result.message=pipeline.value(result.message)
            result.text=pipeline.text(result.text)
            result.generation_info=pipeline.value(result.generation_info)
            if run_manager:run_manager.on_llm_new_token(result.text,chunk=result)
            yield result

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        args, kwargs, pipeline, config = prepare(self, (messages,), kwargs, "_astream",_with_pipeline=True)
        from usr.plugins.local_privacy_guard.helpers import transport_admission
        transport_admission.install()
        admission=transport_admission.receipt.set(transport_admission.capture(pipeline.agent,config))
        result=None
        marker=filtered_call.set((self._privacy_inner,self._privacy_agent()))
        try:
            async for chunk in self._privacy_inner._astream(*args, stop=stop, run_manager=None, **kwargs):
                result=chunk if result is None else result+chunk
        finally:
            filtered_call.reset(marker)
            transport_admission.receipt.reset(admission)
        if result is not None:
            pipeline=pipeline.for_output()
            result.message=pipeline.value(result.message)
            result.text=pipeline.text(result.text)
            result.generation_info=pipeline.value(result.generation_info)
            if run_manager:await run_manager.on_llm_new_token(result.text,chunk=result)
            yield result


def bind(data, agent):
    if agent is None or owner_and_config(agent)[1] is None:
        return
    inner = data.get("result")
    if inner is None or isinstance(inner, PrivacyWrapper):
        return
    if not isinstance(inner, LiteLLMChatWrapper):
        raise ValueError("This model wrapper is not supported by Local Privacy Guard.")
    provider, name = inner.model_name.split("/", 1)
    result = PrivacyWrapper(model=name, provider=provider, model_config=deepcopy(inner.a0_model_conf), **deepcopy(inner.kwargs))
    result._privacy_inner = inner
    result._privacy_agent = weakref.ref(agent)
    data["result"] = result
    agent.data["_local_privacy_wrapped"] = True


def filter_native(data):
    """Vision's direct wrapper call still carries the task-local tool owner."""
    agent = tool_agent.get()
    if agent is None or owner_and_config(agent)[1] is None:
        return
    wrapper = data["args"][0]
    owner, config = owner_and_config(agent)
    pipeline = PayloadFilter(owner, config, external=not is_local(wrapper, data.get("kwargs")))
    include_transport_credentials(pipeline,wrapper,data.get('kwargs'))
    check(wrapper.model_name,pipeline.known_secrets)
    inspect_control_options(pipeline,{**wrapper.kwargs,**data.get('kwargs',{})})
    owner.context.set_data("local_privacy_route", {"model":wrapper.model_name, "local":is_local(wrapper, data.get("kwargs")),
        "endpoint":route_host(data.get("kwargs", {}).get("api_base") or wrapper.kwargs.get("api_base", ""))})
    method = data.get('_privacy_method', 'unified_call')
    bound=inspect.signature(getattr(LiteLLMChatWrapper,method)).bind_partial(*data['args'],**data.get('kwargs',{}))
    kwargs={k:v for k,v in bound.arguments.items() if k not in {'self','kwargs'}}
    kwargs.update(bound.arguments.get('kwargs',{}))
    for key in ('system_message','user_message','messages',*CONTENT_OPTIONS):
        if key in CONTENT_OPTIONS and key not in kwargs and key in wrapper.kwargs:
            kwargs[key]=wrapper.kwargs[key]
        if key in kwargs:
            kwargs[key] = pipeline.value(kwargs[key])
    callbacks={key:kwargs.get(key) for key in ('response_callback','reasoning_callback')}
    data['_privacy_callbacks']=callbacks
    async def buffer(*unused):return None
    for key,callback in callbacks.items():
        if callback:kwargs[key]=buffer
    tokens_callback=kwargs.get('tokens_callback')
    if tokens_callback:
        async def count_only(delta,count):return await tokens_callback('',count)
        kwargs['tokens_callback']=count_only
    data["args"] = (wrapper,)
    data["kwargs"] = kwargs
    pipeline.log_summary('Tool model input')
    from usr.plugins.local_privacy_guard.helpers import transport_admission
    transport_admission.install()
    data['_privacy_pipeline']=pipeline
    if config.get('_privacy_policy',{}).get('mode')=='unmasked':
        data['_privacy_admission']=transport_admission.receipt.set(transport_admission.capture(owner,config))


async def filter_native_result(data):
    from usr.plugins.local_privacy_guard.helpers import transport_admission
    token=data.pop('_privacy_admission',None)
    if token is not None:transport_admission.receipt.reset(token)
    agent=tool_agent.get()
    if agent is None or data.get("exception") is not None:return
    pipeline=data.pop('_privacy_pipeline',None)
    if pipeline is None:
        owner,config=owner_and_config(agent)
        if config is None:return
        pipeline=PayloadFilter(owner,config,False)
    else:pipeline=pipeline.for_output()
    include_transport_credentials(pipeline,data['args'][0])
    result=data.get("result")
    if isinstance(result,tuple) and len(result)==2:
        data['result']=tuple(pipeline.text(value) for value in result)
    elif hasattr(result,'response'):
        result=deepcopy(result)
        result.response=pipeline.text(result.response);result.reasoning=pipeline.text(result.reasoning)
        result.input_items=pipeline.value(result.input_items)
        for item in result.output_items:item.data=pipeline.value(item.data)
        result.raw=pipeline.value(result.raw)
        data['result']=result
    pipeline.log_summary('Tool model output')
    result=data.get('result')
    response,reasoning=result if isinstance(result,tuple) else (result.response,result.reasoning)
    callbacks=data.get('_privacy_callbacks',{})
    if callbacks.get('reasoning_callback') and reasoning:
        await callbacks['reasoning_callback'](reasoning,reasoning)
    if callbacks.get('response_callback') and response:
        stopped=await callbacks['response_callback'](response,response)
        if stopped is not None:
            checked=pipeline.text(stopped)
            if isinstance(result,tuple):data['result']=(checked,reasoning)
            else:result.response=checked
