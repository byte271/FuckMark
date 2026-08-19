from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .._validation import require_int, require_sha256
from ..corpus.mid_dev import MidDevAttackArtifact
from ..corpus.mid_dev_validation import validate_mid_dev_experiment_identity
from ..experiments.residual_signal_geometry import compute_residual_signal_geometry
from ..geometry import CounterfactualGeometryEngine, GeometryConfig, PublicRepetitionGeometry
from ..hashing import sha256_json
from ..scheduling.context_survival import ContextSurvivalExpander
from ..search.normalized_random_safe import (
    MATCHED_COST_RANDOM_SAFE_VERSION,
    MatchedVisibleCostEnvelope,
    derive_matched_cost_random_seed,
    matched_cost_random_safe_search,
)
from ..search.visible_cost_budget import (
    VisibleCostTier,
    assess_visible_cost,
    policy_for_tier,
    visible_cost_beam_search,
)
from ..transforms.contractions import contraction_inverse_semantic_resolver
from ..transforms.hard_invariants import validate_hard_invariants
from .context_survival_plan import _context_registry, _encode_with_offsets
from .mid_dev_context_survival import MID_DEV_RANDOM_REPLICATES, MidDevSelectionConfig
from .mid_dev_plan_builder import (
    MidDevSelectionTraceArtifact,
    _CountingMemoizedExpander,
    _token_ids,
    build_mid_dev_context_survival_plan,
)
from .mid_dev_plan_v5 import (
    MID_DEV_DEVELOPMENT_PLAN_VERSION,
    MID_DEV_NORMALIZED_RANDOM_SAFE_VERSION,
    MidDevDevelopmentPlanV5,
    MidDevNormalizedCostRow,
    MidDevNormalizedPlanner,
)


MID_DEV_V5_BUILDER_VERSION = "mid-dev-v5-development-plan-builder-v1"
MID_DEV_NORMALIZED_TRACE_VERSION = "mid-dev-normalized-selection-trace-v1"
MID_DEV_NORMALIZED_TRACE_ARTIFACT_VERSION = "mid-dev-normalized-trace-artifact-v1"
MID_DEV_V5_REQUIRED_CELL_REGISTRY = (
    "LEGACY_NO_OP",
    "LEGACY_CURRENT_STRONGEST_KEY_BLIND_BASELINE_B1_B2_B4_B6",
    "LEGACY_CONTEXT_SURVIVAL_GREEDY_B1_B2_B4_B6",
    "LEGACY_CONTEXT_SURVIVAL_BEAM_V2_B4_B6",
    "NORMALIZED_BEAM_V2_STRICT",
    "NORMALIZED_BEAM_V2_RELAXED",
    "NORMALIZED_RANDOM_SAFE_MATCHED_COST_STRICT_X16",
    "NORMALIZED_RANDOM_SAFE_MATCHED_COST_RELAXED_X16",
)
MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH = sha256_json(MID_DEV_V5_REQUIRED_CELL_REGISTRY)


@dataclass(frozen=True, slots=True)
class MidDevNormalizedSelectionTrace:
    source_group_id: str
    sample_id: str
    planner: MidDevNormalizedPlanner
    tier: VisibleCostTier
    replicate: int
    seed: int
    policy_hash: str
    candidate_registry_hash: str
    reference_state_hash: str | None
    matched_cost_envelope_hash: str | None
    search_result_hash: str
    final_search_state_hash: str
    candidate_hashes: tuple[str, ...]
    operation_hashes: tuple[str, ...]
    rule_hashes: tuple[str, ...]
    status: str
    detector_access_observed: bool
    secret_access_observed: bool
    trace_hash: str

    def __post_init__(self) -> None:
        for name in ("source_group_id", "sample_id", "status"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be non-empty")
        if not isinstance(self.planner, MidDevNormalizedPlanner):
            raise TypeError("planner must be MidDevNormalizedPlanner")
        if not isinstance(self.tier, VisibleCostTier):
            raise TypeError("tier must be VisibleCostTier")
        require_int("replicate", self.replicate)
        require_int("seed", self.seed)
        if self.replicate < 0 or self.seed < 0 or self.seed >= 1 << 64:
            raise ValueError("invalid replicate or seed")
        for name in (
            "policy_hash",
            "candidate_registry_hash",
            "search_result_hash",
            "final_search_state_hash",
            "trace_hash",
        ):
            require_sha256(name, getattr(self, name))
        for name in ("reference_state_hash", "matched_cost_envelope_hash"):
            value = getattr(self, name)
            if value is not None:
                require_sha256(name, value)
        if self.planner is MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2:
            if self.replicate != 0 or self.seed != 0:
                raise ValueError("Beam v2 normalized traces require replicate=seed=0")
            if self.reference_state_hash is not None or self.matched_cost_envelope_hash is not None:
                raise ValueError("Beam v2 normalized traces cannot carry matched-random references")
        else:
            if not 0 <= self.replicate < MID_DEV_RANDOM_REPLICATES:
                raise ValueError("random-safe normalized trace replicate is outside frozen range")
            if self.reference_state_hash is None or self.matched_cost_envelope_hash is None:
                raise ValueError("matched-cost random trace requires Beam v2 reference and envelope")
        for values in (self.candidate_hashes, self.operation_hashes, self.rule_hashes):
            if not isinstance(values, tuple):
                raise TypeError("trace hash sequences must be tuples")
            for value in values:
                require_sha256("trace member hash", value)
        if len(self.operation_hashes) != len(self.rule_hashes):
            raise ValueError("operation/rule hash sequences must align")
        if self.planner is MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST and len(self.candidate_hashes) != len(self.operation_hashes):
            raise ValueError("random-safe candidate/operation trace lengths must align")
        if type(self.detector_access_observed) is not bool or type(self.secret_access_observed) is not bool:
            raise TypeError("selection access flags must be bool")
        if self.detector_access_observed or self.secret_access_observed:
            raise ValueError("normalized selection trace is contaminated")
        if self.trace_hash != sha256_json(self.payload()):
            raise ValueError("normalized selection trace hash mismatch")

    @classmethod
    def create(cls, **values) -> "MidDevNormalizedSelectionTrace":
        payload_values = dict(values)
        payload = {
            "algorithm_version": MID_DEV_NORMALIZED_TRACE_VERSION,
            **{
                key: (
                    value.value
                    if isinstance(value, (MidDevNormalizedPlanner, VisibleCostTier))
                    else value
                )
                for key, value in payload_values.items()
            },
        }
        return cls(**payload_values, trace_hash=sha256_json(payload))

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_NORMALIZED_TRACE_VERSION,
            "source_group_id": self.source_group_id,
            "sample_id": self.sample_id,
            "planner": self.planner.value,
            "tier": self.tier.value,
            "replicate": self.replicate,
            "seed": self.seed,
            "policy_hash": self.policy_hash,
            "candidate_registry_hash": self.candidate_registry_hash,
            "reference_state_hash": self.reference_state_hash,
            "matched_cost_envelope_hash": self.matched_cost_envelope_hash,
            "search_result_hash": self.search_result_hash,
            "final_search_state_hash": self.final_search_state_hash,
            "candidate_hashes": self.candidate_hashes,
            "operation_hashes": self.operation_hashes,
            "rule_hashes": self.rule_hashes,
            "status": self.status,
            "detector_access_observed": self.detector_access_observed,
            "secret_access_observed": self.secret_access_observed,
        }


@dataclass(frozen=True, slots=True)
class MidDevNormalizedTraceArtifact:
    development_plan_hash: str
    required_cell_registry_hash: str
    traces: tuple[MidDevNormalizedSelectionTrace, ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        require_sha256("development_plan_hash", self.development_plan_hash)
        require_sha256("required_cell_registry_hash", self.required_cell_registry_hash)
        if self.required_cell_registry_hash != MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH:
            raise ValueError("required development cell registry drifted")
        if not isinstance(self.traces, tuple) or not self.traces:
            raise ValueError("normalized trace artifact requires traces")
        if any(not isinstance(value, MidDevNormalizedSelectionTrace) for value in self.traces):
            raise TypeError("normalized trace artifact contains invalid trace")
        if len({value.trace_hash for value in self.traces}) != len(self.traces):
            raise ValueError("normalized trace hashes must be unique")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("normalized trace artifact hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        development_plan_hash: str,
        traces: tuple[MidDevNormalizedSelectionTrace, ...],
    ) -> "MidDevNormalizedTraceArtifact":
        normalized = tuple(
            sorted(
                traces,
                key=lambda value: (
                    value.sample_id,
                    value.planner.value,
                    value.tier.value,
                    value.replicate,
                ),
            )
        )
        payload = {
            "algorithm_version": MID_DEV_NORMALIZED_TRACE_ARTIFACT_VERSION,
            "development_plan_hash": development_plan_hash,
            "required_cell_registry_hash": MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
            "trace_hashes": tuple(value.trace_hash for value in normalized),
        }
        return cls(
            development_plan_hash=development_plan_hash,
            required_cell_registry_hash=MID_DEV_V5_REQUIRED_CELL_REGISTRY_HASH,
            traces=normalized,
            artifact_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_NORMALIZED_TRACE_ARTIFACT_VERSION,
            "development_plan_hash": self.development_plan_hash,
            "required_cell_registry_hash": self.required_cell_registry_hash,
            "trace_hashes": tuple(value.trace_hash for value in self.traces),
        }


def _visible_operation_ceiling(source_text: str, tier: VisibleCostTier) -> int:
    policy = policy_for_tier(tier)
    return max(1, int(math.floor(policy.character_edit_rate_max * len(source_text) + 1e-12)))


def _replay_rule_hashes(registry, root_text: str, operation_hashes: tuple[str, ...]) -> tuple[str, ...]:
    text = root_text
    rule_hashes: list[str] = []
    for operation_hash in operation_hashes:
        enumeration = registry.enumerate(text)
        matched = None
        for candidate in enumeration.candidates:
            try:
                result = registry.apply(enumeration, (candidate.candidate_id,))
            except (KeyError, ValueError):
                continue
            operations = tuple(result.trace.operations)
            if len(operations) == 1 and operations[0].operation_hash == operation_hash:
                matched = (result.output_text, operations[0].rule_hash)
                break
        if matched is None:
            raise ValueError("cannot replay normalized operation hash against frozen registry")
        text, rule_hash = matched
        rule_hashes.append(rule_hash)
    return tuple(rule_hashes)


def _normalized_row(
    *,
    source: Any,
    tokenizer: Any,
    eos_token_id: int,
    ngram_len: int,
    context_history_size: int,
    candidate_registry_hash: str,
    planner: MidDevNormalizedPlanner,
    tier: VisibleCostTier,
    replicate: int,
    state,
    result_hash: str,
    trace: MidDevNormalizedSelectionTrace,
    maximum_search_operations: int,
) -> MidDevNormalizedCostRow:
    policy = policy_for_tier(tier)
    assessment = assess_visible_cost(source.text, state, policy)
    final_tokens = _token_ids(tokenizer, state.text)
    if source.text_only_tokens is None:
        raise ValueError("MidDev source has no text-only token track")
    geometry = compute_residual_signal_geometry(
        source.text_only_tokens.token_ids,
        final_tokens,
        eos_token_id=eos_token_id,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    hard = validate_hard_invariants(source.text, state.text)
    hard_passed = getattr(hard.status, "value", hard.status) == "pass"
    return MidDevNormalizedCostRow.create(
        source_group_id=source.match_id,
        sample_id=source.sample_id,
        source_text_hash=source.text_sha256,
        planner=planner,
        tier=tier,
        replicate=replicate,
        candidate_registry_hash=candidate_registry_hash,
        maximum_search_operations=maximum_search_operations,
        realized_operation_count=state.depth,
        transformed_text=state.text,
        final_search_state_hash=state.search_state_hash,
        search_result_hash=result_hash,
        selection_trace_hash=trace.trace_hash,
        residual_geometry_hash=geometry.geometry_hash,
        word_edit_rate=assessment.word_edit_rate,
        character_edit_rate=assessment.character_edit_rate,
        token_edit_distance=state.token_edit_distance,
        length_ratio=assessment.length_ratio,
        protected_span_violation_count=assessment.protected_span_violation_count,
        hard_invariant_passed=hard_passed,
    )


def build_mid_dev_development_plan_v5(
    artifact: MidDevAttackArtifact,
    tokenizer: Any,
    *,
    source_code_commit: str,
    ngram_len: int = 5,
    context_history_size: int = 1024,
) -> tuple[
    MidDevDevelopmentPlanV5,
    MidDevSelectionTraceArtifact,
    MidDevNormalizedTraceArtifact,
]:
    validate_mid_dev_experiment_identity(artifact)
    eos_token_id = getattr(tokenizer, "eos_token_id", None)
    if isinstance(eos_token_id, bool) or not isinstance(eos_token_id, int) or eos_token_id < 0:
        raise ValueError("normalized MidDev planning requires a non-negative tokenizer eos_token_id")
    legacy_plan, legacy_traces = build_mid_dev_context_survival_plan(
        artifact,
        tokenizer,
        ngram_len=ngram_len,
        context_history_size=context_history_size,
        source_code_commit=source_code_commit,
    )
    config = MidDevSelectionConfig.frozen()
    registry = _context_registry()
    repetition = PublicRepetitionGeometry.create(
        ngram_len=ngram_len,
        context_history_size=context_history_size,
    )
    rows: list[MidDevNormalizedCostRow] = []
    traces: list[MidDevNormalizedSelectionTrace] = []
    samples = tuple(sorted(artifact.manifest.samples, key=lambda value: value.sample_id))
    for source in samples:
        token_ids, _ = _encode_with_offsets(tokenizer, source)
        geometry_config = GeometryConfig.create(
            tokenizer_identity_hash=source.model.identity_hash,
            ngram_len=ngram_len,
            repetition_mask_policy_id=repetition.policy_id,
        )
        geometry_engine = CounterfactualGeometryEngine(
            tokenizer=tokenizer,
            config=geometry_config,
            eligibility_policy=repetition.eligibility_policy,
        )
        base = ContextSurvivalExpander(
            registry=registry,
            geometry_engine=geometry_engine,
            source_sample_id=source.sample_id,
            source_text=source.text,
            max_risk_tier=config.max_risk_tier,
            inverse_semantic_resolver=contraction_inverse_semantic_resolver,
        )
        expander = _CountingMemoizedExpander(base)
        root = base.root_state
        replay_root = geometry_engine.build_root(
            source_sample_id=source.sample_id,
            source_text=source.text,
        )
        if tuple(replay_root.root_tokens) != token_ids:
            raise ValueError("normalized MidDev root tokenization does not replay frozen text-only tokens")
        for tier in (VisibleCostTier.STRICT, VisibleCostTier.RELAXED):
            policy = policy_for_tier(tier)
            operation_ceiling = _visible_operation_ceiling(source.text, tier)
            beam_result = visible_cost_beam_search(
                expander,
                root,
                root_text=source.text,
                tier=tier,
                beam_width=config.beam_width,
                maximum_search_operations=operation_ceiling,
            )
            beam_state = beam_result.states[0]
            beam_rule_hashes = _replay_rule_hashes(registry, source.text, beam_state.operation_hashes)
            beam_trace = MidDevNormalizedSelectionTrace.create(
                source_group_id=source.match_id,
                sample_id=source.sample_id,
                planner=MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
                tier=tier,
                replicate=0,
                seed=0,
                policy_hash=policy.policy_hash,
                candidate_registry_hash=registry.ruleset_hash,
                reference_state_hash=None,
                matched_cost_envelope_hash=None,
                search_result_hash=beam_result.result_hash,
                final_search_state_hash=beam_state.search_state_hash,
                candidate_hashes=(),
                operation_hashes=beam_state.operation_hashes,
                rule_hashes=beam_rule_hashes,
                status="NORMALIZED_FRONTIER",
                detector_access_observed=beam_result.detector_access_observed,
                secret_access_observed=beam_result.secret_access_observed,
            )
            traces.append(beam_trace)
            rows.append(
                _normalized_row(
                    source=source,
                    tokenizer=tokenizer,
                    eos_token_id=eos_token_id,
                    ngram_len=ngram_len,
                    context_history_size=context_history_size,
                    candidate_registry_hash=registry.ruleset_hash,
                    planner=MidDevNormalizedPlanner.CONTEXT_SURVIVAL_BEAM_V2,
                    tier=tier,
                    replicate=0,
                    state=beam_state,
                    result_hash=beam_result.result_hash,
                    trace=beam_trace,
                    maximum_search_operations=operation_ceiling,
                )
            )
            envelope = MatchedVisibleCostEnvelope.from_reference(
                root_text=source.text,
                tier=tier,
                reference_state=beam_state,
            )
            for replicate in range(MID_DEV_RANDOM_REPLICATES):
                seed = derive_matched_cost_random_seed(source.sample_id, tier, replicate)
                random_result = matched_cost_random_safe_search(
                    expander,
                    root,
                    root_text=source.text,
                    envelope=envelope,
                    seed=seed,
                )
                random_state = random_result.final_state
                random_rule_hashes = _replay_rule_hashes(
                    registry,
                    source.text,
                    random_state.operation_hashes,
                )
                random_trace = MidDevNormalizedSelectionTrace.create(
                    source_group_id=source.match_id,
                    sample_id=source.sample_id,
                    planner=MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST,
                    tier=tier,
                    replicate=replicate,
                    seed=seed,
                    policy_hash=policy.policy_hash,
                    candidate_registry_hash=registry.ruleset_hash,
                    reference_state_hash=beam_state.search_state_hash,
                    matched_cost_envelope_hash=envelope.envelope_hash,
                    search_result_hash=random_result.result_hash,
                    final_search_state_hash=random_state.search_state_hash,
                    candidate_hashes=random_result.candidate_hashes,
                    operation_hashes=random_state.operation_hashes,
                    rule_hashes=random_rule_hashes,
                    status=random_result.status,
                    detector_access_observed=random_result.detector_access_observed,
                    secret_access_observed=random_result.secret_access_observed,
                )
                traces.append(random_trace)
                rows.append(
                    _normalized_row(
                        source=source,
                        tokenizer=tokenizer,
                        eos_token_id=eos_token_id,
                        ngram_len=ngram_len,
                        context_history_size=context_history_size,
                        candidate_registry_hash=registry.ruleset_hash,
                        planner=MidDevNormalizedPlanner.RANDOM_SAFE_MATCHED_COST,
                        tier=tier,
                        replicate=replicate,
                        state=random_state,
                        result_hash=random_result.result_hash,
                        trace=random_trace,
                        maximum_search_operations=envelope.max_operation_count,
                    )
                )
        if expander.detector_access_observed or expander.secret_access_observed:
            raise ValueError("normalized MidDev planner observed prohibited selection access")
    expected_normalized_rows = len(samples) * 2 * (1 + MID_DEV_RANDOM_REPLICATES)
    if len(rows) != expected_normalized_rows:
        raise ValueError("normalized MidDev row matrix is incomplete")
    plan = MidDevDevelopmentPlanV5.create(
        source_code_commit=source_code_commit,
        legacy_plan=legacy_plan,
        normalized_rows=tuple(rows),
    )
    normalized_trace_artifact = MidDevNormalizedTraceArtifact.create(
        development_plan_hash=plan.plan_hash,
        traces=tuple(traces),
    )
    if {row.selection_trace_hash for row in plan.normalized_rows} != {
        trace.trace_hash for trace in normalized_trace_artifact.traces
    }:
        raise ValueError("normalized plan rows do not bind complete normalized trace artifact")
    return plan, legacy_traces, normalized_trace_artifact
