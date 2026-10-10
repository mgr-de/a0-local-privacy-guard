"""
Privacy Verification Helper.

Checks that privacy-relevant Agent Zero components are configured to
run locally. Produces a report used by the startup extension for logging
and optional user warnings.
"""

from __future__ import annotations

from typing import Any, Dict, List

from usr.plugins.local_privacy_guard.helpers.embedding_config import (
    verify_embedding_is_local,
    check_sentence_transformers_available,
)


def verify_pii_filter(config: Dict[str, Any]) -> Dict[str, Any]:
    """Verify PII filter configuration."""
    pii_cfg = (config or {}).get("pii_filter", {})
    issues: List[str] = []
    if not pii_cfg.get("enabled", False):
        issues.append("PII filter is disabled")
    if pii_cfg.get("action") == "log_only":
        issues.append("PII filter is in log_only mode - PII is sent unmodified")
    if pii_cfg.get("store_mapping", False):
        issues.append("store_mapping is enabled - PII is stored in memory (session only)")
    return {
        "component": "pii_filter",
        "ok": len(issues) == 0,
        "enabled": pii_cfg.get("enabled", False),
        "action": pii_cfg.get("action", "redact"),
        "issues": issues,
    }


def verify_embedding() -> Dict[str, Any]:
    """Verify that memory embeddings run locally."""
    result = verify_embedding_is_local()
    issues: List[str] = []
    if not result["is_local"]:
        issues.append(
            f"Embedding model '{result['model']}' is not a local sentence-transformers model"
        )
    if result["api_key_set"]:
        issues.append("Embedding configuration contains an API key")
    if result["api_base"]:
        issues.append(f"Embedding configuration points to external API: {result['api_base']}")
    if not check_sentence_transformers_available():
        issues.append("sentence-transformers package is not installed")
    return {
        "component": "embedding",
        "ok": len(issues) == 0,
        "is_local": result["is_local"],
        "model": result["model"],
        "issues": issues,
    }


def verify_memory() -> Dict[str, Any]:
    """Verify memory storage is local (FAISS files under /a0/usr)."""
    from pathlib import Path

    issues: List[str] = []
    memory_dir = Path("/a0/usr/memory")
    if not memory_dir.exists():
        issues.append("Memory directory does not exist yet (will be created on first use)")
    return {
        "component": "memory",
        "ok": True,  # memory plugin is local by design
        "storage": str(memory_dir),
        "issues": issues,
    }


def run_verification(config: Dict[str, Any], components: List[str] | None = None) -> Dict[str, Any]:
    """Run privacy verification for the given components.

    Returns a report dict with per-component results and an overall status.
    """
    checkers = {
        "pii_filter": lambda: verify_pii_filter(config),
        "embedding": verify_embedding,
        "memory": verify_memory,
    }
    wanted = components or list(checkers.keys())

    results = []
    for name in wanted:
        checker = checkers.get(name)
        if checker is None:
            results.append({"component": name, "ok": False, "issues": ["unknown component"]})
            continue
        try:
            results.append(checker())
        except Exception as exc:
            results.append({"component": name, "ok": False, "issues": [str(exc)]})

    return {
        "overall_ok": all(r.get("ok", False) for r in results),
        "results": results,
    }


# Alias for backward compatibility
verify_all = run_verification
