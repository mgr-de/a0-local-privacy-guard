# Optional Presidio: fair local comparison

The optional backend replaces only NER analysis, not the privacy gateway or mapping. Shared regex/custom patterns, overlap resolution and production SQLite tokens remain in use. No anonymizer or second vault is introduced. Native request processing injects the already checked spaCy instances; automatic model downloading is never invoked.

## Configurations

A: same spaCy 3.8.16 / DE+EN small 3.8.0 models, fixed independent paragraphs, native regex/custom rules and equivalent NER entity labels, zero analyzer score threshold.

B: same models and shared base rules, plus local Presidio email/phone/IBAN recognizers and its default context enhancer, score threshold 0.35. This is an initial candidate configuration, not an empirically optimized optimum. Adding recognizers follows the regex switch; disabling regex does not secretly enable additional pattern recognizers. No extra surrounding context is supplied; changing this requires a new cache key/segmentation version.

The recognizer interface yields offsets/types/source/score. The common filter performs overlap resolution and mapping. Scores are not calibrated probabilities. Optional requirements are pinned; availability checks reject a different analyzer version. Missing languages/components stop processing, never silently choose another backend.

## Offline result

40 synthetic cases cover DE/EN contacts, Python/JSON, technical instructions and negative examples. Gold annotations use exact spans and types. Both architectures use the same production mapping, with separate chat scopes. All three configurations produced identical detector spans. German exact-span precision 0.871 / recall 0.964; English precision 0.933 / recall 1.000. This small corpus is not a general population estimate. No tested complete contact values remained in the masked payload.

All 40 cases restored semantically; 38 retained byte-exact text. Two protocol-JSON cases normalize whitespace. Six additional DE/EN/mixed sessions (40/100 each) restored all 420 messages exactly, preserved full-name families and had no tested full contact/name disclosures.

JSON normalization is evaluated separately from token restoration: whitespace changes are not identity loss. Free LLM answer quality, indirect reidentification and image sanitization are not proven. Total comparison runtime includes initialization and mapping and is not a fair standalone detector speed ranking; the dedicated performance replay reports p50/p95 separately.

Run `tools/privacy_benchmark/detector_comparison.py --output RESULTS.json` inside a disposable native Agent Zero test environment with optional Presidio installed. It makes zero LLM calls and exports aggregate metrics only. Keep the existing standard detector as default; any future change needs new evidence and a separate decision.
