# CPU PII detector evaluation — 2026-10-13

Implemented an explicit optional offline Nym ONNX CPU backend in Local Privacy Guard, with a pinned artifact bundle, checksum validation, BIO decoding, overlapping windows, paragraph cache reuse and shared regex/mapping behavior. The native gateway uses the Nym manifest for model identity instead of loading spaCy. Existing defaults and routes remain unchanged.

Privacy Agent retains optional backend settings under its protection floor; its missing-model guidance now covers the selected backend. Requesty Guard adds routing regression coverage. Both companion repositories link the evaluation procedure; neither duplicates inference.

## Measured detector/component results

35 synthetic DE/EN/mixed cases, three repetitions, cold/warm cache, concurrency 1/2/4, four backends (24 successful isolated worker runs; 5,880 timed component samples). Quality is scored once per unique case in each run. The corpus includes an intentionally long technical paragraph and ambiguous synthetic surnames; it is not representative of production traffic.

| Backend | Exact typed precision / recall | Typed character precision / recall | Cold input p50 / p95 ms | Warm input p50 / p95 ms | Peak RSS MiB | Cold CPU seconds | Concurrency 4 cold p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| regex | 100.0% / 57.9% | 100.0% / 66.4% | 0.028 / 0.057 | 0.028 / 0.053 | 30.4 | 0.078 | 0.055 |
| local | 19.3% / 71.1% | 24.9% / 76.8% | 5.298 / 6.973 | 0.671 / 0.820 | 251.3 | 1.375 | 130.054 |
| presidio | 19.3% / 71.1% | 24.9% / 76.8% | 7.964 / 14.254 | 0.662 / 0.836 | 264.8 | 2.000 | 150.062 |
| nym | 51.2% / 57.9% | 98.0% / 85.0% | 43.107 / 118.061 | 0.043 / 0.081 | 809.4 | 24.797 | 1948.117 |

Input timing here measures the detector. Full JSON reports also separate production mapping, simulated transport, output detection, restoration and total component latency, with CPU percent, throughput, load time, SQL/cache counters, environment/package versions, corpus hash and implementation hashes. CPU seconds include client setup and warmup; RSS is sampled and includes model loading. These desktop measurements are estimates, not controlled hardware certification.

On this corpus Nym produced fewer technical false positives and removed every complete annotated value from standalone masked input. Regex alone leaked known values in 14/35 unique cases; spaCy and Presidio B in 3/35; Nym in 0/35. Whole-value leak checks can miss identifying fragments, and typed character recall is below 100%. Nym also has more entity-boundary/type differences than strict span scores alone explain.

The long repeated technical paragraph strongly affects micro precision by producing many baseline false positives. Per-language/per-type counts are in the JSON evidence. These micro scores should not be read as general spaCy/Presidio accuracy estimates.

Cold Nym inference uses substantially more CPU time and RSS than spaCy or Presidio. Warm cache hits reduce its cost. Its shared session serializes clients, so concurrency increases queue latency. These results support keeping Nym optional and do not justify changing the default.

Presidio B and the existing local backend produced identical strict/character quality counts on this corpus. Presidio A is supported by the harness but was not measured in this run. Nym fp32, smaller Nym models, recall-first decoding and threshold sweeps were not evaluated.

## Native integration and local model checks

The native benchmark uses real PayloadFilter input/output checks on system/tool/memory/summary fields, production persistent mappings and a simulated echo transport. It was measured at concurrency 1, two repetitions, cold/warm cache, with each of the three NER backends (six runs, 420 timed samples). Mapping state persists across cases per client.

| Backend/cache | Exact roundtrips | Semantic roundtrips | Complete known-value leak cases |
|---|---:|---:|---:|
| local/cold | 60/70 | 70/70 | 0 |
| local/warm | 60/70 | 70/70 | 0 |
| presidio/cold | 60/70 | 70/70 | 0 |
| presidio/warm | 60/70 | 70/70 | 0 |
| nym/cold | 60/70 | 70/70 | 0 |
| nym/warm | 60/70 | 70/70 | 0 |

Exact native roundtrips differ because the existing gateway normalizes JSON whitespace. Semantic comparison parses JSON values and preserves their meaning. Restoration is checked per text field before serialization. No production mapping or JSON gateway behavior was changed for this evaluation.

Nine actual local Ollama calls used granite4:tiny-h through real native PrivacyWrapper instances: three per backend. All nine restored the expected echo; no complete known email value leaked into the local transport prompt or masked output. The first local call included model loading (about 14.5 seconds); later calls were roughly 0.19–0.38 seconds. This smoke is too small for a fair latency ranking or a model-quality claim.

Final native tests in a clean source snapshot: Local Privacy Guard 139 passed; Requesty Guard 80 passed; Privacy Agent 41 passed (260 total). This includes the real ONNX overflow test, real Nym wrapper input/output/callback test, mapping ownership, history, subordinate scope, streams, media boundaries, presets and routing. Optional dependencies were supplied; no tests were skipped. Python/AST and Git whitespace checks passed. No new credential patterns, weights, vaults or real PII were committed.

The Agent Zero test endpoint and host Ollama were reachable. The active server plugin installation and saved routes were not replaced. Tests used isolated source/plugin copies and synthetic data. No live browser workflow, paid Requesty request, production dataset, full native concurrency matrix or sustained load test was performed. Requesty calls and expenses: zero.

## Reproduction and evidence

See [CPU-DETECTOR-EVALUATION.md](CPU-DETECTOR-EVALUATION.md) and the benchmark requirements/Windows lock for commands and interpretation. Model: Wismut/nym-pii-multilingual revision 0ed0242d67a30ca6a83e5f118506ff1e1daf83ca, int8 bundle; inference uses CPUExecutionProvider and one thread. The adapter uses argmax BIO threshold 0.5, not upstream CLI recall_first.

Detector/component results were generated using the implementation at commit 53ad5dc. The following commit adds semantic JSON roundtrip reporting and failed-worker isolation, and regenerates the native report. All reports record their available source/environment fingerprints. Windows source-byte hashes include working-tree line endings.

- [Detector/component report](results/cpu-detector-evaluation.json)
- [Native payload report](results/cpu-native-evaluation.json)
- [Local Ollama smoke](results/ollama-smoke.json)

Reports export aggregate measurements and public artifact hashes only. They contain no fixture text, original values, detected spans, mappings, local artifact paths or credentials.
