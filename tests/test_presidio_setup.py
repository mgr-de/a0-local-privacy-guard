import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
pytest.importorskip('agent')
from usr.plugins.local_privacy_guard.api.presidio_setup import PresidioSetup
from usr.plugins.local_privacy_guard.helpers import presidio_backend

def test_optional_install_is_fixed_and_requires_restart(monkeypatch):
    import usr.plugins.local_privacy_guard.api.presidio_setup as api
    monkeypatch.setattr(presidio_backend,'restart_requested',False)
    run=Mock(return_value=SimpleNamespace(returncode=0));monkeypatch.setattr(api.subprocess,'run',run)
    result=asyncio.run(PresidioSetup.__new__(PresidioSetup).process({'action':'install','package':'arbitrary'},None))
    assert result['ok'] and result['restart_required']
    args=run.call_args.args[0]
    assert 'presidio-analyzer==2.2.358' in args and 'arbitrary' not in args
    assert presidio_backend.restart_requested
    with pytest.raises(ValueError,match='Restart'):presidio_backend.validate(['de','en'])

def test_failed_install_does_not_claim_available(monkeypatch):
    import usr.plugins.local_privacy_guard.api.presidio_setup as api
    monkeypatch.setattr(presidio_backend,'restart_requested',False)
    monkeypatch.setattr(api.subprocess,'run',Mock(return_value=SimpleNamespace(returncode=1)))
    result=asyncio.run(PresidioSetup.__new__(PresidioSetup).process({'action':'install'},None))
    assert not result['ok'] and not result.get('available')
    assert presidio_backend.restart_requested

def test_unknown_action_has_no_side_effect(monkeypatch):
    import usr.plugins.local_privacy_guard.api.presidio_setup as api
    run=Mock();monkeypatch.setattr(api.subprocess,'run',run)
    result=asyncio.run(PresidioSetup.__new__(PresidioSetup).process({'action':'run'},None))
    assert not result['ok'];run.assert_not_called()
