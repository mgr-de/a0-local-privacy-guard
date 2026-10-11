"""
Local Privacy Guard - Agent Init Extension.

Runs once per agent context when the agent is initialized:

1. Configures local embeddings (sentence-transformers) in presets.yaml
2. Runs privacy verification and logs the results

All operations are local. No data is sent anywhere.

Note: the extension point is ``agent_init``, which Agent Zero dispatches
synchronously right after the Agent object is constructed. ``execute``
must therefore NOT be a coroutine here.
"""

from helpers.extension import Extension
from helpers import plugins

PLUGIN_NAME = "local_privacy_guard"

# Contexts whose agent_init already ran (id -> True). Keeps the config
# pass and verification to one run per context instead of per sub-agent.
_initialized_contexts: dict = {}


def _safe_log(agent, level: str, message: str):
    """Log safely regardless of agent object shape (agent.log may not exist).

    Tries, in order: agent.log, agent.context.log, Python logging module.
    Never raises - logging must not break the LLM call.
    """
    try:
        log = getattr(agent, "log", None)
        if log is not None and hasattr(log, level):
            getattr(log, level)(message)
            return
    except Exception:
        pass
    try:
        ctx_log = getattr(getattr(agent, "context", None), "log", None)
        if ctx_log is not None and hasattr(ctx_log, level):
            getattr(ctx_log, level)(message)
            return
    except Exception:
        pass
    try:
        import logging
        getattr(logging.getLogger("local_privacy_guard"), level)(message)
    except Exception:
        pass


class LocalPrivacyGuardInitExtension(Extension):
    """Initializes local privacy settings when the agent starts."""

    def execute(self, **kwargs):
        agent = self.agent
        if not agent:
            return

        # Only one run per context: sub-agents share the context and the
        # main agent re-initialization must not rewrite presets repeatedly.
        ctx = getattr(agent, "context", None)
        if ctx is None:
            return
        ctx_id = getattr(ctx, "id", "default")
        if _initialized_contexts.get(ctx_id):
            return
        _initialized_contexts[ctx_id] = True

        config = plugins.get_plugin_config(PLUGIN_NAME, agent=agent) or {}

        if not config.get("enabled", True):
            _safe_log(agent, "info", "[Local Privacy Guard] Plugin is disabled")
            return

        # 1. Configure local embeddings
        emb_cfg = config.get("local_embedding", {}) or {}
        if emb_cfg.get("enabled", True) and emb_cfg.get("auto_configure", True):
            try:
                from usr.plugins.local_privacy_guard.helpers.embedding_config import (
                    configure_local_embedding,
                )
                model = emb_cfg.get(
                    "model",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                )
                result = configure_local_embedding(model)
                if result["changed"]:
                    _safe_log(agent, "info",
                        "[Local Privacy Guard] Configured local embedding model: " + model
                        + ((" (backup: " + result["backup"] + ")") if result["backup"] else "")
                    )
                    # Notify the framework so caches (e.g. memory embeddings)
                    # reload instead of reading the stale preset. Best effort.
                    try:
                        import asyncio
                        from helpers import extension as _ext

                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = None
                        coro = _ext.call_extensions_async(
                            "embedding_model_changed", agent, model=model
                        )
                        if loop is not None:
                            asyncio.ensure_future(coro)
                    except Exception:
                        pass
                else:
                    _safe_log(agent, "info",
                        "[Local Privacy Guard] Embedding already local: " + model
                    )
            except Exception as exc:
                _safe_log(agent, "error",
                    "[Local Privacy Guard] Failed to configure local embedding: " + str(exc)
                )

        # 2. Run privacy verification
        ver_cfg = config.get("verification", {}) or {}
        if ver_cfg.get("enabled", True):
            try:
                from usr.plugins.local_privacy_guard.helpers.privacy_verifier import (
                    verify_all,
                )
                components = ver_cfg.get("check_components") or None
                report = verify_all(config, components)
                if report["overall_ok"]:
                    _safe_log(agent, "info",
                        "[Local Privacy Guard] Privacy verification: ALL CHECKS PASSED"
                    )
                else:
                    for r in report["results"]:
                        if not r.get("ok", False):
                            for issue in r.get("issues", []):
                                _safe_log(agent, "warning",
                                    "[Local Privacy Guard] " + r.get("component", "") + ": " + issue
                                )
            except Exception as exc:
                _safe_log(agent, "error",
                    "[Local Privacy Guard] Privacy verification failed: " + str(exc)
                )
