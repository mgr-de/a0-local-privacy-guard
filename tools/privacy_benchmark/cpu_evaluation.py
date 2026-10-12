"""Isolated offline CPU comparison. Exports aggregates only, never text or mappings."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
from importlib.metadata import version, PackageNotFoundError
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


def modules(native=False):
    if native:
        from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter, _get_nlp
        from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
        from usr.plugins.local_privacy_guard.helpers.detection_cache import spans
        return PIIFilter, Mapping, spans, _get_nlp
    # Standalone checkout, independent of Agent Zero's global helpers package.
    spec = importlib.util.spec_from_file_location('cpu_guard', ROOT / 'helpers/__init__.py',
                                                submodule_search_locations=[str(ROOT / 'helpers')])
    package = importlib.util.module_from_spec(spec)
    sys.modules['cpu_guard'] = package
    spec.loader.exec_module(package)
    from cpu_guard.pii_detector import PIIFilter, _get_nlp
    from cpu_guard.mapping import Mapping
    from cpu_guard.detection_cache import spans
    return PIIFilter, Mapping, spans, _get_nlp


def corpus():
    # Reserved test domains, invented identities. Gold is explicit inline annotation.
    templates = {
        'de': [
            'Ich bin {PERSON:Alina Beispiel}. Meine E-Mail ist {EMAIL:alina@example.invalid}.',
            'Kontakt: {PERSON:Alina Beispiel}; Telefon {TELEFON:+49 30 55501001}.',
            '{"name":"{PERSON:Alina Beispiel}","email":"{EMAIL:alina@example.invalid}"}',
            '# Kontakt\n{PERSON:Alina Beispiel}\nE-Mail: {EMAIL:alina@example.invalid}',
            'Die Adresse ist {ADRESSE:Beispielstraße 42}.',
            'Testkonto: {IBAN:DE10500105179000000000}. Datum {DATUM:2026-10-13}.',
        ],
        'en': [
            'My name is {PERSON:Robin Example}. Email {EMAIL:robin@example.invalid}.',
            'Contact {PERSON:Robin Example} at {TELEFON:+1 202 555 0147}.',
            '{"name":"{PERSON:Robin Example}","email":"{EMAIL:robin@example.invalid}"}',
            '# Contact\n{PERSON:Robin Example}\nEmail: {EMAIL:robin@example.invalid}',
            'Send mail to {ADRESSE:42 Example Street}.',
            'Synthetic account {IBAN:DE10500105179000000000}; date {DATUM:2026-10-13}.',
        ],
        'mixed': [
            'Der contact is {PERSON:Alina Beispiel}, email {EMAIL:alina@example.invalid}.',
            'Playwright: {"owner":"{PERSON:Robin Example}","email":"{EMAIL:robin@example.invalid}"}',
            'Tool output: Kontakt {PERSON:Alina Beispiel}; response for {PERSON:Robin Example}.',
            'Context summary: {PERSON:Robin Example} und {PERSON:Alina Beispiel}.',
            'Memory: {EMAIL:robin@example.invalid}; Wiederholung {EMAIL:robin@example.invalid}.',
            'Unicode 🙂 Kontakt {PERSON:Alina Beispiel}; {EMAIL:alina@example.invalid}.',
            'Synthetic host {IP:198.51.100.42}; Test-ID {UUID:00000000-0000-4000-8000-000000000001}.',
            ('CSS HTML JSON browser tool output. ' * 100) + 'Kontakt {PERSON:Alina Beispiel}; {EMAIL:alina@example.invalid}.',
        ],
    }
    negatives = ['Playwright uses CSS and HTML.', 'Agent Zero uses JavaScript.',
                 '{"tool_name":"browser","action":"click","selector":"#submit"}',
                 'def process_json(value): return value', 'HTTP status 200; version 3.8.7; retries=3']
    cases = []
    for language, items in templates.items():
        for template in [*items, *negatives]:
            text = ''; gold = []; position = 0
            for match in re.finditer(r'\{([A-Z_]+):([^{}]+)\}', template):
                text += template[position:match.start()]
                start = len(text); text += match[2]
                gold.append((start, len(text), match[1])); position = match.end()
            text += template[position:]
            cases.append((language, text, gold))
    return cases


def normalized(hit):
    kind = {'IBAN_DE': 'IBAN', 'TELEFON_INTL': 'TELEFON', 'ADDRESS': 'ADRESSE',
            'CREDIT_CARD': 'KREDITKARTE'}.get(hit.pii_type, hit.pii_type)
    return hit.start, hit.end, kind


def tally(found, expected):
    found, expected = set(found), set(expected)
    return {'tp': len(found & expected), 'fp': len(found - expected), 'fn': len(expected - found)}


def character_tally(found, expected):
    # Supplement strict span scoring with type-matched character coverage.
    actual = {(position, kind) for start, end, kind in found for position in range(start, end)}
    gold = {(position, kind) for start, end, kind in expected for position in range(start, end)}
    return {'tp': len(actual & gold), 'fp': len(actual - gold), 'fn': len(gold - actual)}


def equivalent(first, second):
    if first == second:
        return True
    try:
        return json.loads(first) == json.loads(second)
    except (ValueError, TypeError):
        return False


def scores(counts):
    tp, fp, fn = (counts[k] for k in ('tp', 'fp', 'fn'))
    return {**counts, 'precision': tp / (tp + fp) if tp + fp else 1.,
            'recall': tp / (tp + fn) if tp + fn else 1.,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.}


def percentile(values, quantile):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def worker(args):
    import psutil
    PIIFilter, Mapping, cache, get_nlp = modules(args.native)
    native_guard = None
    if args.native:
        from agent import Agent, AgentConfig
        from usr.plugins.local_privacy_guard.helpers import model_guard as native_guard
        original_mapping_for = native_guard.mapping_for
        mappings = {}
        native_guard.mapping_for = lambda agent: mappings[agent.context.id]
    config = {'backend': 'local' if args.backend == 'regex' else args.backend,
              'use_regex': True, 'use_ner': args.backend != 'regex', 'languages': ['de', 'en'],
              'presidio_variant': args.presidio_variant, 'nym_model_dir': args.model_dir,
              'nym_threads': args.threads, 'nym_threshold': args.threshold}
    process = psutil.Process()
    rss = [process.memory_info().rss]
    stop = threading.Event()
    def sample():
        while not stop.wait(.01):
            rss.append(process.memory_info().rss)
    sampler = threading.Thread(target=sample, daemon=True); sampler.start()
    started = time.perf_counter()
    try:
        first = PIIFilter(config)
        if config['use_ner'] and args.backend != 'nym':
            if any(get_nlp(lang) is None for lang in ('de', 'en')):
                raise ValueError('Missing spaCy language model.')
        load_seconds = time.perf_counter() - started
        first.filter('CSS HTML JSON')  # Warm runtime kernel; exclude from steady timing.
        cases = corpus(); quality = {}; character_quality = {}; type_counts = {}; roundtrips = 0; semantic_roundtrips = 0; leak_cases = 0
        for language, text, gold in cases:
            result = first.filter(text)
            counts = tally([normalized(h) for h in result.detections], gold)
            row = quality.setdefault(language, dict(tp=0, fp=0, fn=0))
            for k, v in counts.items(): row[k] += v
            character_counts = character_tally([normalized(h) for h in result.detections], gold)
            row = character_quality.setdefault(language, dict(tp=0, fp=0, fn=0))
            for k, v in character_counts.items(): row[k] += v
            for kind in {x[2] for x in gold} | {normalized(h)[2] for h in result.detections}:
                count = tally([normalized(h) for h in result.detections if normalized(h)[2] == kind],
                              [h for h in gold if h[2] == kind])
                row = type_counts.setdefault(kind, dict(tp=0, fp=0, fn=0))
                for k, v in count.items(): row[k] += v
        cache.clear_scope(first.scope)
        samples = []
        with tempfile.TemporaryDirectory() as directory:
            def run_task(job):
                # Own scope/vault/filter per concurrent client. Shared Nym session is serialized.
                filt = PIIFilter({**config, '_cache_scope': 'cpu-' + str(job)})
                mapping = Mapping(('', 'cpu-test'), str(job), directory)
                if args.native:
                    agent = Agent(0, AgentConfig(profile='cpu-evaluation', mcp_servers=''))
                    mappings[agent.context.id] = mapping
                    pipeline_config = {'pii_filter': {**config, 'enabled': True, 'action': 'redact'}}
                    filt.scope = mapping.namespace
                if args.cache == 'warm':
                    for _, text, _ in cases:
                        if args.native:
                            native_guard.PayloadFilter(agent, pipeline_config, False).text(text)
                        else: filt.filter(text)
                local_samples = []; local_roundtrips = local_semantic_roundtrips = local_leaks = 0
                native_metrics = dict(filt.metrics)
                try:
                    for _ in range(args.repeats):
                        for language, text, gold in cases:
                            if args.cache == 'cold': cache.clear_scope(filt.scope)
                            tick = time.perf_counter()
                            if args.native:
                                pipeline = native_guard.PayloadFilter(agent, pipeline_config, False)
                                payload = {'system_message': text, 'tool_output': text, 'memory': text, 'summary': text}
                                masked_payload = pipeline.value(payload)
                                result = None
                            else:
                                result = filt.filter(text)
                            detection_seconds = time.perf_counter() - tick
                            tick = time.perf_counter()
                            if args.native:
                                masked = masked_payload['summary']
                            else:
                                hits = sorted(result.detections, key=lambda h: h.start, reverse=True)
                                tokens = mapping.token_many([(h.pii_type, h.original, None) for h in hits])
                                masked = text
                                for hit, token in zip(hits, tokens):
                                    masked = masked[:hit.start] + token + masked[hit.end:]
                            mapping_seconds = time.perf_counter() - tick
                            # Deterministic local transport echoes masked input; response is independently checked.
                            tick = time.perf_counter(); response = masked; transport_seconds = time.perf_counter() - tick
                            tick = time.perf_counter()
                            if args.native:
                                output_pipeline = native_guard.PayloadFilter(agent, pipeline_config, False)
                                response = output_pipeline.text(str(response))
                                output_count = output_pipeline.detected_count
                            else:
                                output = filt.filter(re.sub(r'\[LPG_[^\]]+\]', lambda m: ' ' * len(m[0]), response))
                                output_count = len(output.detections)
                            output_seconds = time.perf_counter() - tick
                            # Output leaks are separately counted; timing uses detection, no generated text.
                            tick = time.perf_counter(); restored = mapping.restore(response)
                            restore_seconds = time.perf_counter() - tick
                            exact = restored == text
                            semantic = equivalent(restored, text)
                            if args.native:
                                # Restore text values before JSON escaping, as native display does.
                                # Restoring a serialized container could inject unescaped quotes.
                                exact = exact and {k: mapping.restore(str(v)) for k, v in masked_payload.items()} == payload
                                semantic = semantic and all(equivalent(mapping.restore(str(v)), payload[k]) for k, v in masked_payload.items())
                            local_roundtrips += exact
                            local_semantic_roundtrips += semantic
                            leak_target = json.dumps(masked_payload) if args.native else masked
                            local_leaks += any(text[a:b] in leak_target for a, b, _ in gold)
                            local_samples.append({'input': detection_seconds, 'mapping': mapping_seconds,
                                'transport': transport_seconds, 'output': output_seconds, 'restore': restore_seconds,
                                'total': detection_seconds + mapping_seconds + transport_seconds + output_seconds + restore_seconds,
                                'output_detections': output_count})
                            if args.native:
                                for active_filter in (pipeline.filter, output_pipeline.filter):
                                    for key, value in active_filter.metrics.items(): native_metrics[key] += value
                finally:
                    cache.clear_scope(filt.scope)
                return local_samples, local_roundtrips, local_leaks, native_metrics if args.native else dict(filt.metrics), dict(mapping.metrics), local_semantic_roundtrips
            cpu_start = sum(process.cpu_times()[:2]); start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                results = list(pool.map(run_task, range(args.concurrency)))
            wall = time.perf_counter() - start; cpu = sum(process.cpu_times()[:2]) - cpu_start
            for values, trips, leaks, _, _, semantic_trips in results:
                samples.extend(values); roundtrips += trips; semantic_roundtrips += semantic_trips; leak_cases += leaks
        packages = {}
        for name in ('numpy', 'onnxruntime', 'tokenizers', 'spacy', 'presidio-analyzer', 'psutil', 'en-core-web-sm', 'de-core-news-sm'):
            try: packages[name] = version(name)
            except PackageNotFoundError: packages[name] = None
        timings = {stage: {'p50_ms': percentile([s[stage] for s in samples], .5) * 1000,
                           'p95_ms': percentile([s[stage] for s in samples], .95) * 1000}
                   for stage in ('input', 'mapping', 'transport', 'output', 'restore', 'total')}
        return {'status': 'ok', 'backend': args.backend, 'presidio_variant': args.presidio_variant,
            'cache': args.cache, 'concurrency': args.concurrency, 'threads': args.threads,
            'threshold': args.threshold, 'load_seconds': load_seconds, 'cases': len(cases),
            'samples': len(samples), 'quality_exact_typed_spans': {k: scores(v) for k, v in quality.items()},
            'quality_typed_characters': {k: scores(v) for k, v in character_quality.items()},
            'quality_by_type': {k: scores(v) for k, v in type_counts.items()}, 'latency': timings,
            'cpu_seconds': cpu, 'wall_seconds': wall, 'cpu_percent_one_core': 100 * cpu / wall,
            'rss_peak_sampled_bytes': max(rss + [process.memory_info().rss]),
            'throughput_cases_per_second': len(samples) / wall,
            'roundtrips_exact': roundtrips, 'roundtrips_semantic': semantic_roundtrips, 'cases_with_known_value_leak': leak_cases,
            'output_false_positive_detections': sum(s['output_detections'] for s in samples),
            'detector_metrics': [r[3] for r in results], 'mapping_metrics': [r[4] for r in results],
            'environment': {'python': platform.python_version(), 'os': platform.system(),
                            'cpu_count': os.cpu_count(), 'cpu_physical_count': psutil.cpu_count(logical=False),
                            'processor': platform.processor(), 'ram_bytes': psutil.virtual_memory().total,
                            'packages': packages},
            'implementation_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                ('helpers/pii_detector.py', 'helpers/nym_backend.py', 'helpers/presidio_backend.py',
                 'helpers/model_guard.py', 'helpers/mapping.py', 'tools/privacy_benchmark/cpu_evaluation.py')},
            'inference_settings': {'languages': ['de', 'en'], 'use_regex': True,
                                   'nym_max_tokens': 512, 'nym_stride': 64},
            'artifact': first.nym_model.identity if args.backend == 'nym' else None,
            'corpus_sha256': hashlib.sha256(json.dumps(cases, ensure_ascii=False).encode()).hexdigest(),
            'llm_calls': 0, 'pipeline': ('native PayloadFilter over system/tool/memory/summary + simulated echo + native output check'
                if args.native else 'detector + production Mapping + simulated echo + output detector; not native gateway'),
            'timing_note': 'native input includes mapping; mapping stage is only standalone. CPU/wall include task setup and warmup.'}
    finally:
        stop.set(); sampler.join()
        if native_guard is not None: native_guard.mapping_for = original_mapping_for


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--backends', nargs='+', choices=['regex', 'local', 'presidio', 'nym'], default=['regex', 'local', 'presidio', 'nym'])
    parser.add_argument('--concurrencies', nargs='+', type=int, default=[1, 2, 4])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--threshold', type=float, default=.5)
    parser.add_argument('--presidio-variant', choices=['A', 'B'], default='B')
    parser.add_argument('--model-dir')
    parser.add_argument('--backend', choices=['regex', 'local', 'presidio', 'nym'])
    parser.add_argument('--concurrency', type=int, default=1)
    parser.add_argument('--cache', choices=['cold', 'warm'], default='cold')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--native', action='store_true', help='Use real PayloadFilter in Agent Zero environment; transport remains simulated')
    args = parser.parse_args()
    if args.repeats < 1 or any(c < 1 for c in args.concurrencies) or args.concurrency < 1:
        parser.error('repeats and concurrency must be positive')
    if args.worker:
        try: result = worker(args)
        except Exception: result = {'status': 'failed', 'reason': 'Dependency, model or evaluation failure; no results inferred.'}
        Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
        return 0 if result['status'] == 'ok' else 1
    report = {'schema': 1, 'runs': []}
    with tempfile.TemporaryDirectory() as directory:
        for backend in args.backends:
            for concurrency in args.concurrencies:
                for cache in ('cold', 'warm'):
                    output = Path(directory) / 'worker.json'
                    output.unlink(missing_ok=True)
                    command = [sys.executable, __file__, '--worker', '--output', str(output),
                               '--backend', backend, '--concurrency', str(concurrency), '--cache', cache,
                               '--threads', str(args.threads), '--repeats', str(args.repeats),
                               '--threshold', str(args.threshold), '--presidio-variant', args.presidio_variant]
                    if args.model_dir: command += ['--model-dir', args.model_dir]
                    if args.native: command += ['--native']
                    # Never publish exception output which may contain local paths or input values.
                    environment = {**os.environ, 'OMP_NUM_THREADS': str(args.threads),
                                   'OPENBLAS_NUM_THREADS': str(args.threads), 'MKL_NUM_THREADS': str(args.threads)}
                    try:
                        completed = subprocess.run(command, capture_output=True, timeout=3600, env=environment)
                    except subprocess.TimeoutExpired:
                        report['runs'].append({'backend': backend, 'concurrency': concurrency, 'cache': cache,
                                               'status': 'failed', 'reason': 'worker timed out'})
                        continue
                    result = json.loads(output.read_text()) if output.exists() else {'status': 'failed'}
                    if completed.returncode != 0 and result.get('status') == 'ok':
                        result = {'status': 'failed', 'reason': 'worker exited unsuccessfully'}
                    report['runs'].append({'backend': backend, 'concurrency': concurrency, 'cache': cache, **result})
                    print(backend, concurrency, cache, result['status'], flush=True)
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    return int(any(r['status'] != 'ok' for r in report['runs']))


if __name__ == '__main__':
    raise SystemExit(main())
