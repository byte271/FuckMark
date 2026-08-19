from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..detector_calibration import PRIMARY_TARGET_FPR
from ..hashing import sha256_json
from ..scheduling.algorithm_ids import CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION
from ..search.beam_v3_promotion import FROZEN_BEAM_V3_PROMOTION_LOCK
from ..search.visible_cost_budget import RELAXED_VISIBLE_COST_POLICY, STRICT_VISIBLE_COST_POLICY
from ..transforms.hard_invariants import HARD_INVARIANT_ALGORITHM_VERSION
from ..transforms.protected import PROTECTED_SPAN_ALGORITHM_VERSION
from ..transforms.scheduler import CANDIDATE_SCHEDULER_ALGORITHM_VERSION
from .mid_dev_analysis import MID_DEV_FROZEN_PRIMARY_CELLS_HASH
from .mid_dev_context_survival import MID_DEV_RANDOM_REPLICATES
from .mid_dev_plan_v5 import MID_DEV_DEVELOPMENT_PLAN_VERSION
from .residual_signal_geometry import RESIDUAL_SIGNAL_GEOMETRY_ALGORITHM_VERSION


PRE_RUN_SCIENTIFIC_LOCK_VERSION = "middev-pre-run-scientific-lock-v1"
PRE_RUN_ROLE = "DEVELOPMENT_PILOT_ONLY"
PRE_RUN_SOURCE_GROUP_COUNT = 36
PRE_RUN_SOURCE_SAMPLE_COUNT = 72
PRE_RUN_PROMPT_FAMILY_COUNT = 6
PRE_RUN_TARGET_LENGTHS = (128, 256)
PRE_RUN_KEY_SPLIT = "DEV_KEYS"
PRE_RUN_LEGACY_BUDGETS = (1, 2, 4, 6)
PRE_RUN_BOOTSTRAP_REPLICATES = 10_000
PRE_RUN_BOOTSTRAP_SEED_BASE = 0x4D494444455641
PRE_RUN_CALIBRATION_CONSISTENCY_RULE = "TARGET_FPR_MUST_LIE_WITHIN_EACH_CAL_AUDIT_EXACT_95_PERCENT_INTERVAL"
PRE_RUN_MULTIPLICITY_RULE = "DEVELOPMENT_ALL_FROZEN_PRIMARY_CELLS_ALWAYS_REPORTED_NO_POSTHOC_BEST_CELL_SELECTION_NO_CONFIRMATORY_PVALUE_CLAIM_V1"
PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE = "BLINDED_TO_LABEL_PLANNER_DETECTOR_AND_THRESHOLD__AUDIT_ALL_STRICT_NORMALIZED_BEAM_V2__PLUS_SHA256_SELECTED_25_PERCENT_OF_OTHER_TRANSFORMED_PRIMARY_ROWS_STRATIFIED_BY_DOMAIN_LENGTH_AND_LABEL__V1"
PRE_RUN_NORMALIZED_PRIMARY_CELLS = (
    "BEAM_V2_STRICT",
    "BEAM_V2_RELAXED",
    "RANDOM_SAFE_MATCHED_COST_STRICT",
    "RANDOM_SAFE_MATCHED_COST_RELAXED",
)
PRE_RUN_PRIMARY_METRICS = (
    "SOURCE_LEVEL_RIF",
    "SOURCE_LEVEL_NCF",
    "SOURCE_LEVEL_VDR",
    "SOURCE_LEVEL_CONTROL_ADJUSTED_DETECTOR_MARGIN_ADVANTAGE",
    "FIXED_1_PERCENT_FPR_TPR",
    "MATCHED_UNWATERMARKED_CONTROL_SHIFT",
    "WORD_CHARACTER_TOKEN_VISIBLE_COST",
)
PRE_RUN_PRIMARY_COMPARISONS = (
    "BEAM_V2_VS_RANDOM_AT_MATCHED_REALIZED_VISIBLE_COST",
    "WATERMARKED_EFFECT_MINUS_MATCHED_UNWATERMARKED_EFFECT",
    "STRICT_VS_RELAXED_NORMALIZED_FRONTIER",
    "ALL_SIX_LEGACY_PRIMARY_CELLS_ALWAYS_REPORTED",
)
PRE_RUN_INELIGIBILITY_RULES = (
    "VDR_BELOW_0_90",
    "VISIBLE_COST_TIER_VIOLATION",
    "PROTECTED_SPAN_CHANGED",
    "REPETITION_MASK_GROWTH_ABOVE_FROZEN_CAP",
    "DUPLICATED_FILLER_OR_REPETITION_GAMING",
    "HARD_SEMANTIC_OR_FIDELITY_INVARIANT_FAILURE",
)
PRE_RUN_QUALITY_GATES = (
    "STRICT_WORD_EDIT_RATE_LE_0_03",
    "STRICT_CHARACTER_EDIT_RATE_LE_0_015",
    "STRICT_LENGTH_RATIO_0_97_TO_1_03",
    "RELAXED_WORD_EDIT_RATE_LE_0_05",
    "RELAXED_CHARACTER_EDIT_RATE_LE_0_03",
    "PROTECTED_SPAN_VIOLATIONS_EQ_0",
    "HARD_INVARIANTS_PASS",
    "ORDINARY_STRUCTURAL_REPLACEMENT_VDR_GE_0_90",
    "NO_DUPLICATED_FILLER_OR_REPETITION_GAMING",
    "BLINDED_HUMAN_AUDIT_NO_MATERIAL_SEMANTIC_CHANGE",
)
PRE_RUN_STOP_RULES = (
    "D1_K2_MEANS_BEAM_V3_NOT_PROMOTED_AND_BEAM_V2_REMAINS_CANONICAL",
    "D2_IF_TARGET_1_PERCENT_FPR_IS_OUTSIDE_ANY_CAL_AUDIT_EXACT_95_PERCENT_INTERVAL_BLOCK_THRESHOLD_CROSSING_INTERPRETATION",
    "D3_IF_PRISTINE_WATERMARKED_TPR_IS_BELOW_FROZEN_INTERPRETABILITY_FLOOR_BLOCK_REMOVAL_CLAIM_FOR_THAT_CELL",
    "D4_IF_CONTEXT_SURVIVAL_DOES_NOT_BEAT_MATCHED_RANDOM_ON_FROZEN_SOURCE_LEVEL_STRUCTURAL_METRIC_KILL_STRUCTURAL_OPTIMIZER_ADVANTAGE_CLAIM",
    "D5_IF_STRUCTURAL_ADVANTAGE_DOES_NOT_TRANSLATE_DIRECTIONALLY_TO_CONTROL_ADJUSTED_DETECTOR_MARGIN_CLASSIFY_STRUCTURAL_METRIC_AS_INCOMPLETE_PREDICTOR",
    "D6_IF_MATCHED_UNWATERMARKED_CONTROL_SHIFT_EXCEEDS_FROZEN_RATIO_LIMIT_BLOCK_WATERMARK_SPECIFIC_DEGRADATION_CLAIM",
    "D7_ANY_MATERIAL_SEMANTIC_CHANGE_OR_PROTECTED_SPAN_FAILURE_REMOVES_RULE_FAMILY_AND_REQUIRES_NEW_DEVELOPMENT_VERSION",
    "SATURATION_TWO_CONSECUTIVE_BUDGET_INCREMENTS_WITH_MEDIAN_RIF_IMPROVEMENT_LT_0_01_AND_HIGHER_VISIBLE_COST_STOPS_BUDGET_ESCALATION",
)
PRE_RUN_FALLBACK_LOGIC = (
    "BEAM_V3_K2_FALLBACK_TO_BEAM_V2",
    "CALIBRATION_GATE_FAILURE_FIX_CALIBRATION_BEFORE_ATTACK_SCORING_INTERPRETATION",
    "STRUCTURAL_ADVANTAGE_FAILURE_KEEP_RANDOM_AS_REFERENCE_AND_KILL_OPTIMIZER_ADVANTAGE_CLAIM",
    "DETECTOR_TRANSLATION_FAILURE_REVISIT_MECHANISM_ONLY_ON_DEVELOPMENT_DATA",
    "NEGATIVE_CONTROL_GATE_FAILURE_CLASSIFY_EFFECT_AS_GENERIC_DISTRIBUTION_SHIFT",
    "FIDELITY_FAILURE_VERSION_BUMP_RULE_REGISTRY_BEFORE_NEW_DEVELOPMENT_RUN",
)


def _git_object_id(name: str, value: str) -> None:
    require_clean_string(name, value)
    if len(value) not in (40, 64) or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase 40- or 64-hex object ID")


def _canonical_nonempty_strings(name: str, values: tuple[str, ...]) -> None:
    if not isinstance(values, tuple) or not values:
        raise ValueError(f"{name} must be a non-empty tuple")
    for value in values:
        require_clean_string(name, value)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates")


@dataclass(frozen=True, slots=True)
class PreRunScientificLock:
    algorithm_version: str
    role: str
    source_code_commit: str
    development_plan_version: str
    development_plan_hash: str
    corpus_artifact_hash: str
    corpus_manifest_hash: str
    source_profile_hash: str
    analysis_split_hash: str
    model_tokenizer_identity_hash: str
    model_revision: str
    tokenizer_revision: str
    watermark_config_hash: str
    watermark_condition_hash: str
    detector_identity_hash: str
    detector_implementation_hash: str
    opportunity_audit_hash: str
    calibration_regime_decision_hash: str
    cal_select_manifest_hash: str
    cal_audit_manifest_hash: str
    threshold_registry_hash: str
    calibration_audit_artifact_hashes: tuple[str, ...]
    residual_signal_algorithm_version: str
    residual_signal_implementation_hash: str
    candidate_rule_registry_hash: str
    candidate_rule_hashes: tuple[str, ...]
    protected_span_algorithm_version: str
    protected_span_implementation_hash: str
    hard_invariant_algorithm_version: str
    candidate_scheduler_algorithm_version: str
    candidate_enumeration_policy_hash: str
    planner_algorithm_version: str
    beam_v3_promotion_lock_hash: str
    beam_v3_gate_decision: str
    beam_v3_promoted: bool
    strict_policy_hash: str
    relaxed_policy_hash: str
    normalized_frontier_artifact_hash: str
    legacy_primary_cells_hash: str
    normalized_primary_cells: tuple[str, ...]
    normalized_primary_cells_hash: str
    source_analysis_rules_hash: str
    bootstrap_seed_schedule_hash: str
    pilot_seed_schedule_hash: str
    random_safe_policy_hash: str
    random_safe_replicates: int
    pilot_source_group_count: int
    pilot_source_sample_count: int
    prompt_family_count: int
    target_lengths: tuple[int, ...]
    key_split: str
    legacy_budgets: tuple[int, ...]
    bootstrap_replicates: int
    bootstrap_seed_base: int
    calibration_target_fpr: float
    calibration_consistency_rule: str
    pristine_watermarked_tpr_interpretability_floor: float
    negative_control_shift_ratio_limit: float
    stop_rules: tuple[str, ...]
    primary_metrics: tuple[str, ...]
    primary_comparisons: tuple[str, ...]
    multiplicity_rule: str
    ineligibility_rules: tuple[str, ...]
    quality_gates: tuple[str, ...]
    fallback_logic: tuple[str, ...]
    human_audit_sampling_rule: str
    lock_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != PRE_RUN_SCIENTIFIC_LOCK_VERSION:
            raise ValueError("unsupported pre-run scientific lock version")
        if self.role != PRE_RUN_ROLE:
            raise ValueError("Real MidDev must be DEVELOPMENT_PILOT_ONLY")
        _git_object_id("source_code_commit", self.source_code_commit)
        if self.development_plan_version != MID_DEV_DEVELOPMENT_PLAN_VERSION:
            raise ValueError("pre-run lock requires the v5 development plan container")
        hash_fields = (
            "development_plan_hash", "corpus_artifact_hash", "corpus_manifest_hash", "source_profile_hash",
            "analysis_split_hash", "model_tokenizer_identity_hash", "watermark_config_hash", "watermark_condition_hash",
            "detector_identity_hash", "detector_implementation_hash", "opportunity_audit_hash",
            "calibration_regime_decision_hash", "cal_select_manifest_hash", "cal_audit_manifest_hash",
            "threshold_registry_hash", "residual_signal_implementation_hash", "candidate_rule_registry_hash",
            "protected_span_implementation_hash", "candidate_enumeration_policy_hash", "beam_v3_promotion_lock_hash",
            "strict_policy_hash", "relaxed_policy_hash", "normalized_frontier_artifact_hash", "legacy_primary_cells_hash",
            "normalized_primary_cells_hash", "source_analysis_rules_hash", "bootstrap_seed_schedule_hash",
            "pilot_seed_schedule_hash", "random_safe_policy_hash", "lock_hash",
        )
        for name in hash_fields:
            require_sha256(name, getattr(self, name))
        _git_object_id("model_revision", self.model_revision)
        _git_object_id("tokenizer_revision", self.tokenizer_revision)
        _canonical_nonempty_strings("calibration_audit_artifact_hashes", self.calibration_audit_artifact_hashes)
        for value in self.calibration_audit_artifact_hashes:
            require_sha256("calibration_audit_artifact_hash", value)
        _canonical_nonempty_strings("candidate_rule_hashes", self.candidate_rule_hashes)
        for value in self.candidate_rule_hashes:
            require_sha256("candidate_rule_hash", value)
        if self.cal_select_manifest_hash == self.cal_audit_manifest_hash:
            raise ValueError("CAL-SELECT and CAL-AUDIT manifests must be independent")
        if self.residual_signal_algorithm_version != RESIDUAL_SIGNAL_GEOMETRY_ALGORITHM_VERSION:
            raise ValueError("residual-signal algorithm version drifted")
        if self.protected_span_algorithm_version != PROTECTED_SPAN_ALGORITHM_VERSION:
            raise ValueError("protected-span algorithm version drifted")
        if self.hard_invariant_algorithm_version != HARD_INVARIANT_ALGORITHM_VERSION:
            raise ValueError("hard-invariant algorithm version drifted")
        if self.candidate_scheduler_algorithm_version != CANDIDATE_SCHEDULER_ALGORITHM_VERSION:
            raise ValueError("candidate scheduler algorithm version drifted")
        if self.planner_algorithm_version != CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION:
            raise ValueError("Beam v2 must remain the canonical planner after frozen K2")
        beam_lock = FROZEN_BEAM_V3_PROMOTION_LOCK
        if self.beam_v3_promotion_lock_hash != beam_lock.lock_hash:
            raise ValueError("Beam v3 promotion lock hash drifted")
        if self.beam_v3_gate_decision != beam_lock.gate_decision or self.beam_v3_promoted is not False:
            raise ValueError("Beam v3 must remain killed by frozen K2")
        if self.strict_policy_hash != STRICT_VISIBLE_COST_POLICY.policy_hash:
            raise ValueError("STRICT visible-cost policy hash drifted")
        if self.relaxed_policy_hash != RELAXED_VISIBLE_COST_POLICY.policy_hash:
            raise ValueError("RELAXED visible-cost policy hash drifted")
        if self.legacy_primary_cells_hash != MID_DEV_FROZEN_PRIMARY_CELLS_HASH:
            raise ValueError("six legacy primary cells drifted")
        if self.normalized_primary_cells != PRE_RUN_NORMALIZED_PRIMARY_CELLS:
            raise ValueError("normalized primary cells drifted")
        if self.normalized_primary_cells_hash != sha256_json(self.normalized_primary_cells):
            raise ValueError("normalized primary cell hash mismatch")
        for name in (
            "random_safe_replicates", "pilot_source_group_count", "pilot_source_sample_count", "prompt_family_count",
            "bootstrap_replicates", "bootstrap_seed_base",
        ):
            require_int(name, getattr(self, name))
        if self.random_safe_replicates != MID_DEV_RANDOM_REPLICATES:
            raise ValueError("random-safe replicate count drifted")
        if self.pilot_source_group_count != PRE_RUN_SOURCE_GROUP_COUNT:
            raise ValueError("development pilot must contain exactly 36 source groups")
        if self.pilot_source_sample_count != PRE_RUN_SOURCE_SAMPLE_COUNT:
            raise ValueError("development pilot must contain exactly 72 matched source samples")
        if self.prompt_family_count != PRE_RUN_PROMPT_FAMILY_COUNT:
            raise ValueError("development pilot must contain exactly six prompt families")
        if self.target_lengths != PRE_RUN_TARGET_LENGTHS:
            raise ValueError("development pilot target lengths drifted")
        if self.key_split != PRE_RUN_KEY_SPLIT:
            raise ValueError("development pilot must use DEV_KEYS only")
        if self.legacy_budgets != PRE_RUN_LEGACY_BUDGETS:
            raise ValueError("legacy B1/B2/B4/B6 budget registry drifted")
        if self.bootstrap_replicates != PRE_RUN_BOOTSTRAP_REPLICATES or self.bootstrap_seed_base != PRE_RUN_BOOTSTRAP_SEED_BASE:
            raise ValueError("source-level bootstrap schedule drifted")
        if self.calibration_target_fpr != PRIMARY_TARGET_FPR:
            raise ValueError("pre-run lock target FPR must remain 1%")
        if self.calibration_consistency_rule != PRE_RUN_CALIBRATION_CONSISTENCY_RULE:
            raise ValueError("CAL-AUDIT uncertainty rule drifted")
        for name in ("pristine_watermarked_tpr_interpretability_floor", "negative_control_shift_ratio_limit"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 < float(value) <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        exact_tuples = (
            ("stop_rules", self.stop_rules, PRE_RUN_STOP_RULES),
            ("primary_metrics", self.primary_metrics, PRE_RUN_PRIMARY_METRICS),
            ("primary_comparisons", self.primary_comparisons, PRE_RUN_PRIMARY_COMPARISONS),
            ("ineligibility_rules", self.ineligibility_rules, PRE_RUN_INELIGIBILITY_RULES),
            ("quality_gates", self.quality_gates, PRE_RUN_QUALITY_GATES),
            ("fallback_logic", self.fallback_logic, PRE_RUN_FALLBACK_LOGIC),
        )
        for name, actual, expected in exact_tuples:
            _canonical_nonempty_strings(name, actual)
            if actual != expected:
                raise ValueError(f"{name} drifted from preregistration")
        if self.multiplicity_rule != PRE_RUN_MULTIPLICITY_RULE:
            raise ValueError("development multiplicity rule drifted")
        if self.human_audit_sampling_rule != PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE:
            raise ValueError("human audit sampling rule drifted")
        if self.lock_hash != sha256_json(self.payload()):
            raise ValueError("pre-run scientific lock hash mismatch")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "lock_hash"}


def create_pre_run_scientific_lock(**values) -> PreRunScientificLock:
    values = dict(values)
    values.setdefault("algorithm_version", PRE_RUN_SCIENTIFIC_LOCK_VERSION)
    values.setdefault("role", PRE_RUN_ROLE)
    values.setdefault("development_plan_version", MID_DEV_DEVELOPMENT_PLAN_VERSION)
    values.setdefault("residual_signal_algorithm_version", RESIDUAL_SIGNAL_GEOMETRY_ALGORITHM_VERSION)
    values.setdefault("protected_span_algorithm_version", PROTECTED_SPAN_ALGORITHM_VERSION)
    values.setdefault("hard_invariant_algorithm_version", HARD_INVARIANT_ALGORITHM_VERSION)
    values.setdefault("candidate_scheduler_algorithm_version", CANDIDATE_SCHEDULER_ALGORITHM_VERSION)
    values.setdefault("planner_algorithm_version", CONTEXT_SURVIVAL_BEAM_V2_ALGORITHM_VERSION)
    values.setdefault("beam_v3_promotion_lock_hash", FROZEN_BEAM_V3_PROMOTION_LOCK.lock_hash)
    values.setdefault("beam_v3_gate_decision", FROZEN_BEAM_V3_PROMOTION_LOCK.gate_decision)
    values.setdefault("beam_v3_promoted", False)
    values.setdefault("strict_policy_hash", STRICT_VISIBLE_COST_POLICY.policy_hash)
    values.setdefault("relaxed_policy_hash", RELAXED_VISIBLE_COST_POLICY.policy_hash)
    values.setdefault("legacy_primary_cells_hash", MID_DEV_FROZEN_PRIMARY_CELLS_HASH)
    values.setdefault("normalized_primary_cells", PRE_RUN_NORMALIZED_PRIMARY_CELLS)
    values.setdefault("normalized_primary_cells_hash", sha256_json(PRE_RUN_NORMALIZED_PRIMARY_CELLS))
    values.setdefault("random_safe_replicates", MID_DEV_RANDOM_REPLICATES)
    values.setdefault("pilot_source_group_count", PRE_RUN_SOURCE_GROUP_COUNT)
    values.setdefault("pilot_source_sample_count", PRE_RUN_SOURCE_SAMPLE_COUNT)
    values.setdefault("prompt_family_count", PRE_RUN_PROMPT_FAMILY_COUNT)
    values.setdefault("target_lengths", PRE_RUN_TARGET_LENGTHS)
    values.setdefault("key_split", PRE_RUN_KEY_SPLIT)
    values.setdefault("legacy_budgets", PRE_RUN_LEGACY_BUDGETS)
    values.setdefault("bootstrap_replicates", PRE_RUN_BOOTSTRAP_REPLICATES)
    values.setdefault("bootstrap_seed_base", PRE_RUN_BOOTSTRAP_SEED_BASE)
    values.setdefault("calibration_target_fpr", PRIMARY_TARGET_FPR)
    values.setdefault("calibration_consistency_rule", PRE_RUN_CALIBRATION_CONSISTENCY_RULE)
    values.setdefault("stop_rules", PRE_RUN_STOP_RULES)
    values.setdefault("primary_metrics", PRE_RUN_PRIMARY_METRICS)
    values.setdefault("primary_comparisons", PRE_RUN_PRIMARY_COMPARISONS)
    values.setdefault("multiplicity_rule", PRE_RUN_MULTIPLICITY_RULE)
    values.setdefault("ineligibility_rules", PRE_RUN_INELIGIBILITY_RULES)
    values.setdefault("quality_gates", PRE_RUN_QUALITY_GATES)
    values.setdefault("fallback_logic", PRE_RUN_FALLBACK_LOGIC)
    values.setdefault("human_audit_sampling_rule", PRE_RUN_HUMAN_AUDIT_SAMPLING_RULE)
    payload = {name: value for name, value in values.items() if name != "lock_hash"}
    return PreRunScientificLock(**payload, lock_hash=sha256_json(payload))
