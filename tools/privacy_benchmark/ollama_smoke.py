"""Native privacy-wrapper smoke test against a strictly local Ollama endpoint."""
import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def run(args):
    from agent import Agent, AgentConfig
    import models
    from usr.plugins.local_privacy_guard.helpers import model_guard as guard
    from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
    parsed = urlparse(args.endpoint)
    if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1', 'host.docker.internal'} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {'', '/'}:
        raise ValueError('Only a host-local Ollama endpoint is allowed.')
    report = {'transport': 'local Ollama through real native PrivacyWrapper', 'requesty_calls': 0, 'runs': []}
    original_owner, original_mapping = guard.owner_and_config, guard.mapping_for
    try:
        with tempfile.TemporaryDirectory() as directory:
            for backend in args.backends:
                config = {'enabled': True, 'pii_filter': {'backend': backend, 'use_regex': True,
                    'use_ner': True, 'languages': ['de', 'en'], 'enabled': True, 'action': 'redact',
                    'nym_model_dir': args.model_dir, 'nym_threads': 1}}
                agent = Agent(0, AgentConfig(profile='cpu-ollama-smoke', mcp_servers=''))
                mapping = Mapping(('', backend), agent.context.id, directory)
                guard.owner_and_config = lambda unused: (agent, config)
                guard.mapping_for = lambda unused: mapping
                rows = []; sent = []
                class LocalOllama(models.LiteLLMChatWrapper):
                    async def unified_call(self, *unused, **kwargs):
                        prompt = str(kwargs.get('user_message', ''))
                        sent.append(prompt)
                        payload = {'model': args.model, 'prompt': prompt, 'stream': False,
                                   'options': {'temperature': 0, 'num_predict': 128}}
                        request = Request(args.endpoint.rstrip('/') + '/api/generate',
                            data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
                        with urlopen(request, timeout=180) as response:
                            result = json.load(response)
                        rows.append({k: result.get(k) for k in ('total_duration', 'load_duration',
                            'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration')})
                        return result['response'], ''
                inner = LocalOllama(model=args.model, provider='ollama', api_base=args.endpoint)
                data = {'result': inner}; guard.bind(data, agent)
                exact = 0; leaks = 0; latencies = []
                for text, gold in [('Meine E-Mail ist alina@example.invalid.', 'alina@example.invalid'),
                                   ('Email robin@example.invalid.', 'robin@example.invalid'),
                                   ('JSON email: alina@example.invalid. Bitte repeat exactly.', 'alina@example.invalid')]:
                    prompt = 'Repeat the following text exactly, preserving all placeholder tokens. Output only the text:\n' + text
                    started = time.perf_counter()
                    response, _ = asyncio.run(data['result'].unified_call(user_message=prompt))
                    latencies.append((time.perf_counter() - started) * 1000)
                    if gold in sent[-1]: raise ValueError('Input protection failed.')
                    leaks += gold in response
                    exact += mapping.restore(response).strip() == text
                report['runs'].append({'backend': backend, 'model': args.model, 'cases': 3,
                    'input_known_value_leaks': 0, 'output_known_value_leaks': leaks,
                    'exact_echo_after_restore': exact, 'end_to_end_ms': latencies, 'ollama_metrics': rows})
    finally:
        guard.owner_and_config, guard.mapping_for = original_owner, original_mapping
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--model', required=True)
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--backends', nargs='+', choices=['local', 'presidio', 'nym'], default=['local', 'presidio', 'nym'])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try: result = run(args)
    except Exception:
        result = {'status': 'failed', 'reason': 'Local native Ollama smoke failed; no raw exception or payload exported.'}
    Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    raise SystemExit(int(result.get('status') == 'failed'))
