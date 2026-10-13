# Single production detector — release decision

The fixed production text detector is optimized spaCy NER with built-in and custom Regex rules. Its paragraph cache, secret checks, current-known-value matching and persistent chat mappings remain in place. No model route, browser/media boundary or saved user preset is changed by this decision.

Presidio/Nym runtime modules, optional package setup, backend selection and dependent comparison adapters have been removed from main. Existing `backend: presidio`/`backend: nym` markers are normalized by PIIFilter to the fixed detector without rewriting configuration files. Unknown backend names fail validation. Other configured languages continue using spaCy; no fallback detector or alternate model download exists in production.

The complete evaluation implementation, benchmark tools and measurement evidence are preserved on `archive/cpu-pii-evaluation-2026-10-13` in all three repositories. Use that branch only for future experiments. Its draft PRs are closed rather than merged into production. The archive is retained when temporary feature branches are removed.

Before merging, the release is validated with isolated native Python/Node suites, private numeric-only performance replay, real uninstall/reinstall in the provided Agent Zero test instance, preservation of original credentials/presets/profiles/mappings, and an actual local Ollama chat. No paid Requesty call is used. Detailed verified lifecycle evidence is recorded separately after the run.

Local Privacy Guard is released as 1.7.4; Privacy Agent as 0.2.7, requiring the fixed Local Privacy Guard release. Requesty remains 0.6.0.
