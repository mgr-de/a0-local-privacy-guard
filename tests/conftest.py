"""Test bootstrap for Local Privacy Guard.

Makes the production-like directory layout importable and stubs the Agent
Zero framework modules (`helpers.extension`, `helpers.plugins`) that the
plugin extensions import at module load time.
"""

import sys
import types
from pathlib import Path

# <plugin_root>/tests/conftest.py -> project root is three parents up
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _install_framework_stubs() -> None:
    if "helpers" in sys.modules and hasattr(sys.modules["helpers"], "extension"):
        return  # already stubbed (or the real framework is importable)

    helpers = types.ModuleType("helpers")
    helpers.__path__ = []  # mark as package for submodule imports

    extension_mod = types.ModuleType("helpers.extension")

    class Extension:
        def __init__(self, agent=None, **kwargs):
            self.agent = agent
            self.kwargs = kwargs

    extension_mod.Extension = Extension

    plugins_mod = types.ModuleType("helpers.plugins")
    plugins_mod.get_plugin_config = lambda *args, **kwargs: {}

    helpers.extension = extension_mod
    helpers.plugins = plugins_mod
    sys.modules["helpers"] = helpers
    sys.modules["helpers.extension"] = extension_mod
    sys.modules["helpers.plugins"] = plugins_mod


_install_framework_stubs()
