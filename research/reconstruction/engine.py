from __future__ import annotations

from dataclasses import dataclass, asdict
from collections import Counter
import hashlib
import json
import re
import unicodedata
from .planner import Alternative, DEFAULT_VIEWS, Plan, SearchLimitExceeded, plan, words

VERSION = 'constraint-first-reconstruction-v1'
_ENTITY = r'[A-Z][A-Za-z0-9]*(?: [A-Z][A-Za-z0-9]*){0,4}'
_VALUE = r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?'
_YEAR = r'(?:19|20|21)[0-9]{2}'
_METRIC_UNITS = {
    'revenue': frozenset({'USD', 'EUR', 'GBP', 'CNY'}),
    'cost': frozenset({'USD', 'EUR', 'GBP', 'CNY'}),
    'distance': frozenset({'km', 'm'}),
    'duration': frozenset({'hours', 'minutes', 'seconds'}),
    'mass': frozenset({'kg', 'g'}),
}
_METRIC = '(?:' + '|'.join(_METRIC_UNITS) + ')'
_UNIT = '(?:' + '|'.join(sorted(set().union(*_METRIC_UNITS.values()))) + ')'
_PREDICATE = r'(?:reported|did not report)'
_STATIVE = r'(?:was reported|was not reported)'
_COMMON = rf'(?P<metric>{_METRIC}) of (?P<value>{_VALUE}) (?P<unit>{_UNIT})'
_PATTERNS = (
    re.compile(rf'(?P<entity>{_ENTITY}) (?P<verb>{_PREDICATE}) a {_COMMON} in (?P<year>{_YEAR})\.'),
    re.compile(rf'In (?P<year>{_YEAR}), (?P<entity>{_ENTITY}) (?P<verb>{_PREDICATE}) a {_COMMON}\.'),
    re.compile(rf'A {_COMMON} (?P<state>{_STATIVE}) by (?P<entity>{_ENTITY}) in (?P<year>{_YEAR})\.'),
    re.compile(rf'In (?P<year>{_YEAR}), a {_COMMON} (?P<state>{_STATIVE}) by (?P<entity>{_ENTITY})\.'),
)


@dataclass(frozen=True)
class Frame:
    entity: str
    metric: str
    value: str
    unit: str
    year: str
    negated: bool = False

    def __post_init__(self):
        if not all(isinstance(x, str) for x in (self.entity, self.metric, self.value, self.unit, self.year)):
            raise TypeError('fact fields must be strings')
        if not re.fullmatch(_ENTITY, self.entity):
            raise ValueError('unsupported entity')
        if self.metric not in _METRIC_UNITS or self.unit not in _METRIC_UNITS[self.metric]:
            raise ValueError('unsupported metric/unit combination')
        if not re.fullmatch(_VALUE, self.value) or len(self.value) > 24:
            raise ValueError('unsupported numeric literal')
        if not re.fullmatch(_YEAR, self.year):
            raise ValueError('unsupported year')
        if type(self.negated) is not bool:
            raise TypeError('negated must be boolean')


def parse_frame(text: str) -> Frame | None:
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    if len(text) > 512:
        return None
    for pattern in _PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            data = match.groupdict()
            negative = 'not' in (data.get('verb') or data.get('state')).split()
            try:
                return Frame(data['entity'], data['metric'], data['value'], data['unit'], data['year'], negative)
            except ValueError:
                return None
    return None


def render(frame: Frame) -> tuple[str, ...]:
    if not isinstance(frame, Frame):
        raise TypeError('expected a Frame')
    verb = 'did not report' if frame.negated else 'reported'
    state = 'was not reported' if frame.negated else 'was reported'
    phrase = f'{frame.metric} of {frame.value} {frame.unit}'
    candidates = (
        f'{frame.entity} {verb} a {phrase} in {frame.year}.',
        f'In {frame.year}, {frame.entity} {verb} a {phrase}.',
        f'A {phrase} {state} by {frame.entity} in {frame.year}.',
        f'In {frame.year}, a {phrase} {state} by {frame.entity}.',
    )
    if any(parse_frame(candidate) != frame for candidate in candidates):
        raise RuntimeError('candidate failed semantic-frame roundtrip')
    return candidates


def edit_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        nxt = [i]
        for j, b in enumerate(right, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = nxt
    return row[-1]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _hidden(text: str) -> bool:
    return any(unicodedata.category(c) in {'Cf', 'Cc', 'Cs', 'Co', 'Cn', 'Me'} and c not in '\n\r\t'
               or 0xFE00 <= ord(c) <= 0xFE0F or 0xE0100 <= ord(c) <= 0xE01EF for c in text)


@dataclass(frozen=True)
class Reconstruction:
    text: str
    status: str
    reason: str
    frames: tuple[Frame, ...]
    plan: Plan | None
    input_hash: str
    output_hash: str

    def receipt(self) -> dict:
        result = {
            'algorithm_version': VERSION,
            'status': self.status,
            'reason': self.reason,
            'input_sha256': self.input_hash,
            'output_sha256': self.output_hash,
            'facts': [asdict(frame) for frame in self.frames],
            'scope': 'restricted English reporting grammar; not arbitrary prose',
            'watermark_removal_verified': False,
            'detector_queries_during_selection': 0,
            'watermark_keys_during_selection': 0,
            'unicode_payload_added': False,
            'visible_wording_can_change': True,
        }
        if self.plan is not None:
            result['plan'] = {
                'selected_indices': list(self.plan.selected),
                'normalized_word_edit_cost': self.plan.edit_cost,
                'views': [v.name for v in DEFAULT_VIEWS],
                'shared_window_counts': list(self.plan.shared_counts),
                'source_window_counts': list(self.plan.source_counts),
                'worst_shared_fraction': str(self.plan.objective[0]),
                'states_evaluated': self.plan.states_evaluated,
                'states_pruned': self.plan.states_pruned,
                'exact_within_candidate_lattice': self.plan.exact_within_candidate_lattice,
                'quality_guarantee': 'ordered grammar-frame equality only, not universal semantic equivalence',
            }
        result['receipt_sha256'] = _sha(json.dumps(result, sort_keys=True, separators=(',', ':'), ensure_ascii=True))
        return result


def reconstruct_frames(source_segments: tuple[str, ...], *, budget: int = 32,
                       max_states: int = 20000, max_evaluations: int = 200000,
                       separator: str = ' ') -> Reconstruction:
    if not isinstance(source_segments, tuple) or not source_segments or any(not isinstance(s, str) for s in source_segments):
        raise TypeError('source_segments must be a nonempty tuple of strings')
    if not isinstance(separator, str) or not separator or not separator.isspace():
        raise ValueError('separator must contain whitespace only')
    if type(budget) is not int or budget < 0:
        raise ValueError('budget must be a nonnegative integer')
    if type(max_states) is not int or max_states < 1:
        raise ValueError('max_states must be a positive integer')
    if type(max_evaluations) is not int or max_evaluations < 1:
        raise ValueError('max_evaluations must be a positive integer')
    if len(source_segments) > 64:
        raise ValueError('input exceeds bounded research limits')
    source = separator.join(source_segments)
    if len(source) > 100000 or len(source_segments) > 64:
        raise ValueError('input exceeds bounded research limits')
    if any(0xD800 <= ord(c) <= 0xDFFF for c in source):
        raise ValueError('input is not Unicode scalar text')
    digest = _sha(source)
    parsed = tuple(parse_frame(s) for s in source_segments)
    if any(f is None for f in parsed):
        return Reconstruction(source, 'unsupported', 'at least one sentence is outside the explicit grammar', (), None, digest, digest)
    frames = tuple(f for f in parsed if f is not None)
    lattice = tuple(tuple(Alternative(text, edit_distance(words(s), words(text)), f'frame-{i}-form-{j}')
                          for j, text in enumerate(render(f)))
                    for i, (s, f) in enumerate(zip(source_segments, frames, strict=True)))
    try:
        chosen = plan(source, lattice, budget=budget, max_states=max_states,
                      max_evaluations=max_evaluations, separator=separator)
    except SearchLimitExceeded as error:
        return Reconstruction(source, 'search_limit', str(error), frames, None, digest, digest)
    selected = tuple(lattice[i][j].text for i, j in enumerate(chosen.selected))
    if tuple(parse_frame(s) for s in selected) != frames:
        raise RuntimeError('ordered fact frames changed')
    if Counter(re.findall(r'\d+(?:\.\d+)?', source)) != Counter(re.findall(r'\d+(?:\.\d+)?', chosen.text)):
        raise RuntimeError('numeric literals changed')
    if _hidden(chosen.text) or unicodedata.normalize('NFKC', chosen.text) != chosen.text:
        raise RuntimeError('noncanonical or hidden output')
    if len(words(chosen.text)) > 2 * len(words(source)):
        raise RuntimeError('output exceeds the length guard')
    return Reconstruction(chosen.text, 'changed' if chosen.text != source else 'unchanged',
                          'restricted grammar verified; watermark effect unverified', frames, chosen,
                          digest, _sha(chosen.text))


def reconstruct(source: str, *, budget: int = 32, max_states: int = 20000,
                max_evaluations: int = 200000) -> Reconstruction:
    if not isinstance(source, str):
        raise TypeError('source must be text')
    if not source or len(source) > 100000:
        raise ValueError('input must contain 1 to 100000 characters')
    if any(0xD800 <= ord(c) <= 0xDFFF for c in source):
        raise ValueError('input is not Unicode scalar text')
    segments = tuple(re.split(r'(?<=\.) ', source))
    return reconstruct_frames(segments, budget=budget, max_states=max_states,
                              max_evaluations=max_evaluations)
