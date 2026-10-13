# Production privacy regression tools

The sole production detector is spaCy NER with shared Regex rules. Use `filter_performance.py` in an isolated Agent Zero environment to replay a private system context: output contains numeric measurements only and makes no model call. Remaining tools cover native mappings, memory, compaction, browser boundaries and budget guards.

Local Privacy Guard 1.8.1 also recognizes supported source syntax; comments, literals and secrets remain checked. The native code regression suites are `tests/test_code_regions.py` and `tests/test_code_model_guard.py` in the plugin root. See [code handling](../../docs/CODE-FILTERING.md). These tests use synthetic inputs and simulated model transport; they do not require Ollama or a paid provider.

Historical alternative-detector adapters, long comparisons and their dependent scripts are preserved on `archive/cpu-pii-evaluation-2026-10-13`; they are not shipped in the production runtime. Historical reports predate the single-detector decision and are not current install instructions.

Do not run paid transport scripts without a separate established budget. The single-detector release is tested with local Ollama and simulated transports only. Existing language model packages and mappings are not removed during plugin uninstall.

Developer profile exceptions (1.9.0/manager 0.3.0) are tested in the native offline integration suite; this detector benchmark does not grant exemptions or change the default detector or routes. It makes no paid Requesty calls.
