# Production privacy regression tools

The sole production detector is spaCy NER with shared Regex rules. Use `filter_performance.py` in an isolated Agent Zero environment to replay a private system context: output contains numeric measurements only and makes no model call. Remaining tools cover native mappings, memory, compaction, browser boundaries and budget guards.

Historical alternative-detector adapters, long comparisons and their dependent scripts are preserved on `archive/cpu-pii-evaluation-2026-10-13`; they are not shipped in the production runtime. Historical reports predate the single-detector decision and are not current install instructions.

Do not run paid transport scripts without a separate established budget. The single-detector release is tested with local Ollama and simulated transports only. Existing language model packages and mappings are not removed during plugin uninstall.
