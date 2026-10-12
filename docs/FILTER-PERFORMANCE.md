# Incremental filtering, phase 1

All supported outgoing model text remains checked. Paragraphs are fixed independent NER recognition units, matching the previous detector. Batching changes execution, not the context supplied to recognition.

The process-local cache has a 32 MiB accounting limit and 15-minute lifetime, with LRU eviction. Values contain only offsets, types, sources, scores and language. Keys contain keyed fingerprints and protection/configuration/model identity. Fingerprints are not an anonymity guarantee. Original text is not cached or exported. Secrets and current mappings are checked on every pass, including cache hits.

Mapping snapshots check the transactional SQLite revision once per filter pass. Input and output use separate snapshots. Local committed writes update active snapshots; other-process writes become visible next pass. Token allocation remains atomic. Existing mapping files receive a revision table and insert trigger without changing existing tokens. Archiving retains mappings; final deletion also invalidates the cache.

Only internally produced string objects may carry process-local inspection proof. Plain user/model text and placeholder syntax never establish trust. Serialization and restart remove proof. Changed text/configuration requires recognition again. Persistent trusted-history provenance is not implemented.

Native calls expose input preparation, model processing and output preparation separately. Diagnostics contain counts and durations, never content or fingerprints. Replacement counts cover repeated occurrences throughout the full model context, not unique people.

No Ollama runtime, additional service, new model route or image/browser restriction is introduced. Presidio remains a separate optional second phase.

## Measured phase-1 result (12 October 2026)

Private 37,119-character system-context replay; 20 samples per scenario, sequential baseline/candidate processes, no profiler and no LLM calls. Text remains inside the test container. Shared development hardware is not a controlled performance lab.

| Scenario | Baseline p50 / p95 | Optimized p50 / p95 |
|---|---:|---:|
| Unchanged context | 3.025 / 3.216 s | 0.200 / 0.204 s |
| Known context plus new message | 3.052 / 3.144 s | 0.212 / 0.218 s |
| New large text | 5.202 / 6.147 s | 2.445 / 3.330 s |

Warm p95 improved 93.7%; a new message ran one new recognition unit and reused 1,095. New-text p95 improved 45.8%. These results exclude model/provider time. Optimized model loading was measured separately at 1.055 s; baseline preload was outside its recorded interval and is not a comparable cold-load measurement.

All 16 production language replays passed: 1,120 exact restorations and stable full-name families, no tested complete contact values or full names in captured text. This deterministic corpus does not establish free-answer quality, general PII-freedom or sanitized images.

## Native form regression, 13 October 2026

The first two real DeepSeek Flash extractions failed the strict field comparison, despite correct masking of the known full name/address. Diagnostic output showed an additional false PERSON mapping for `ich bin Herr`. Version 1.7.3 excludes specific introduction phrases both from NER merge and existing-value matching; old records are retained. A third reserved attempt returned exact field placeholders and filled the real native browser form with locally restored fictional values. No image was sent. This is a controlled native extraction-to-browser integration, not a 40/100-turn free-answer quality claim.
