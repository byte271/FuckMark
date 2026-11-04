from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from collections.abc import Callable, Sequence
import re
import unicodedata

VERSION = 'boundary-aware-reconstruction-v1'


class SearchLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class View:
    name: str
    width: int
    tokenize: Callable[[str], tuple[str, ...]]

    def __post_init__(self):
        if not self.name or type(self.width) is not int or self.width < 1:
            raise ValueError('view requires a name and positive integer width')
        if not callable(self.tokenize):
            raise TypeError('view tokenizer must be callable')


def words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


def words_and_punctuation(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r'\w+|[^\w\s]', unicodedata.normalize('NFKC', text).casefold()))


DEFAULT_VIEWS = (
    View('normalized-word-3', 3, words),
    View('normalized-word-5', 5, words),
    View('normalized-token-5', 5, words_and_punctuation),
)


@dataclass(frozen=True)
class Alternative:
    text: str
    cost: int
    identity: str

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError('alternative text must be nonempty')
        if type(self.cost) is not int or self.cost < 0:
            raise ValueError('alternative cost must be a nonnegative integer')
        if not isinstance(self.identity, str) or not self.identity:
            raise ValueError('alternative identity must be nonempty')


@dataclass(frozen=True)
class Plan:
    text: str
    selected: tuple[int, ...]
    edit_cost: int
    shared_counts: tuple[int, ...]
    source_counts: tuple[int, ...]
    objective: tuple[Fraction, Fraction, int, tuple[int, ...]]
    states_evaluated: int
    states_pruned: int
    exact_within_candidate_lattice: bool


@dataclass(frozen=True)
class _State:
    tails: tuple[tuple[str, ...], ...]
    counts: tuple[int, ...]
    cost: int
    path: tuple[int, ...]


def windows(tokens: tuple[str, ...], width: int) -> tuple[tuple[str, ...], ...]:
    return tuple(tokens[i:i + width] for i in range(max(0, len(tokens) - width + 1)))


def reference(text: str, views: Sequence[View]):
    rows = tuple(windows(view.tokenize(text), view.width) for view in views)
    return tuple(frozenset(row) for row in rows), tuple(len(row) for row in rows)


def residual_counts(text: str, refs, views: Sequence[View]) -> tuple[int, ...]:
    return tuple(sum(window in ref for window in windows(view.tokenize(text), view.width))
                 for view, ref in zip(views, refs, strict=True))


def objective(counts, denominators, cost, path):
    fractions = tuple(Fraction(count, max(1, size)) for count, size in zip(counts, denominators, strict=True))
    return max(fractions), sum(fractions, Fraction()), cost, path


def _dominates(left: _State, right: _State) -> bool:
    if left.cost > right.cost or any(a > b for a, b in zip(left.counts, right.counts, strict=True)):
        return False
    if left.cost < right.cost or left.counts != right.counts:
        return True
    return left.path <= right.path


def _insert(frontier: list[_State], candidate: _State) -> int:
    if any(_dominates(old, candidate) for old in frontier):
        return 1
    retained = [old for old in frontier if not _dominates(candidate, old)]
    removed = len(frontier) - len(retained)
    retained.append(candidate)
    frontier[:] = retained
    return removed


def plan(source: str, lattice: Sequence[Sequence[Alternative]], *, budget: int,
         views: Sequence[View] = DEFAULT_VIEWS, max_states: int = 20000,
         max_evaluations: int = 200000, separator: str = ' ') -> Plan:
    if not isinstance(source, str):
        raise TypeError('source must be text')
    if type(budget) is not int or budget < 0:
        raise ValueError('budget must be a nonnegative integer')
    if type(max_states) is not int or max_states < 1:
        raise ValueError('max_states must be a positive integer')
    if type(max_evaluations) is not int or max_evaluations < 1:
        raise ValueError('max_evaluations must be a positive integer')
    if not isinstance(separator, str) or not separator or not separator.isspace():
        raise ValueError('separator must contain whitespace only')
    views = tuple(views)
    if not views or len({v.name for v in views}) != len(views):
        raise ValueError('views must be nonempty with unique names')
    if any(v.tokenize not in (words, words_and_punctuation) for v in views):
        raise ValueError('exact search requires a supported whitespace-compositional tokenizer')
    lattice = tuple(tuple(row) for row in lattice)
    if not lattice or any(not row for row in lattice):
        raise ValueError('each source segment needs alternatives')
    if len(lattice) > 64 or any(len(row) > 16 for row in lattice) or len(source) > 100000:
        raise ValueError('input exceeds bounded research limits')
    if any(not isinstance(a, Alternative) for row in lattice for a in row):
        raise TypeError('lattice must contain Alternative values')
    if any(len(a.text) > 10000 for row in lattice for a in row):
        raise ValueError('alternative exceeds text limit')
    refs, sizes = reference(source, views)
    encoded = tuple(tuple(tuple(v.tokenize(a.text) for v in views) for a in row) for row in lattice)
    states = [_State(tuple(() for _ in views), tuple(0 for _ in views), 0, ())]
    evaluated = pruned = 0
    for row_index, row in enumerate(lattice):
        groups: dict[tuple, list[_State]] = {}
        alive = 0
        for state in states:
            for choice, alternative in enumerate(row):
                evaluated += 1
                if evaluated > max_evaluations:
                    raise SearchLimitExceeded('evaluation limit exceeded; no optimality claim or output')
                cost = state.cost + alternative.cost
                if cost > budget:
                    continue
                tails, counts = [], []
                for i, view in enumerate(views):
                    combined = state.tails[i] + encoded[row_index][choice][i]
                    counts.append(state.counts[i] + sum(w in refs[i] for w in windows(combined, view.width)))
                    tails.append(combined[-(view.width - 1):] if view.width > 1 else ())
                new = _State(tuple(tails), tuple(counts), cost, state.path + (choice,))
                frontier = groups.setdefault(new.tails, [])
                before = len(frontier)
                pruned += _insert(frontier, new)
                alive += len(frontier) - before
                if alive > max_states:
                    raise SearchLimitExceeded('state limit exceeded; no optimality claim or output')
        states = [s for group in groups.values() for s in group]
        if not states:
            raise ValueError('no feasible reconstruction within budget')
    best = min(states, key=lambda s: objective(s.counts, sizes, s.cost, s.path))
    output = separator.join(row[index].text for row, index in zip(lattice, best.path, strict=True))
    replay = residual_counts(output, refs, views)
    if replay != best.counts:
        raise RuntimeError('full-output replay disagrees with dynamic program')
    return Plan(output, best.path, best.cost, best.counts, sizes,
                objective(best.counts, sizes, best.cost, best.path), evaluated, pruned, True)
