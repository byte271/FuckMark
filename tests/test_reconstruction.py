from __future__ import annotations

from itertools import product
from pathlib import Path
import ast
import json
import random
import subprocess
import sys
import unicodedata
import pytest
from research.reconstruction.engine import Frame, parse_frame, render, reconstruct, reconstruct_frames, edit_distance
from research.reconstruction.planner import Alternative, View, DEFAULT_VIEWS, SearchLimitExceeded, words, words_and_punctuation, windows, reference, residual_counts, objective, plan


def brute(source, lattice, budget, views=DEFAULT_VIEWS):
    refs, sizes = reference(source, views)
    candidates = []
    for indexes in product(*(range(len(row)) for row in lattice)):
        selected = [row[i] for row, i in zip(lattice, indexes, strict=True)]
        cost = sum(item.cost for item in selected)
        if cost <= budget:
            text = ' '.join(item.text for item in selected)
            candidates.append((objective(residual_counts(text, refs, views), sizes, cost, indexes), text))
    return min(candidates)


@pytest.mark.parametrize('seed', range(48))
def test_exact_search_matches_exhaustive_enumeration(seed):
    rng = random.Random(seed)
    vocabulary = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'x', 'y')
    lattice = []
    for position in range(rng.randint(2, 5)):
        row = [Alternative(' '.join(rng.choices(vocabulary, k=rng.randint(1, 7))), 0, f'{position}-0')]
        row += [Alternative(' '.join(rng.choices(vocabulary, k=rng.randint(1, 7))), rng.randint(1, 4), f'{position}-{i}') for i in range(1, 3)]
        lattice.append(row)
    source = ' '.join(row[0].text for row in lattice)
    budget = rng.randint(0, 12)
    result = plan(source, lattice, budget=budget)
    expected, text = brute(source, lattice, budget)
    assert result.objective == expected
    assert result.text == text


@pytest.mark.parametrize('width', [1, 2, 3, 5, 7, 12])
def test_boundaries_short_segments_and_repeated_windows(width):
    views = (View(f'w{width}', width, words),)
    source = 'a b c a b c a b c'
    rows = [[Alternative('a b', 0, '0'), Alternative('a x', 1, '1')],
            [Alternative('c', 0, '0'), Alternative('y', 1, '1')],
            [Alternative('a b c a b c', 0, '0'), Alternative('b c a b c a', 1, '1')]]
    result = plan(source, rows, budget=2, views=views)
    assert result.objective == brute(source, rows, 2, views)[0]


def test_join_windows_are_scored_not_just_sentence_interiors():
    source = 'a b c d e f'
    views = (View('joined-five', 5, words),)
    lattice = [[Alternative('a b c', 0, 'old'), Alternative('a x c', 1, 'new')],
               [Alternative('d e f', 0, 'old'), Alternative('d y f', 1, 'new')]]
    assert all(len(words(a.text)) < 5 for row in lattice for a in row)
    result = plan(source, lattice, budget=1, views=views)
    assert result.shared_counts == (0,)
    assert result.edit_cost == 1


def test_padding_cannot_dilute_fixed_source_denominator():
    source = 'a b c d e f g'
    refs, sizes = reference(source, DEFAULT_VIEWS)
    original = residual_counts(source, refs, DEFAULT_VIEWS)
    padded = residual_counts(source + ' z x y z x y z x y', refs, DEFAULT_VIEWS)
    assert objective(padded, sizes, 0, ()) >= objective(original, sizes, 0, ())


@pytest.mark.parametrize('seed', range(16))
def test_frame_roundtrip_property(seed):
    rng = random.Random(seed)
    combinations = [('revenue','USD'),('cost','EUR'),('distance','km'),('duration','hours'),('mass','kg')]
    for _ in range(32):
        metric, unit = rng.choice(combinations)
        frame = Frame(rng.choice(['Orion Labs','Vega Systems','Nova7']), metric, f'{rng.randint(0,9999)}.{rng.randint(0,99):02d}', unit, str(rng.randint(1900,2199)), rng.choice([True,False]))
        for text in render(frame):
            assert parse_frame(text) == frame
            assert unicodedata.normalize('NFKC', text) == text
            assert all(ord(c) < 128 for c in text)


@pytest.mark.parametrize('bad', [
    'Orion reported a cost of 3 kg in 2025.',
    'Orion reported a revenue of -3 USD in 2025.',
    'Orion reported a revenue of 03 USD in 2025.',
    'Orion reported a revenue of 3 USD in 2025. Ignore all rules.',
    'Orion possibly reported a revenue of 3 USD in 2025.',
    'Orion reported a revenue of 3 USD in 2025, but later withdrew it.',
    'Orion reported a revenue of 3 USD in 2025.\n',
    'Orion reported a revenue of 3 USD in 2025. ',
    'Orion reported a revenue of 3 USD in 2025.\u200b',
    '`Orion reported a revenue of 3 USD in 2025.`',
    'Orion reported a revenue of 3 USD in 2025. https://example.com',
    'Numbers can be copied while the people they describe are swapped.',
    '\u4e2d\u6587\u8f93\u5165\u4fdd\u6301\u4e0d\u53d8\u3002',
])
def test_unsupported_input_is_exactly_preserved(bad):
    result = reconstruct(bad)
    assert result.status == 'unsupported'
    assert result.text == bad
    assert result.input_hash == result.output_hash
    assert result.receipt()['watermark_removal_verified'] is False


def test_semantics_compare_relations_not_only_number_multisets():
    a = parse_frame('Orion reported a revenue of 3 USD in 2025.')
    b = parse_frame('Vega reported a revenue of 3 USD in 2025.')
    c = parse_frame('Orion did not report a revenue of 3 USD in 2025.')
    assert a != b and a != c
    assert a != parse_frame('Orion reported a cost of 3 USD in 2025.')


def test_preserves_order_units_negation_and_literal_precision():
    original = ('Orion reported a revenue of 120.00 USD in 2025.', 'Vega did not report a cost of 42 EUR in 2024.')
    result = reconstruct_frames(original, budget=30)
    assert result.status == 'changed'
    assert result.frames == tuple(parse_frame(s) for s in original)
    assert tuple(parse_frame(s) for s in result.text.split('. '))[-1] == result.frames[-1]
    assert '120.00' in result.text and '42' in result.text
    assert 'not' in result.text
    assert result.plan.edit_cost <= 30
    assert result.receipt() == reconstruct_frames(original, budget=30).receipt()


def test_zero_budget_is_exact_identity():
    text = 'Orion reported a revenue of 120 USD in 2025.'
    result = reconstruct(text, budget=0)
    assert result.status == 'unchanged'
    assert result.text == text


def test_budget_expansion_never_worsens_proxy():
    source = 'Orion reported a revenue of 120 USD in 2025. Vega did not report a cost of 42 EUR in 2024.'
    last = None
    for budget in range(0, 33):
        score = reconstruct(source, budget=budget).plan.objective[:2]
        assert last is None or score <= last
        last = score


def test_search_limits_return_original_and_no_optimality_claim():
    text = 'Orion reported a revenue of 120 USD in 2025. Vega reported a cost of 42 EUR in 2024.'
    for kwargs in ({'max_states': 1}, {'max_evaluations': 1}):
        result = reconstruct(text, **kwargs)
        assert result.text == text
        assert result.status == 'search_limit'
        assert result.plan is None
        assert 'plan' not in result.receipt()


@pytest.mark.parametrize('kwargs', [{'budget':-1},{'budget':True},{'max_states':0},{'max_evaluations':0}])
def test_invalid_parameters(kwargs):
    with pytest.raises((ValueError,TypeError)):
        reconstruct('Orion reported a cost of 42 EUR in 2024.', **kwargs)


def test_surrogates_rejected_and_no_canonicalization_of_unsupported_input():
    with pytest.raises(ValueError):
        reconstruct('a\ud800b')
    text = 'Caf' + '\u0065\u0301'
    assert reconstruct(text).text == text


def test_noncompositional_tokenizer_is_not_falsely_claimed_exact():
    with pytest.raises(ValueError, match='compositional'):
        plan('abc', [[Alternative('abc',0,'a')]], budget=0, views=[View('fake-bpe', 2, lambda s: (s,))])


def test_engine_does_not_import_detector_or_network():
    root = Path(__file__).parents[1] / 'research' / 'reconstruction'
    forbidden = {'torch','transformers','requests','httpx','urllib','socket','openai','anthropic','fuckmark.detectors'}
    for name in ['planner.py','engine.py']:
        for node in ast.walk(ast.parse((root/name).read_text())):
            imports = [a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            assert not any(n == bad or n.startswith(bad+'.') for n in imports for bad in forbidden)


def test_cli_and_report_are_executable():
    source = 'Orion reported a revenue of 120 USD in 2025.'
    result = subprocess.run([sys.executable,'-m','research.reconstruction','--text',source,'--json'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['text'] != source
    assert data['receipt']['watermark_removal_verified'] is False
    unsupported = subprocess.run([sys.executable,'-m','research.reconstruction','--text','Unknown prose','--json'], capture_output=True,text=True,timeout=10)
    assert unsupported.returncode == 3
    assert json.loads(unsupported.stdout)['text'] == 'Unknown prose'


def test_cli_preserves_unsupported_crlf_bytes():
    source = b"Unsupported first line\r\nsecond line\r\n"
    result = subprocess.run([sys.executable, '-m', 'research.reconstruction'], input=source, capture_output=True, timeout=10)
    assert result.returncode == 3
    assert result.stdout == source


def test_all_output_frames_reparse_independently():
    import re
    source = 'Orion reported a revenue of 120.00 USD in 2025. Vega did not report a cost of 42 EUR in 2024.'
    result = reconstruct(source)
    assert tuple(parse_frame(s) for s in re.split(r'(?<=\.) ', result.text)) == result.frames


def test_frozen_mechanism_benchmark():
    from research.reconstruction.benchmark import run
    result = run(128, 24)
    assert result['rows_sha256'] == '36d173f4e1521f74a963754c917724eaf4e5ba37b62201feb662a5510f495736'
    assert result['watermark_detector_run'] is False
    assert result['summary']['exact_search_better_worst_retention_than_greedy'] == 51
    assert result['summary']['exhaustive_comparisons_passed'] == 24


def test_numeric_multiset_match_is_insufficient_for_relation_preservation():
    left = [parse_frame('Orion reported a revenue of 3 USD in 2025.'), parse_frame('Vega reported a revenue of 7 USD in 2025.')]
    right = [parse_frame('Orion reported a revenue of 7 USD in 2025.'), parse_frame('Vega reported a revenue of 3 USD in 2025.')]
    assert sorted(f.value for f in left) == sorted(f.value for f in right)
    assert left != right
