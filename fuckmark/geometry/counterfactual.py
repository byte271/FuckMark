from __future__ import annotations

from array import array
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .._validation import normalize_token_sequence, require_clean_string, require_int, require_sha256
from ..alignment import AlignmentResult, align_tokens
from ..hashing import sha256_json, sha256_text
from .observations import (
    GeometryConfig,
    ObservationSurvivalReport,
    RootObservationSet,
    build_root_observations,
    compute_observation_survival,
    normalize_window_eligibility,
)


COUNTERFACTUAL_GEOMETRY_ALGORITHM_VERSION = "counterfactual-geometry-v1"
DEFAULT_MAX_ALIGNMENT_CELLS = 4_500_000
DEFAULT_MAX_TOKEN_COUNT = 10_000

EligibilityPolicy = Callable[[tuple[int, ...], GeometryConfig], Sequence[bool]]


class GeometryResourceLimitError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CounterfactualRoot:
    source_sample_id: str
    source_text: str
    source_text_hash: str
    root_tokens: tuple[int, ...]
    observations: RootObservationSet
    geometry_config_hash: str
    root_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_sample_id", self.source_sample_id)
        if not isinstance(self.source_text, str):
            raise TypeError("source_text must be a string")
        require_sha256("source_text_hash", self.source_text_hash)
        if self.source_text_hash != sha256_text(self.source_text):
            raise ValueError("source_text_hash does not match source_text")
        normalized = normalize_token_sequence("root_tokens", self.root_tokens)
        if normalized != self.root_tokens:
            raise ValueError("root_tokens must already be a tuple")
        if not isinstance(self.observations, RootObservationSet):
            raise TypeError("observations must be a RootObservationSet")
        if self.observations.source_text_hash != self.source_text_hash:
            raise ValueError("observation root source hash does not match source text")
        if self.observations.root_token_hash != sha256_json(self.root_tokens):
            raise ValueError("observation root token hash does not match root tokens")
        require_sha256("geometry_config_hash", self.geometry_config_hash)
        if self.observations.geometry_config_hash != self.geometry_config_hash:
            raise ValueError("observation root config hash does not match geometry config")
        require_sha256("root_hash", self.root_hash)
        if self.root_hash != sha256_json(self.payload()):
            raise ValueError("root_hash does not match CounterfactualRoot payload")

    def payload(self) -> dict[str, object]:
        return {
            "source_sample_id": self.source_sample_id,
            "source_text_hash": self.source_text_hash,
            "root_token_hash": sha256_json(self.root_tokens),
            "observation_root_hash": self.observations.root_hash,
            "geometry_config_hash": self.geometry_config_hash,
        }


@dataclass(frozen=True, slots=True)
class CandidateCounterfactual:
    algorithm_version: str
    root_source_hash: str
    source_state_hash: str
    candidate_id: str
    rule_hash: str
    output_text_hash: str
    root_token_hash: str
    output_token_hash: str
    alignment_hash: str
    geometry_hash: str
    survival_report: ObservationSurvivalReport
    token_edit_distance: int
    character_edit_distance: int
    visible_cost_class: int
    family: str
    tier: int
    hard_invariant_status: str
    counterfactual_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        for name in (
            "root_source_hash",
            "source_state_hash",
            "rule_hash",
            "output_text_hash",
            "root_token_hash",
            "output_token_hash",
            "alignment_hash",
            "geometry_hash",
            "counterfactual_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_clean_string("candidate_id", self.candidate_id)
        if not isinstance(self.survival_report, ObservationSurvivalReport):
            raise TypeError("survival_report must be an ObservationSurvivalReport")
        for name in ("token_edit_distance", "character_edit_distance", "visible_cost_class", "tier"):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        require_clean_string("family", self.family)
        require_clean_string("hard_invariant_status", self.hard_invariant_status)
        if self.hard_invariant_status != "PASS":
            raise ValueError("counterfactuals may only represent hard-invariant PASS states")
        if self.counterfactual_hash != sha256_json(self.payload()):
            raise ValueError("counterfactual_hash does not match CandidateCounterfactual payload")

    @property
    def root_observation_count(self) -> int:
        return self.survival_report.root_observation_count

    @property
    def surviving_count(self) -> int:
        return self.survival_report.surviving_count

    @property
    def destroyed_count(self) -> int:
        return self.survival_report.destroyed_count

    @property
    def survival_ratio(self) -> float:
        return self.survival_report.survival_ratio

    @property
    def destruction_ratio(self) -> float:
        return self.survival_report.destruction_ratio

    @property
    def newly_masked_count(self) -> int:
        return self.survival_report.newly_masked_count

    @property
    def unmapped_count(self) -> int:
        return self.survival_report.unmapped_count

    @property
    def ambiguous_count(self) -> int:
        return self.survival_report.ambiguous_count

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "root_source_hash": self.root_source_hash,
            "source_state_hash": self.source_state_hash,
            "candidate_id": self.candidate_id,
            "rule_hash": self.rule_hash,
            "output_text_hash": self.output_text_hash,
            "root_token_hash": self.root_token_hash,
            "output_token_hash": self.output_token_hash,
            "alignment_hash": self.alignment_hash,
            "geometry_hash": self.geometry_hash,
            "survival_report_hash": self.survival_report.report_hash,
            "token_edit_distance": self.token_edit_distance,
            "character_edit_distance": self.character_edit_distance,
            "visible_cost_class": self.visible_cost_class,
            "family": self.family,
            "tier": self.tier,
            "hard_invariant_status": self.hard_invariant_status,
        }


@dataclass(frozen=True, slots=True)
class _GeometryCore:
    output_tokens: tuple[int, ...]
    output_token_hash: str
    alignment: AlignmentResult
    alignment_hash: str
    survival_report: ObservationSurvivalReport
    geometry_hash: str


class CounterfactualGeometryEngine:
    def __init__(
        self,
        *,
        tokenizer: Any,
        config: GeometryConfig,
        eligibility_policy: EligibilityPolicy | None = None,
        enable_cache: bool = True,
        max_alignment_cells: int = DEFAULT_MAX_ALIGNMENT_CELLS,
        max_token_count: int = DEFAULT_MAX_TOKEN_COUNT,
    ) -> None:
        if tokenizer is None:
            raise TypeError("tokenizer is required")
        if not isinstance(config, GeometryConfig):
            raise TypeError("config must be a GeometryConfig")
        if eligibility_policy is not None and not callable(eligibility_policy):
            raise TypeError("eligibility_policy must be callable")
        if not isinstance(enable_cache, bool):
            raise TypeError("enable_cache must be a boolean")
        require_int("max_alignment_cells", max_alignment_cells)
        require_int("max_token_count", max_token_count)
        if max_alignment_cells <= 0 or max_token_count <= 0:
            raise ValueError("geometry resource limits must be positive")
        self._tokenizer = tokenizer
        self._config = config
        self._eligibility_policy = eligibility_policy
        self._enable_cache = enable_cache
        self._max_alignment_cells = max_alignment_cells
        self._max_token_count = max_token_count
        self._core_cache: dict[tuple[str, str, str, str], _GeometryCore] = {}
        self._token_cache: dict[str, tuple[int, ...]] = {}
        self._cache_hit_count = 0

    @property
    def config(self) -> GeometryConfig:
        return self._config

    @property
    def detector_access_observed(self) -> bool:
        return False

    @property
    def cache_hit_count(self) -> int:
        return self._cache_hit_count

    def clear_cache(self) -> None:
        self._core_cache.clear()
        self._token_cache.clear()
        self._cache_hit_count = 0

    def build_root(self, *, source_sample_id: str, source_text: str) -> CounterfactualRoot:
        require_clean_string("source_sample_id", source_sample_id)
        if not isinstance(source_text, str):
            raise TypeError("source_text must be a string")
        tokens = self._tokenize(source_text)
        eligibility = self._eligibility(tokens)
        observations = build_root_observations(
            source_sample_id=source_sample_id,
            source_text=source_text,
            root_tokens=tokens,
            config=self._config,
            eligible_windows=eligibility,
        )
        payload = {
            "source_sample_id": source_sample_id,
            "source_text_hash": sha256_text(source_text),
            "root_token_hash": sha256_json(tokens),
            "observation_root_hash": observations.root_hash,
            "geometry_config_hash": self._config.config_hash,
        }
        return CounterfactualRoot(
            source_sample_id=source_sample_id,
            source_text=source_text,
            source_text_hash=payload["source_text_hash"],
            root_tokens=tokens,
            observations=observations,
            geometry_config_hash=self._config.config_hash,
            root_hash=sha256_json(payload),
        )

    def evaluate_output(
        self,
        *,
        root: CounterfactualRoot,
        current_text: str,
        output_text: str,
        candidate_id: str,
        rule_hash: str,
        visible_cost_class: int,
        family: str,
        tier: int,
        hard_invariant_status: str = "PASS",
    ) -> CandidateCounterfactual:
        if not isinstance(root, CounterfactualRoot):
            raise TypeError("root must be a CounterfactualRoot")
        if root.geometry_config_hash != self._config.config_hash:
            raise ValueError("root was built with a different geometry configuration")
        if not isinstance(current_text, str) or not isinstance(output_text, str):
            raise TypeError("current_text and output_text must be strings")
        require_clean_string("candidate_id", candidate_id)
        require_sha256("rule_hash", rule_hash)
        require_int("visible_cost_class", visible_cost_class)
        require_int("tier", tier)
        if visible_cost_class < 0 or tier < 0:
            raise ValueError("visible_cost_class and tier must be non-negative")
        require_clean_string("family", family)
        require_clean_string("hard_invariant_status", hard_invariant_status)
        if hard_invariant_status != "PASS":
            raise ValueError("hard invariants must pass before geometry evaluation")
        output_text_hash = sha256_text(output_text)
        cache_key = (
            root.root_hash,
            output_text_hash,
            self._config.tokenizer_identity_hash,
            self._config.config_hash,
        )
        core = self._core_cache.get(cache_key) if self._enable_cache else None
        if core is not None:
            self._cache_hit_count += 1
        else:
            core = self._evaluate_core(root, output_text, output_text_hash)
            if self._enable_cache:
                self._core_cache[cache_key] = core
        payload = {
            "algorithm_version": COUNTERFACTUAL_GEOMETRY_ALGORITHM_VERSION,
            "root_source_hash": root.source_text_hash,
            "source_state_hash": sha256_text(current_text),
            "candidate_id": candidate_id,
            "rule_hash": rule_hash,
            "output_text_hash": output_text_hash,
            "root_token_hash": sha256_json(root.root_tokens),
            "output_token_hash": core.output_token_hash,
            "alignment_hash": core.alignment_hash,
            "geometry_hash": core.geometry_hash,
            "survival_report_hash": core.survival_report.report_hash,
            "token_edit_distance": core.alignment.distance,
            "character_edit_distance": _levenshtein_distance(root.source_text, output_text),
            "visible_cost_class": visible_cost_class,
            "family": family,
            "tier": tier,
            "hard_invariant_status": hard_invariant_status,
        }
        return CandidateCounterfactual(
            algorithm_version=COUNTERFACTUAL_GEOMETRY_ALGORITHM_VERSION,
            root_source_hash=root.source_text_hash,
            source_state_hash=payload["source_state_hash"],
            candidate_id=candidate_id,
            rule_hash=rule_hash,
            output_text_hash=output_text_hash,
            root_token_hash=payload["root_token_hash"],
            output_token_hash=core.output_token_hash,
            alignment_hash=core.alignment_hash,
            geometry_hash=core.geometry_hash,
            survival_report=core.survival_report,
            token_edit_distance=core.alignment.distance,
            character_edit_distance=payload["character_edit_distance"],
            visible_cost_class=visible_cost_class,
            family=family,
            tier=tier,
            hard_invariant_status=hard_invariant_status,
            counterfactual_hash=sha256_json(payload),
        )

    def _evaluate_core(
        self,
        root: CounterfactualRoot,
        output_text: str,
        output_text_hash: str,
    ) -> _GeometryCore:
        output_tokens = self._tokenize(output_text)
        cells = (len(root.root_tokens) + 1) * (len(output_tokens) + 1)
        if cells > self._max_alignment_cells:
            raise GeometryResourceLimitError(
                f"geometry alignment requires {cells} cells, exceeding max_alignment_cells={self._max_alignment_cells}"
            )
        try:
            alignment = align_tokens(
                root.root_tokens,
                output_tokens,
                max_cells=self._max_alignment_cells,
                max_steps=max(self._max_token_count, len(root.root_tokens), len(output_tokens)) + 1,
            )
        except ValueError as error:
            raise GeometryResourceLimitError(str(error)) from error
        ambiguous = _ambiguous_root_indices(
            root.root_tokens,
            output_tokens,
            alignment.distance,
            max_cells=self._max_alignment_cells,
        )
        output_eligibility = self._eligibility(output_tokens)
        report = compute_observation_survival(
            root=root.observations,
            root_tokens=root.root_tokens,
            transformed_tokens=output_tokens,
            transformed_eligible_windows=output_eligibility,
            alignment=alignment,
            ambiguous_original_indices=ambiguous,
        )
        alignment_hash = sha256_json(
            {
                "distance": alignment.distance,
                "steps": tuple(
                    {
                        "op": step.op.value,
                        "original_index": step.original_index,
                        "transformed_index": step.transformed_index,
                        "original_token": step.original_token,
                        "transformed_token": step.transformed_token,
                    }
                    for step in alignment.steps
                ),
                "original_to_transformed": alignment.original_to_transformed,
                "ambiguous_original_indices": tuple(sorted(ambiguous)),
            }
        )
        output_token_hash = sha256_json(output_tokens)
        geometry_hash = sha256_json(
            {
                "algorithm_version": COUNTERFACTUAL_GEOMETRY_ALGORITHM_VERSION,
                "root_hash": root.root_hash,
                "output_text_hash": output_text_hash,
                "output_token_hash": output_token_hash,
                "alignment_hash": alignment_hash,
                "survival_report_hash": report.report_hash,
                "tokenizer_identity_hash": self._config.tokenizer_identity_hash,
                "geometry_config_hash": self._config.config_hash,
            }
        )
        return _GeometryCore(
            output_tokens=output_tokens,
            output_token_hash=output_token_hash,
            alignment=alignment,
            alignment_hash=alignment_hash,
            survival_report=report,
            geometry_hash=geometry_hash,
        )

    def _eligibility(self, tokens: tuple[int, ...]) -> tuple[bool, ...]:
        if self._eligibility_policy is None:
            values = None
        else:
            values = self._eligibility_policy(tokens, self._config)
        return normalize_window_eligibility(len(tokens), self._config.ngram_len, values)

    def _tokenize(self, text: str) -> tuple[int, ...]:
        text_hash = sha256_text(text)
        cached = self._token_cache.get(text_hash) if self._enable_cache else None
        if cached is not None:
            self._cache_hit_count += 1
            return cached
        tokenizer = self._tokenizer
        result: Any
        if hasattr(tokenizer, "encode") and callable(tokenizer.encode):
            try:
                result = tokenizer.encode(text, add_special_tokens=False)
            except TypeError:
                result = tokenizer.encode(text)
        elif callable(tokenizer):
            try:
                result = tokenizer(text, add_special_tokens=False)
            except TypeError:
                result = tokenizer(text)
        else:
            raise TypeError("tokenizer must be callable or expose encode")
        if isinstance(result, Mapping):
            if "input_ids" not in result:
                raise TypeError("tokenizer mapping output must contain input_ids")
            result = result["input_ids"]
        if hasattr(result, "tolist") and callable(result.tolist):
            result = result.tolist()
        if (
            isinstance(result, Sequence)
            and not isinstance(result, (str, bytes, bytearray))
            and len(result) == 1
            and isinstance(result[0], Sequence)
            and not isinstance(result[0], (str, bytes, bytearray))
        ):
            result = result[0]
        tokens = normalize_token_sequence("tokenizer output", result)
        if len(tokens) > self._max_token_count:
            raise GeometryResourceLimitError(
                f"tokenizer output has {len(tokens)} tokens, exceeding max_token_count={self._max_token_count}"
            )
        if self._enable_cache:
            self._token_cache[text_hash] = tokens
        return tokens


def _levenshtein_distance(original: Sequence[Any], transformed: Sequence[Any]) -> int:
    if len(original) < len(transformed):
        original, transformed = transformed, original
    previous = list(range(len(transformed) + 1))
    for i, left in enumerate(original, start=1):
        current = [i]
        for j, right in enumerate(transformed, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (left != right),
                )
            )
        previous = current
    return previous[-1]


def _ambiguous_root_indices(
    original: Sequence[int],
    transformed: Sequence[int],
    optimal_distance: int,
    *,
    max_cells: int,
) -> frozenset[int]:
    left = normalize_token_sequence("original", original)
    right = normalize_token_sequence("transformed", transformed)
    n = len(left)
    m = len(right)
    cells = (n + 1) * (m + 1)
    if cells > max_cells:
        raise GeometryResourceLimitError(
            f"ambiguity analysis requires {cells} cells, exceeding max_alignment_cells={max_cells}"
        )
    columns = m + 1
    forward = array("I", [0]) * cells
    backward = array("I", [0]) * cells
    for i in range(n + 1):
        forward[i * columns] = i
    for j in range(m + 1):
        forward[j] = j
    for i in range(1, n + 1):
        row = i * columns
        prev_row = (i - 1) * columns
        for j in range(1, m + 1):
            forward[row + j] = min(
                forward[prev_row + j] + 1,
                forward[row + j - 1] + 1,
                forward[prev_row + j - 1] + (left[i - 1] != right[j - 1]),
            )
    if int(forward[n * columns + m]) != optimal_distance:
        raise ValueError("optimal_distance does not match exact alignment distance")
    for i in range(n, -1, -1):
        backward[i * columns + m] = n - i
    for j in range(m, -1, -1):
        backward[n * columns + j] = m - j
    for i in range(n - 1, -1, -1):
        row = i * columns
        next_row = (i + 1) * columns
        for j in range(m - 1, -1, -1):
            backward[row + j] = min(
                backward[next_row + j] + 1,
                backward[row + j + 1] + 1,
                backward[next_row + j + 1] + (left[i] != right[j]),
            )
    ambiguous: set[int] = set()
    for i in range(n):
        possible_matches: list[int] = []
        nonmatch_possible = False
        for j in range(m + 1):
            prefix = int(forward[i * columns + j])
            if prefix + 1 + int(backward[(i + 1) * columns + j]) == optimal_distance:
                nonmatch_possible = True
            if j == m:
                continue
            if left[i] == right[j] and prefix + int(backward[(i + 1) * columns + (j + 1)]) == optimal_distance:
                possible_matches.append(j)
            elif left[i] != right[j] and prefix + 1 + int(
                backward[(i + 1) * columns + (j + 1)]
            ) == optimal_distance:
                nonmatch_possible = True
        if len(possible_matches) != 1 or nonmatch_possible:
            ambiguous.add(i)
    return frozenset(ambiguous)
