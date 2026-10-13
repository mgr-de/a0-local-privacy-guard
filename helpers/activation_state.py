"""Strict central activation protocol, usable without the Manager plugin."""
import json
from pathlib import Path

def activation_state(user):
    user=Path(user).resolve()
    folder=user/'privacy-agent'
    if folder.is_symlink() or not folder.resolve().is_relative_to(user):
        raise ValueError('Privacy Agent activation storage is unsafe. Restore it from a trusted backup.')
    marker=folder/'active.json'
    receipt=folder/'activation-record.json'
    journal=user/'privacy-guard-adapters'/'requesty_privacy_agent.json'
    if marker.is_symlink() or receipt.is_symlink():
        raise ValueError('Privacy Agent activation file is unsafe. Restore it from a trusted backup.')
    if receipt.exists():
        try:record=json.loads(receipt.read_text(encoding='utf-8'))
        except Exception:raise ValueError('Privacy Agent activation record cannot be read. Restore it from a trusted backup.') from None
        if not isinstance(record,dict) or record.get('schema')!=1 or record.get('managed') is not True:
            raise ValueError('Privacy Agent activation record is invalid. Restore it from a trusted backup.')
    if not marker.exists():
        if receipt.exists() or journal.exists() or journal.is_symlink():
            raise ValueError('Privacy Agent activation file is missing from a managed installation. Restore active.json from a trusted backup; protection was not intentionally disabled.')
        return 'unconfigured'
    try:value=json.loads(marker.read_text(encoding='utf-8'))
    except Exception:raise ValueError('Privacy Agent activation cannot be read. Restore active.json from a trusted backup.') from None
    if not isinstance(value,dict) or type(value.get('active')) is not bool:
        raise ValueError('Privacy Agent activation must contain a boolean active value. Restore active.json from a trusted backup.')
    return 'active' if value['active'] else 'inactive'
