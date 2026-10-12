"""Read-only UI example: fixed synthetic data, no inference calls or downloads."""
from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter, SPACY_MODEL_NAMES

SAMPLE = "My email is anna@example.com."


def example(config):
    if not isinstance(config, dict) or not isinstance(config.get("pii_filter"), dict):
        raise ValueError("Invalid filter settings.")
    raw = config["pii_filter"]
    for value in (config.get("enabled", False), raw.get("enabled", False),
                  raw.get("use_regex", True), raw.get("use_ner", True)):
        if type(value) is not bool:
            raise ValueError("Filter switches must be true or false.")
    action = raw.get("action", "redact")
    if action not in ("redact", "block", "log_only"):
        raise ValueError("Unknown detection action.")
    languages = raw.get("languages", [])
    if not isinstance(languages, list) or any(not isinstance(lang, str) or lang not in SPACY_MODEL_NAMES for lang in languages):
        raise ValueError("Unknown detection language.")
    # Never execute arbitrary user regexes or persist mappings during this UI test.
    settings = {"use_regex": raw.get("use_regex", True), "use_ner": raw.get("use_ner", True),
                "languages": list(dict.fromkeys(languages)), "store_mapping": False, "backend": raw.get("backend", "local")}
    enabled = config.get("enabled", False) and raw.get("enabled", False)
    filt = PIIFilter(settings)
    result = filt.filter(SAMPLE) if enabled else None
    loaded = filt.get_loaded_languages() if enabled and settings["use_ner"] else []
    wanted = list(dict.fromkeys(["en", *languages]))
    missing = [lang for lang in wanted if lang not in loaded] if enabled and settings["use_ner"] else []
    detected = result.pii_count if result else 0
    blocked = bool(enabled and action == "block" and detected)
    output = None if blocked else result.filtered_text if enabled and action == "redact" else SAMPLE
    return {"sample": SAMPLE, "output": output, "blocked": blocked, "detected": detected,
            "enabled": enabled, "loaded_languages": loaded, "missing_languages": missing,
            "scope": "Built-in filter rules on a fixed synthetic example; not an active-chat or completeness check."}
