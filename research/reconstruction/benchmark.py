from __future__ import annotations

from dataclasses import asdict
from itertools import product
from pathlib import Path
from fractions import Fraction
from statistics import mean
import argparse
import hashlib
import json
import random
import time

from .engine import Frame, parse_frame, render, reconstruct_frames, edit_distance
from .planner import Alternative, DEFAULT_VIEWS, reference, residual_counts, objective, words

SEED = 27112401
BENCHMARK_ID = 'reconstruction-geometry-sanity-v1'


def _metric(text, refs, sizes, cost, path):
    return objective(residual_counts(text, refs, DEFAULT_VIEWS), sizes, cost, tuple(path))


def _greedy(source, lattice, budget):
    refs, sizes = reference(source, DEFAULT_VIEWS)
    chosen = tuple(next(i for i, a in enumerate(row) if a.cost == 0) for row in lattice)
    current = _metric(source, refs, sizes, 0, chosen)
    evaluations = 1
    while True:
        best = None
        for position, row in enumerate(lattice):
            for choice, alternative in enumerate(row):
                path = list(chosen)
                path[position] = choice
                cost = sum(lattice[i][j].cost for i, j in enumerate(path))
                if cost > budget:
                    continue
                text = ' '.join(lattice[i][j].text for i, j in enumerate(path))
                score = _metric(text, refs, sizes, cost, path)
                evaluations += 1
                if score < current and (best is None or score < best[0]):
                    best = (score, tuple(path), text)
        if best is None:
            output = ' '.join(lattice[i][j].text for i, j in enumerate(chosen))
            return current, output, evaluations
        current, chosen, output = best


def _exhaustive(source, lattice, budget):
    refs, sizes = reference(source, DEFAULT_VIEWS)
    best = None
    for path in product(*(range(len(row)) for row in lattice)):
        cost = sum(lattice[i][j].cost for i, j in enumerate(path))
        if cost > budget:
            continue
        text = ' '.join(lattice[i][j].text for i, j in enumerate(path))
        score = _metric(text, refs, sizes, cost, path)
        if best is None or score < best:
            best = score
    return best


def fixtures(count):
    rng = random.Random(SEED)
    combinations = [('revenue','USD'),('cost','EUR'),('distance','km'),('duration','hours'),('mass','kg')]
    for index in range(count):
        sentences = []
        for _ in range(rng.randint(2, 5)):
            metric, unit = rng.choice(combinations)
            frame = Frame(rng.choice(['Orion Labs','Vega Systems','Nova7','Atlas Group','Helix Research']),
                          metric, f'{rng.randint(1,999)}.{rng.randint(0,99):02d}', unit,
                          str(rng.randint(2000,2025)), rng.random() < .25)
            sentences.append(render(frame)[rng.randrange(4)])
        yield f'grammar-{index:04d}', tuple(sentences), rng.choice([6,12,18,24,30])


def run(count=128, exhaustive_count=24):
    if count < 1 or count > 4096 or exhaustive_count < 0 or exhaustive_count > count:
        raise ValueError('invalid benchmark bounds')
    start = time.perf_counter()
    rows = []
    checked = 0
    for index, (identity, segments, budget) in enumerate(fixtures(count)):
        source = ' '.join(segments)
        frames = tuple(parse_frame(s) for s in segments)
        lattice = tuple(tuple(Alternative(t,edit_distance(words(s),words(t)),str(i)) for i,t in enumerate(render(f))) for s,f in zip(segments,frames,strict=True))
        result = reconstruct_frames(segments, budget=budget)
        if result.plan is None:
            raise AssertionError(f'bounded benchmark hit a search limit: {identity}')
        p = result.plan
        greedy, greedy_text, evaluations = _greedy(source, lattice, budget)
        if p.objective > greedy:
            raise AssertionError('exact search is worse than its own greedy baseline')
        brute_ok = None
        if index < exhaustive_count:
            brute_ok = p.objective == _exhaustive(source,lattice,budget)
            if not brute_ok:
                raise AssertionError('optimality check failed')
            checked += 1
        row = {
            'id':identity,'source':source,'output':result.text,'budget':budget,
            'status':result.status,'source_frames':[asdict(f) for f in frames],
            'source_windows':list(p.source_counts),'output_shared_windows':list(p.shared_counts),
            'worst_source_retention':str(p.objective[0]),
            'greedy_worst_source_retention':str(greedy[0]),
            'joint_cost':p.edit_cost,'greedy_cost':greedy[2],
            'greedy_output':greedy_text,'states_evaluated':p.states_evaluated,
            'states_pruned':p.states_pruned,'greedy_evaluations':evaluations,
            'exhaustive_agreement':brute_ok,'receipt':result.receipt(),
        }
        rows.append(row)
    joint = [float(Fraction(r['worst_source_retention'])) for r in rows]
    greedy = [float(Fraction(r['greedy_worst_source_retention'])) for r in rows]
    strict = sum(Fraction(r['worst_source_retention']) < Fraction(r['greedy_worst_source_retention']) for r in rows)
    view_retention = [mean(r['output_shared_windows'][i]/max(1,r['source_windows'][i]) for r in rows) for i in range(len(DEFAULT_VIEWS))]
    numeric_signature = json.dumps(rows, sort_keys=True, separators=(',',':'), ensure_ascii=True).encode()
    return {
        'benchmark_id':BENCHMARK_ID, 'seed':SEED, 'samples':count,
        'corpus_kind':'synthetic controlled-grammar reports, NOT LLM-generated watermarked text',
        'measurement_kind':'source-window retention proxy, NOT watermark detection',
        'generation_uses_watermark':False,'watermark_detector_run':False,
        'prior_frozen_corpora_used':False,'selection_detector_queries':0,
        'baseline':'full-text one-coordinate greedy over the identical alternatives and edit budget; not the historical FuckMark scheduler',
        'views':[v.name for v in DEFAULT_VIEWS],
        'summary':{
            'changed':sum(r['status']=='changed' for r in rows),
            'unchanged':sum(r['status']=='unchanged' for r in rows),
            'ordered_frame_checks_passed':count,
            'exact_search_better_worst_retention_than_greedy':strict,
            'exact_search_tied_worst_retention_with_greedy':count-strict,
            'mean_worst_retention_joint':mean(joint),
            'mean_worst_retention_greedy':mean(greedy),
            'mean_retention_per_view':view_retention,
            'exhaustive_comparisons_passed':checked,
            'max_states_evaluated':max(r['states_evaluated'] for r in rows),
            'total_states_pruned':sum(r['states_pruned'] for r in rows),
        },
        'rows_sha256':hashlib.sha256(numeric_signature).hexdigest(),
        'elapsed_seconds':time.perf_counter()-start,
        'rows':rows,
    }


def main():
    parser=argparse.ArgumentParser(description='Geometry sanity only; no watermark-removal rate is measured')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=128)
    parser.add_argument('--exhaustive',type=int,default=24)
    args=parser.parse_args()
    report=run(args.samples,args.exhaustive)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=True,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},sort_keys=True,indent=2))


if __name__=='__main__':
    main()
