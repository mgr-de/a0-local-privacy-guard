"""Admission at each native provider attempt, after rate-limit waits.

Admission is the start boundary. A revoked admitted call may finish. Internal
LiteLLM/SDK retries are disabled for unmasked calls; framework retries re-enter
these four dispatch functions and receive a fresh admission.
"""
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import inspect

receipt = ContextVar('privacy_transport_admission', default=None)
_bridges = {}


def capture(agent, config):
    policy = config.get('_privacy_policy', {'mode': 'masked'})
    return (agent, deepcopy(policy))


def admit(options):
    value = receipt.get()
    if not value or value[1].get('mode') != 'unmasked':
        return options
    from usr.plugins.local_privacy_guard.helpers.instance import manager
    instance = manager()
    if instance is None:
        raise ValueError('Restore central privacy protection before continuing this Developer chat.')
    instance.require_components()
    from usr.plugins.requesty_privacy_agent.helpers import profile_exceptions
    if profile_exceptions.effective(value[0]) != value[1]:
        raise ValueError(profile_exceptions.REVOKED)
    # Unowned alternate clients/fallback routers would evade per-attempt checks.
    forbidden = {'client', 'aclient', 'http_client', 'fallbacks', 'context_window_fallbacks', 'model_list', 'router'}
    if forbidden.intersection(options):
        raise ValueError('Developer calls require the native checked provider transport.')
    return {**options, 'num_retries': 0, 'max_retries': 0}


def install():
    from helpers import litellm_transport
    for name in ('completion', 'acompletion', 'responses', 'aresponses'):
        current = getattr(litellm_transport, name)
        if getattr(current, '_privacy_admission', False):
            continue
        def factory(previous):
            if inspect.iscoroutinefunction(previous):
                @wraps(previous)
                async def checked(*args, **kwargs):
                    return await previous(*args, **admit(kwargs))
            else:
                @wraps(previous)
                def checked(*args, **kwargs):
                    return previous(*args, **admit(kwargs))
            checked._privacy_admission = True
            return checked
        proxy = factory(current)
        setattr(litellm_transport, name, proxy)
        _bridges[name] = (current, proxy)


def healthy():
    from helpers import litellm_transport
    return all(getattr(getattr(litellm_transport, name), '_privacy_admission', False)
        for name in ('completion', 'acompletion', 'responses', 'aresponses'))
