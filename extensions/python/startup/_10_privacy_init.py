"""
Local Privacy Guard - Startup Extension.

On Agent Zero startup:
1. Configures local embeddings (sentence-transformers) in presets.yaml
2. Runs privacy verification and logs the results

All operations are local. No data is sent anywhere.
"""

from helpers.extension import Extension
from helpers import plugins

PLUGIN_NAME = "local_privacy_guard"


class LocalPrivacyGuardStartupExtension(Extension):
    """Initializes local privacy settings on startup."""

    async def execute(self, *args, **kwargs):
        if not self.agent:
            return

        config = plugins.get_plugin_config(PLUGIN_NAME, agent=self.agent) or {}

        if not config.get("enabled", True):
            self.agent.log.info("[Local Privacy Guard] Plugin is disabled")
            return

        # 1. Configure local embeddings
        emb_cfg = config.get("local_embedding", {})
        if emb_cfg.get("enabled", True) and emb_cfg.get("auto_configure_presets", True):
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
                    self.agent.log.info(
                        f"[Local Privacy Guard] Configured local embedding model: {model}"
                        + (f" (backup: {result['backup']})" if result["backup"] else "")
                    )
                else:
                    self.agent.log.info(
                        f"[Local Privacy Guard] Embedding already local: {model}"
                    )
            except Exception as exc:
                self.agent.log.error(
                    f"[Local Privacy Guard] Failed to configure local embedding: {exc}"
                )

        # 2. Run privacy verification
        ver_cfg = config.get("verification", {})
        if ver_cfg.get("enabled", True):
            try:
                from usr.plugins.local_privacy_guard.helpers.privacy_verifier import (
                    verify_all,
                )
                components = ver_cfg.get("check_components") or None
                report = verify_all(config, components)
                if report["overall_ok"]:
                    self.agent.log.info(
                        "[Local Privacy Guard] Privacy verification: ALL CHECKS PASSED"
                    )
                else:
                    for r in report["results"]:
                        if not r.get("ok", False):
                            for issue in r.get("issues", []):
                                self.agent.log.warning(
                                    f"[Local Privacy Guard] {r['component']}: {issue}"
                                )
            except Exception as exc:
                self.agent.log.error(
                    f"[Local Privacy Guard] Privacy verification failed: {exc}"
                )
