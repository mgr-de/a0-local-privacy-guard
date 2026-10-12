"""Optional instance-manager discovery. An active marker must never fail open."""
import json
from pathlib import Path

def manager():
    try:
        from helpers import files
    except ImportError:return None  # Framework-free pure unit tests.
    marker=Path(files.get_abs_path(files.USER_DIR))/'privacy-agent'/'active.json'
    if not marker.exists():return None
    if marker.is_symlink():raise ValueError('Privacy Agent activation file is unsafe.')
    try:value=json.loads(marker.read_text(encoding='utf-8'))
    except Exception:raise ValueError('Privacy Agent activation cannot be read. Repair the installation.') from None
    if value.get('active') is not True:return None
    try:
        from usr.plugins.requesty_privacy_agent.helpers import manager as implementation
    except ImportError:
        raise ValueError('Privacy Agent is active but its manager is missing. Restore the plugin or deactivate centrally.') from None
    implementation.require_components()
    return implementation
