# Optional CPU detector evaluation

The production default remains `backend: local`. Routes, browser behavior, media boundaries, secret blocking and the persistent mapping implementation are unchanged. `backend: nym` is an expert configuration option for DE/EN/mixed evaluation, not a new default. There is no download or automatic fallback in model request processing.

Nym uses CPUExecutionProvider only, one shared serialized ONNX session, bounded thread settings, BIO label decoding, absolute Unicode character offsets and overlapping token windows. Every nonempty paragraph is covered, including overflow windows. It uses the same paragraph boundary, span cache, regex precedence, nonentity exclusions and production mapping as existing backends. Unsupported Nym categories map to `CUSTOM`; name/address/date categories map to existing local types. The Nym multilingual model processes each paragraph once rather than running separate language-specific models.

Decoding selects each token's highest-probability BIO label with a configurable confidence threshold. For overlap duplicates it selects the prediction furthest from the window edge, repairs orphan I tags and joins adjacent given-name/surname spans. This adapter does not reproduce the upstream CLI's optional total-entity-mass `recall_first` mode; upstream benchmark claims are not imported into these results.

## Reproduce offline

Use a dedicated Python 3.12 or 3.13 environment; never install evaluation dependencies into a running server. From this repository:

```sh
python -m pip install -r tools/privacy_benchmark/requirements-cpu-evaluation.txt
python tools/privacy_benchmark/prepare_nym.py --destination /absolute/local/nym-int8
python tools/privacy_benchmark/cpu_evaluation.py --model-dir /absolute/local/nym-int8 --output cpu-results.json --repeats 10 --concurrencies 1 2 4
```

The committed `tools/privacy_benchmark/requirements-cpu-evaluation-windows.lock.txt` records all resolved packages for the Windows/Python 3.13 run, including hashed spaCy model URLs. Use that lock for the matching platform; the smaller requirements file pins direct dependencies for other supported environments. Reports record the actual environment.

The setup command explicitly downloads `Wismut/nym-pii-multilingual` revision `0ed0242d67a30ca6a83e5f118506ff1e1daf83ca`, defaults to its `int8/` artifact and records SHA256 for model/config/tokenizer. `--variant fp32` prepares the larger root bundle. Runtime verifies all three checksums before loading. This detects local corruption; the immutable upstream revision is the download trust anchor. Keep weights and manifests outside Git. `nym_model_dir` must point to that directory. Restart after replacing weights.

```yaml
pii_filter:
  backend: nym
  languages: [de, en]
  use_regex: true
  use_ner: true
  nym_model_dir: /absolute/local/nym-int8
  nym_threads: 1
  nym_max_tokens: 512
  nym_stride: 64
  nym_threshold: 0.5
```

Run Presidio A separately with `--presidio-variant A`. B retains its supplemental structured recognizers. All comparisons retain built-in regex by default; `regex` measures regex alone. Changing threshold, variant or model invalidates Nym span reuse. Missing artifacts/dependencies, unsupported language/labels, invalid settings and inference failures stop detection with sanitized errors.

## Measurements and limits

Each backend/cache/concurrency combination runs in a fresh subprocess. Reports include package versions, artifact revision and hashes, corpus hash, load time, exact typed-span precision/recall/F1 per language/type, detector/input/mapping/simulated transport/output/restore/total latency p50/p95, process CPU seconds and percent of one core, sampled peak RSS, throughput, cache/SQL metrics, exact roundtrips and known-value leaks. RSS is sampled every 10 ms and can miss short peaks. CPU/wall include task initialization and warmup; latency samples exclude these. Cold clears detector cache per input; warm primes fixture paragraphs. Repetitions are not independent quality samples.

The small explicit synthetic corpus covers DE/EN/mixed prose, JSON, Markdown, technical negatives, system/tool/memory/summary examples, repeated entities, Unicode, addresses, IBAN/date/IP/UUID and long paragraphs. Exact scoring intentionally penalizes partial spans, punctuation and type differences. A missed entity can still roundtrip perfectly: leak counts and recall must be reviewed alongside roundtrips. No claim about real-world accuracy follows from this corpus.

Type-matched character precision/recall/F1 supplement strict span scoring, so punctuation overreach can be distinguished from missed coverage. Synthetic surnames such as `Beispiel`/`Example` deliberately stress ambiguous technical text; this corpus is not a representative population sample.

Standalone runs exercise production `Mapping`, with a deterministic echo transport and separate output detection. In a native Agent Zero checkout, add `--native` to exercise real `PayloadFilter.value` on system/tool/memory/summary fields and `PayloadFilter.text` on outputs. Native input timing includes mapping; its separate mapping column does not measure native database time (use mapping metrics). Both modes make zero LLM/provider calls. The native mode is still a simulated transport, not a live browser or Ollama chat.

Use isolated copies of all three plugins in a clean Agent Zero source checkout for native tests. Do not point tests at live user configuration. The existing native suites cover routing, history, callback buffering, structured tools, subordinate scope, images, mapping ownership and policy. Run each plugin's pytest suite separately because some filenames collide. Set `NYM_TEST_MODEL_DIR` to include the real ONNX overflow/roundtrip test. The new companion tests verify backend configuration survives the instance floor and cannot add route privileges.

For an actual cost-free local model smoke in that isolated native environment:

```sh
python tools/privacy_benchmark/ollama_smoke.py --endpoint http://127.0.0.1:11434 --model granite4:tiny-h --model-dir /absolute/local/nym-int8 --output ollama-results.json
```

This sends synthetic masked prompts through real `PrivacyWrapper` instances to the local Ollama API, then checks outputs before restoration. It makes three calls per selected backend (nine by default), caps each generated reply at 128 tokens, and exports timings, leak counts, exact-echo checks and Ollama counters. A model need not echo perfectly; semantic answers and tool execution are not evaluated by this smoke. Use an already installed model. The endpoint validator rejects remote hosts and URL credentials. Docker may use `http://host.docker.internal:11434` to reach host Ollama.

Reports contain aggregates only, not fixture strings, original values, detected spans, mapping rows, vaults, credentials or local artifact paths. Failures are explicit and no measurements are invented. Requesty is never called by this harness. Live paid testing requires a separately established budget.

Model documentation: https://huggingface.co/Wismut/nym-pii-multilingual
