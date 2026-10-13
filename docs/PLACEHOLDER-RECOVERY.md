# Placeholder recovery — 14 October 2026

A model can change a placeholder type (for example PERSON to ORGANISATION) while preserving the chat namespace, numeric ID and spelling variant. Exact lookup then leaves the token visible even when the original local mapping exists.

Local display decoding now recovers a changed type only when that exact namespace, numeric ID and optional variant identify one stored token in the current chat. It reads one snapshot per display batch. Foreign namespaces, missing IDs/variants and ambiguous historical identities stay unresolved. Canonical history and mappings are not rewritten. Normal protocol/input decoding still requires exact tokens; user-entered changed tokens gain no routing privileges or checked-text proofs.

Masked response processing canonicalizes these uniquely recoverable tokens before detection, keeping private originals local. Secret checks still run and newly generated PII is still scanned. Secret-only and log-only modes do not rewrite output. Every masked model call receives the same instruction from the first turn to preserve exact tokens and avoid invented identities.

This repairs display/transport syntax, not the meaning of a response. A model can use a valid ID in the wrong place. Masked jurisdictions can also remove facts needed for advice. Recovery does not certify factual, financial or tax correctness, fix the underlying NER classification, or guarantee recovery when the model changes IDs. No real financial-context text is included in these regression fixtures.

## Validation

On the isolated Agent Zero 2.14 instance: 184 Local Guard, 79 Gateway and 97 Manager Python tests passed (360 total, plus 32 Gateway subtests); 39 Node tests passed. On the isolated 2.13 source harness, 181 Local Guard tests passed and three 2.14-specific tests were skipped. These are local/simulated integration checks, with no paid model requests for this correction.

Regressions cover changed types, exact variants, foreign namespaces/profiles, unknown IDs/variants, ambiguous historical rows, unchanged incoming protocol privileges, response PII and Secret checks, first-turn guidance, log-only behavior, and the local display API's batched snapshot lookup. Test presets were reset in the disposable 2.14 instance before running the Gateway tests; the two user instances were not used for pytest.
