import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('cpu_evaluation_tested',
    Path(__file__).parents[1] / 'tools/privacy_benchmark/cpu_evaluation.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_exact_typed_scoring_penalizes_partial_and_wrong_type():
    gold = [(0, 10, 'PERSON'), (20, 30, 'EMAIL')]
    result = evaluation.tally([(0, 9, 'PERSON'), (20, 30, 'PERSON')], gold)
    assert result == {'tp': 0, 'fp': 2, 'fn': 2}
    assert evaluation.scores(result)['f1'] == 0
    assert evaluation.tally(gold, gold) == {'tp': 2, 'fp': 0, 'fn': 0}


def test_percentiles_include_slow_tail():
    assert evaluation.percentile(list(range(1, 101)), .5) == 50
    assert evaluation.percentile(list(range(1, 101)), .95) == 95


def test_character_coverage_distinguishes_punctuation_from_missed_entity():
    assert evaluation.character_tally([(0, 11, 'PERSON')], [(0, 10, 'PERSON')]) == {'tp': 10, 'fp': 1, 'fn': 0}
    assert evaluation.character_tally([(0, 10, 'EMAIL')], [(0, 10, 'PERSON')]) == {'tp': 0, 'fp': 10, 'fn': 10}


def test_semantic_roundtrip_allows_only_equivalent_json():
    assert evaluation.equivalent('{"a":1}', '{"a": 1}')
    assert not evaluation.equivalent('{"a":1}', '{"a":2}')
    assert not evaluation.equivalent('a  b', 'a b')


def test_failed_worker_cannot_reuse_prior_success(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            Path(command[command.index('--output') + 1]).write_text(json.dumps({'status': 'ok'}))
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(returncode=1)
    destination = tmp_path / 'report.json'
    monkeypatch.setattr(evaluation.subprocess, 'run', execute)
    monkeypatch.setattr(evaluation.sys, 'argv', ['cpu_evaluation', '--output', str(destination),
        '--backends', 'regex', '--concurrencies', '1'])
    assert evaluation.main() == 1
    assert [row['status'] for row in json.loads(destination.read_text())['runs']] == ['ok', 'failed']


def test_all_gold_offsets_reconstruct_annotated_values_and_long_case():
    cases = evaluation.corpus()
    assert {language for language, _, _ in cases} == {'de', 'en', 'mixed'}
    assert any(len(text) > 3000 and gold for _, text, gold in cases)
    for _, text, gold in cases:
        assert all(0 <= start < end <= len(text) for start, end, _ in gold)
        assert all('{' not in text[start:end] for start, end, _ in gold)
