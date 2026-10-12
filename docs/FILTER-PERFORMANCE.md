# Incremental filtering, phase 1

All supported outgoing model text remains checked. Paragraphs are fixed independent NER recognition units, matching the previous detector. Batching changes execution, not the context supplied to recognition.

The process-local cache has a 32 MiB accounting limit and 15-minute lifetime, with LRU eviction. Values contain only offsets, types, sources, scores and language. Keys contain keyed fingerprints and protection/configuration/model identity. Fingerprints are not an anonymity guarantee. Original text is not cached or exported. Secrets and current mappings are checked on every pass, including cache hits.

Mapping snapshots check the transactional SQLite revision once per filter pass. Input and output use separate snapshots. Local committed writes update active snapshots; other-process writes become visible next pass. Token allocation remains atomic. Existing mapping files receive a revision table and insert trigger without changing existing tokens. Archiving retains mappings; final deletion also invalidates the cache.

Only internally produced string objects may carry process-local inspection proof. Plain user/model text and placeholder syntax never establish trust. Serialization and restart remove proof. Changed text/configuration requires recognition again. Persistent trusted-history provenance is not implemented.

Native calls expose input preparation, model processing and output preparation separately. Diagnostics contain counts and durations, never content or fingerprints. Replacement counts cover repeated occurrences throughout the full model context, not unique people.

No Ollama runtime, additional service, new model route or image/browser restriction is introduced. Presidio remains a separate optional second phase.
