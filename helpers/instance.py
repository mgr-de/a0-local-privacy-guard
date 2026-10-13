"""Optional instance-manager discovery. An active marker must never fail open."""
import json
from pathlib import Path

def manager():
    try:
        from helpers import files
    except ImportError:return None  # Framework-free pure unit tests.
    from .activation_state import activation_state
    if activation_state(files.get_abs_path(files.USER_DIR)) != 'active':return None
    try:
        from usr.plugins.requesty_privacy_agent.helpers import manager as implementation
    except ImportError:
        raise ValueError('Privacy Agent is active but its manager is missing. Restore the plugin or deactivate centrally.') from None
    implementation.require_components()
    return implementation
