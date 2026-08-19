from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from .mid_dev_quality import protected_span_violation_count
from .residual_signal_geometry import compute_residual_signal_geometry
from .structural_leverage import build_structural_leverage_sidecar


TINY_DEV_RESIDUAL_REPLAY_ALGORITHM_VERSION = "tiny-dev-residual-signal-replay-v1"
TINY_DEV_RESIDUAL_EXPLANATION_COMPARISON_VERSION = "tiny-dev-residual-explanation-comparison-v1"
FROZEN_BASELINE_SHA = "697146f0e7fb443c9d02c60393266442549b7ced"
FROZEN_TINY_DEV_PLAN_HASH = "d8b55b88c246caed90e0d26003627a144e2f2649eaddc937911d1073a048729a"
FROZEN_TINY_DEV_EVIDENCE_HASH = "88f7cbd967cbfc7babee29ebf2a4c1e7de86bf65710a11b472067c18d00ee7f9"
FROZEN_TINY_DEV_CORPUS_HASH = "42240f72e17df1a048f44197f216a0b5f30128c26e2da93afbe92820946e4561"
PRIMARY_POLICIES = (
    "CONTEXT_SURVIVAL_EXACT_B1",
    "CONTEXT_SURVIVAL_EXACT_B2",
    "CONTEXT_SURVIVAL_BEAM_B4",
    "CONTEXT_SURVIVAL_BEAM_B6",
)


class ResidualReplayDecision(str, Enum):
    RESIDUAL_EXPLAINS_BETTER = "RESIDUAL_EXPLAINS_BETTER"
    KILL_NEW_OBJECTIVE_KEEP_BEAM_V2 = "KILL_NEW_OBJECTIVE_KEEP_BEAM_V2"


@dataclass(frozen=True, slots=True)
class TinyDevResidualReplayRow:
    source_sample_id: str
    source_label: str
    schedule_policy: str
    budget: int
    schedule_seed: int
    realized_edit_cost: int
    variant_hash: str
    source_text_hash: str
    transformed_text_hash: str
    geometry_hash: str
    root_valid_observation_count: int
    final_valid_observation_count: int
    preserved_root_valid_observation_count: int
    root_survival_fraction: float
    root_destruction_fraction: float
    residual_inherited_fraction: float
    new_context_opportunity_fraction: float
    valid_denominator_ratio: float
    repetition_mask_delta: int
    visible_word_edit_rate: float
    visible_character_edit_rate: float
    token_edit_distance: int
    protected_span_violation_count: int
    hard_invariant_status: str
    old_exact_destruction_ratio: float
    margin_drop: float
    row_hash: str

    def __post_init__(self) -> None:
        for name in ("source_sample_id", "source_label", "schedule_policy", "hard_invariant_status"):
            require_clean_string(name, getattr(self, name))
        for name in (
            "budget", "schedule_seed", "realized_edit_cost", "root_valid_observation_count",
            "final_valid_observation_count", "preserved_root_valid_observation_count",
            "repetition_mask_delta", "token_edit_distance", "protected_span_violation_count",
        ):
            require_int(name, getattr(self, name))
        for name in ("variant_hash", "source_text_hash", "transformed_text_hash", "geometry_hash", "row_hash"):
            require_sha256(name, getattr(self, name))
        for name in (
            "root_survival_fraction", "root_destruction_fraction", "residual_inherited_fraction",
            "new_context_opportunity_fraction", "valid_denominator_ratio", "visible_word_edit_rate",
            "visible_character_edit_rate", "old_exact_destruction_ratio", "margin_drop",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("row_hash does not match TinyDev residual replay row")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "row_hash"}


@dataclass(frozen=True, slots=True)
class TinyDevResidualExplanationComparison:
    algorithm_version: str
    independent_source_count: int
    primary_row_count: int
    old_predictor: str
    new_predictor: str
    old_source_centered_pearson: float
    new_source_centered_pearson: float
    old_leave_one_source_out_rmse: float
    new_leave_one_source_out_rmse: float
    predictor_pearson: float
    maximum_absolute_predictor_difference: float
    decision: ResidualReplayDecision
    comparison_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != TINY_DEV_RESIDUAL_EXPLANATION_COMPARISON_VERSION:
            raise ValueError("unsupported TinyDev residual explanation comparison version")
        require_int("independent_source_count", self.independent_source_count)
        require_int("primary_row_count", self.primary_row_count)
        if (self.independent_source_count, self.primary_row_count) != (4, 16):
            raise ValueError("TinyDev primary comparison must bind four sources and sixteen rows")
        if self.old_predictor != "root_destruction_fraction" or self.new_predictor != "new_context_opportunity_fraction":
            raise ValueError("TinyDev replay predictor definitions drifted")
        for name in (
            "old_source_centered_pearson", "new_source_centered_pearson",
            "old_leave_one_source_out_rmse", "new_leave_one_source_out_rmse",
            "predictor_pearson", "maximum_absolute_predictor_difference",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
        better = (
            self.new_leave_one_source_out_rmse < self.old_leave_one_source_out_rmse
            and abs(self.new_source_centered_pearson) > abs(self.old_source_centered_pearson)
        )
        expected = ResidualReplayDecision.RESIDUAL_EXPLAINS_BETTER if better else ResidualReplayDecision.KILL_NEW_OBJECTIVE_KEEP_BEAM_V2
        if self.decision is not expected:
            raise ValueError("decision does not match frozen TinyDev replay gate")
        require_sha256("comparison_hash", self.comparison_hash)
        if self.comparison_hash != sha256_json(self.payload()):
            raise ValueError("comparison_hash does not match TinyDev residual comparison")

    def payload(self) -> dict[str, object]:
        return {
            name: (getattr(self, name).value if name == "decision" else getattr(self, name))
            for name in self.__dataclass_fields__ if name != "comparison_hash"
        }


@dataclass(frozen=True, slots=True)
class TinyDevResidualReplayArtifact:
    algorithm_version: str
    source_code_commit: str
    plan_hash: str
    evidence_hash: str
    tiny_dev_corpus_hash: str
    tokenizer_identity_hash: str
    detector_access_during_selection_observed: bool
    secret_access_during_selection_observed: bool
    rows: tuple[TinyDevResidualReplayRow, ...]
    comparison: TinyDevResidualExplanationComparison
    artifact_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != TINY_DEV_RESIDUAL_REPLAY_ALGORITHM_VERSION:
            raise ValueError("unsupported TinyDev residual replay version")
        if self.source_code_commit != FROZEN_BASELINE_SHA or self.plan_hash != FROZEN_TINY_DEV_PLAN_HASH:
            raise ValueError("TinyDev replay baseline binding drifted")
        if self.evidence_hash != FROZEN_TINY_DEV_EVIDENCE_HASH or self.tiny_dev_corpus_hash != FROZEN_TINY_DEV_CORPUS_HASH:
            raise ValueError("TinyDev replay artifact binding drifted")
        require_sha256("tokenizer_identity_hash", self.tokenizer_identity_hash)
        if self.detector_access_during_selection_observed or self.secret_access_during_selection_observed:
            raise ValueError("TinyDev replay refuses selection-time detector/secret access")
        if len(self.rows) != 384 or len({row.variant_hash for row in self.rows}) != 384:
            raise ValueError("TinyDev residual replay requires 384 unique frozen rows")
        if tuple(sorted(self.rows, key=_row_sort_key)) != self.rows:
            raise ValueError("TinyDev residual replay rows must be canonically ordered")
        require_sha256("artifact_hash", self.artifact_hash)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match TinyDev residual replay")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_code_commit": self.source_code_commit,
            "plan_hash": self.plan_hash,
            "evidence_hash": self.evidence_hash,
            "tiny_dev_corpus_hash": self.tiny_dev_corpus_hash,
            "tokenizer_identity_hash": self.tokenizer_identity_hash,
            "detector_access_during_selection_observed": self.detector_access_during_selection_observed,
            "secret_access_during_selection_observed": self.secret_access_during_selection_observed,
            "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in self.rows),
            "comparison": self.comparison.payload() | {"comparison_hash": self.comparison.comparison_hash},
        }


def _row_sort_key(row: TinyDevResidualReplayRow) -> tuple[object, ...]:
    return (row.source_sample_id, row.schedule_policy, row.budget, row.schedule_seed, row.variant_hash)


def _sequence(name: str, value: object) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence")
    return value


def _mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    output = float(value)
    if not math.isfinite(output):
        raise ValueError(f"{name} must be finite")
    return output


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("pearson inputs must have equal length >= 2")
    lm, rm = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((x - lm) * (y - rm) for x, y in zip(left, right))
    lss = sum((x - lm) ** 2 for x in left)
    rss = sum((y - rm) ** 2 for y in right)
    return 0.0 if lss == 0.0 or rss == 0.0 else numerator / math.sqrt(lss * rss)


def _source_centered(rows: Sequence[TinyDevResidualReplayRow], field: str) -> tuple[float, ...]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row.source_sample_id].append(float(getattr(row, field)))
    means = {key: sum(values) / len(values) for key, values in grouped.items()}
    return tuple(float(getattr(row, field)) - means[row.source_sample_id] for row in rows)


def _fit(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    xm, ym = sum(x) / len(x), sum(y) / len(y)
    denominator = sum((value - xm) ** 2 for value in x)
    if denominator == 0.0:
        return ym, 0.0
    slope = sum((a - xm) * (b - ym) for a, b in zip(x, y)) / denominator
    return ym - slope * xm, slope


def _loso_rmse(rows: Sequence[TinyDevResidualReplayRow], predictor: str) -> float:
    errors: list[float] = []
    for held_out in sorted({row.source_sample_id for row in rows}):
        train = tuple(row for row in rows if row.source_sample_id != held_out)
        test = tuple(row for row in rows if row.source_sample_id == held_out)
        intercept, slope = _fit(
            tuple(float(getattr(row, predictor)) for row in train),
            tuple(row.margin_drop for row in train),
        )
        errors.extend((row.margin_drop - (intercept + slope * float(getattr(row, predictor)))) ** 2 for row in test)
    return math.sqrt(sum(errors) / len(errors))


def build_tiny_dev_residual_explanation_comparison(rows: Sequence[TinyDevResidualReplayRow]) -> TinyDevResidualExplanationComparison:
    primary = tuple(row for row in rows if row.source_label == "watermarked" and row.schedule_policy in PRIMARY_POLICIES)
    if len(primary) != 16 or len({row.source_sample_id for row in primary}) != 4:
        raise ValueError("frozen TinyDev primary residual comparison requires 16 watermarked rows from four sources")
    old_centered = _source_centered(primary, "root_destruction_fraction")
    new_centered = _source_centered(primary, "new_context_opportunity_fraction")
    margin_centered = _source_centered(primary, "margin_drop")
    old_corr = _pearson(old_centered, margin_centered)
    new_corr = _pearson(new_centered, margin_centered)
    old_rmse = _loso_rmse(primary, "root_destruction_fraction")
    new_rmse = _loso_rmse(primary, "new_context_opportunity_fraction")
    predictor_corr = _pearson(
        tuple(row.root_destruction_fraction for row in primary),
        tuple(row.new_context_opportunity_fraction for row in primary),
    )
    max_difference = max(abs(row.root_destruction_fraction - row.new_context_opportunity_fraction) for row in primary)
    decision = (
        ResidualReplayDecision.RESIDUAL_EXPLAINS_BETTER
        if new_rmse < old_rmse and abs(new_corr) > abs(old_corr)
        else ResidualReplayDecision.KILL_NEW_OBJECTIVE_KEEP_BEAM_V2
    )
    payload = {
        "algorithm_version": TINY_DEV_RESIDUAL_EXPLANATION_COMPARISON_VERSION,
        "independent_source_count": 4,
        "primary_row_count": 16,
        "old_predictor": "root_destruction_fraction",
        "new_predictor": "new_context_opportunity_fraction",
        "old_source_centered_pearson": old_corr,
        "new_source_centered_pearson": new_corr,
        "old_leave_one_source_out_rmse": old_rmse,
        "new_leave_one_source_out_rmse": new_rmse,
        "predictor_pearson": predictor_corr,
        "maximum_absolute_predictor_difference": max_difference,
        "decision": decision.value,
    }
    return TinyDevResidualExplanationComparison(
        TINY_DEV_RESIDUAL_EXPLANATION_COMPARISON_VERSION, 4, 16,
        "root_destruction_fraction", "new_context_opportunity_fraction",
        old_corr, new_corr, old_rmse, new_rmse, predictor_corr, max_difference,
        decision, sha256_json(payload),
    )


def replay_frozen_tiny_dev_residual_signal(
    plan: Mapping[str, object], evidence: Mapping[str, object], corpus: Mapping[str, object], *,
    retokenize: Callable[[str], Sequence[int]],
) -> TinyDevResidualReplayArtifact:
    if plan.get("source_code_commit") != FROZEN_BASELINE_SHA or evidence.get("source_code_commit") != FROZEN_BASELINE_SHA:
        raise ValueError("TinyDev replay source commit does not match frozen #47 baseline")
    if plan.get("plan_hash") != FROZEN_TINY_DEV_PLAN_HASH or evidence.get("plan_hash") != FROZEN_TINY_DEV_PLAN_HASH:
        raise ValueError("TinyDev replay plan hash does not match frozen baseline")
    if evidence.get("artifact_hash") != FROZEN_TINY_DEV_EVIDENCE_HASH or corpus.get("artifact_hash") != FROZEN_TINY_DEV_CORPUS_HASH:
        raise ValueError("TinyDev replay artifact hashes do not match frozen baseline")
    if evidence.get("detector_access_during_selection_observed") is not False or evidence.get("secret_access_during_selection_observed") is not False:
        raise ValueError("TinyDev evidence reports forbidden selection-time access")
    if plan.get("detector_access_observed") is not False or plan.get("secret_access_observed") is not False:
        raise ValueError("TinyDev plan reports forbidden selection-time access")
    tokenizer_identity_hash = plan.get("tokenizer_identity_hash")
    require_sha256("tokenizer_identity_hash", tokenizer_identity_hash)
    samples = _sequence("corpus samples", _mapping("manifest", corpus.get("manifest")).get("samples"))
    sample_map = {sample["sample_id"]: sample for value in samples if isinstance((sample := _mapping("sample", value)).get("sample_id"), str)}
    variants = tuple(_mapping("variant", value) for value in _sequence("plan variants", plan.get("variants")))
    scored_rows = tuple(_mapping("evidence row", value) for value in _sequence("evidence rows", evidence.get("rows")))
    scored_by_variant = {row.get("variant_hash"): row for row in scored_rows}
    if len(variants) != 384 or len(scored_rows) != 384 or len(scored_by_variant) != 384:
        raise ValueError("TinyDev replay requires the complete frozen 384-row matrix")
    ngram_len, history = plan.get("ngram_len"), plan.get("context_history_size")
    require_int("ngram_len", ngram_len)
    require_int("context_history_size", history)
    output: list[TinyDevResidualReplayRow] = []
    for variant in variants:
        variant_hash = variant.get("variant_hash")
        require_sha256("variant_hash", variant_hash)
        scored = scored_by_variant.get(variant_hash)
        if scored is None:
            raise ValueError("plan variant is missing from frozen evidence")
        source_id = variant.get("source_sample_id")
        sample = sample_map.get(source_id)
        if sample is None:
            raise ValueError("plan variant source is missing from frozen corpus")
        source_text, final_text = sample.get("text"), variant.get("transformed_text")
        if not isinstance(source_text, str) or not isinstance(final_text, str):
            raise TypeError("TinyDev replay text fields must be strings")
        if sha256_text(source_text) != variant.get("source_text_hash") or sha256_text(final_text) != variant.get("transformed_text_hash"):
            raise ValueError("TinyDev replay text hash mismatch")
        root_tokens = tuple(int(value) for value in _sequence("root token ids", _mapping("text track", sample.get("text_only_tokens")).get("token_ids")))
        final_tokens = tuple(int(value) for value in retokenize(final_text))
        eos_token_id = _mapping("model", sample.get("model")).get("eos_token_id")
        require_int("eos_token_id", eos_token_id)
        geometry = compute_residual_signal_geometry(root_tokens, final_tokens, eos_token_id=eos_token_id, ngram_len=ngram_len, context_history_size=history)
        leverage = build_structural_leverage_sidecar(
            variant_hash=variant_hash, source_text=source_text, transformed_text=final_text,
            geometry=geometry, operation_count=int(variant.get("realized_edit_cost")),
        )
        if geometry.alignment_distance != int(scored.get("alignment_distance")) or len(final_tokens) != int(scored.get("transformed_token_count")):
            raise ValueError("public tokenizer/alignment replay drifted from frozen evidence")
        old = _finite("exact_destruction_ratio", scored.get("exact_destruction_ratio"))
        row_payload = {
            "source_sample_id": str(source_id),
            "source_label": str(variant.get("source_label")),
            "schedule_policy": str(variant.get("schedule_policy")),
            "budget": int(variant.get("budget")),
            "schedule_seed": int(variant.get("schedule_seed")),
            "realized_edit_cost": int(variant.get("realized_edit_cost")),
            "variant_hash": variant_hash,
            "source_text_hash": str(variant.get("source_text_hash")),
            "transformed_text_hash": str(variant.get("transformed_text_hash")),
            "geometry_hash": geometry.geometry_hash,
            "root_valid_observation_count": geometry.root_valid_observation_count,
            "final_valid_observation_count": geometry.final_valid_observation_count,
            "preserved_root_valid_observation_count": geometry.preserved_root_valid_observation_count,
            "root_survival_fraction": geometry.root_survival_fraction,
            "root_destruction_fraction": geometry.root_destruction_fraction,
            "residual_inherited_fraction": geometry.residual_inherited_fraction,
            "new_context_opportunity_fraction": geometry.new_context_opportunity_fraction,
            "valid_denominator_ratio": geometry.valid_denominator_ratio,
            "repetition_mask_delta": geometry.repetition_mask_delta,
            "visible_word_edit_rate": leverage.visible_word_edit_rate,
            "visible_character_edit_rate": leverage.visible_character_edit_rate,
            "token_edit_distance": leverage.token_edit_distance,
            "protected_span_violation_count": protected_span_violation_count(source_text, final_text),
            "hard_invariant_status": str(variant.get("hard_invariant_status")),
            "old_exact_destruction_ratio": old,
            "margin_drop": _finite("margin_drop", scored.get("margin_drop")),
        }
        if abs(row_payload["root_destruction_fraction"] - old) > 1e-15:
            raise ValueError("new root destruction accounting drifted from frozen TinyDev exact destruction")
        output.append(TinyDevResidualReplayRow(**row_payload, row_hash=sha256_json(row_payload)))
    rows = tuple(sorted(output, key=_row_sort_key))
    comparison = build_tiny_dev_residual_explanation_comparison(rows)
    payload = {
        "algorithm_version": TINY_DEV_RESIDUAL_REPLAY_ALGORITHM_VERSION,
        "source_code_commit": FROZEN_BASELINE_SHA,
        "plan_hash": FROZEN_TINY_DEV_PLAN_HASH,
        "evidence_hash": FROZEN_TINY_DEV_EVIDENCE_HASH,
        "tiny_dev_corpus_hash": FROZEN_TINY_DEV_CORPUS_HASH,
        "tokenizer_identity_hash": tokenizer_identity_hash,
        "detector_access_during_selection_observed": False,
        "secret_access_during_selection_observed": False,
        "rows": tuple(row.payload() | {"row_hash": row.row_hash} for row in rows),
        "comparison": comparison.payload() | {"comparison_hash": comparison.comparison_hash},
    }
    return TinyDevResidualReplayArtifact(
        TINY_DEV_RESIDUAL_REPLAY_ALGORITHM_VERSION, FROZEN_BASELINE_SHA, FROZEN_TINY_DEV_PLAN_HASH,
        FROZEN_TINY_DEV_EVIDENCE_HASH, FROZEN_TINY_DEV_CORPUS_HASH, tokenizer_identity_hash,
        False, False, rows, comparison, sha256_json(payload),
    )
