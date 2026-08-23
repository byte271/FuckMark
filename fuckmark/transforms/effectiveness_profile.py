from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .contractions import development_forward_contraction_rules
from .hard_invariants import HARD_INVARIANT_ALGORITHM_VERSION
from .lexical_rules import development_lexical_rules
from .registry import (
    TRANSFORM_APPLY_ALGORITHM_VERSION,
    TRANSFORM_REGISTRY_ALGORITHM_VERSION,
    TransformRegistry,
)
from .scheduler import CANDIDATE_SCHEDULER_ALGORITHM_VERSION
from .surface_rules import coverage_completion_surface_rules, development_surface_rules
from .syntax_rules import development_syntax_rules
from .tokenizer_geometry import TOKENIZER_GEOMETRY_ALGORITHM_VERSION


EFFECTIVENESS_PROFILE_ALGORITHM_VERSION = "effectiveness-transform-profile-v1"
KEY_BLIND_HIGH_COVERAGE_PROFILE_ID = "key-blind-high-coverage-v1"
KEY_BLIND_HIGH_COVERAGE_BUDGETS = (16,)
KEY_BLIND_HIGH_COVERAGE_SEED_BASE = 1_120_000
KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID = "key-blind-full-pool-coverage-v1"
KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE = 1_130_000
KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID = "key-blind-coverage-completion-v2"
KEY_BLIND_COVERAGE_COMPLETION_SEED_BASE = 1_140_000


@dataclass(frozen=True, slots=True)
class EffectivenessTransformProfile:
    algorithm_version: str
    profile_id: str
    budgets: tuple[int, ...]
    budget_unit: str
    schedule_policy_id: str
    schedule_seed_base: int
    replicate_count: int
    ngram_len: int
    ruleset_hash: str
    candidate_scheduler_algorithm_version: str
    tokenizer_geometry_algorithm_version: str
    hard_invariant_algorithm_version: str
    transform_registry_algorithm_version: str
    transform_apply_algorithm_version: str
    scientific_scope: str
    profile_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != EFFECTIVENESS_PROFILE_ALGORITHM_VERSION:
            raise ValueError("unsupported effectiveness profile algorithm version")
        for name in (
            "profile_id",
            "budget_unit",
            "schedule_policy_id",
            "candidate_scheduler_algorithm_version",
            "tokenizer_geometry_algorithm_version",
            "hard_invariant_algorithm_version",
            "transform_registry_algorithm_version",
            "transform_apply_algorithm_version",
            "scientific_scope",
        ):
            require_clean_string(name, getattr(self, name))
        if isinstance(self.ngram_len, bool) or not isinstance(self.ngram_len, int) or self.ngram_len <= 0:
            raise ValueError("ngram_len must be a positive integer")
        require_int("schedule_seed_base", self.schedule_seed_base)
        require_int("replicate_count", self.replicate_count)
        if self.schedule_seed_base < 0 or self.schedule_seed_base >= 1 << 64:
            raise ValueError("schedule_seed_base must be between 0 and 2^64-1")
        if self.replicate_count <= 0:
            raise ValueError("replicate_count must be positive")
        if not isinstance(self.budgets, tuple):
            raise TypeError("budgets must be a tuple")
        if (
            not self.budgets
            or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in self.budgets)
            or self.budgets != tuple(sorted(set(self.budgets)))
        ):
            raise ValueError("budgets must be unique positive integers in ascending order")
        require_sha256("ruleset_hash", self.ruleset_hash)
        require_sha256("profile_hash", self.profile_hash)
        if self.profile_hash != sha256_json(self.payload()):
            raise ValueError("profile_hash does not match effectiveness profile")

    @classmethod
    def create(
        cls,
        *,
        profile_id: str,
        budgets: tuple[int, ...],
        budget_unit: str,
        schedule_policy_id: str,
        schedule_seed_base: int,
        replicate_count: int,
        ngram_len: int,
        ruleset_hash: str,
        scientific_scope: str,
    ) -> EffectivenessTransformProfile:
        payload = {
            "algorithm_version": EFFECTIVENESS_PROFILE_ALGORITHM_VERSION,
            "profile_id": profile_id,
            "budgets": budgets,
            "budget_unit": budget_unit,
            "schedule_policy_id": schedule_policy_id,
            "schedule_seed_base": schedule_seed_base,
            "replicate_count": replicate_count,
            "ngram_len": ngram_len,
            "ruleset_hash": ruleset_hash,
            "candidate_scheduler_algorithm_version": CANDIDATE_SCHEDULER_ALGORITHM_VERSION,
            "tokenizer_geometry_algorithm_version": TOKENIZER_GEOMETRY_ALGORITHM_VERSION,
            "hard_invariant_algorithm_version": HARD_INVARIANT_ALGORITHM_VERSION,
            "transform_registry_algorithm_version": TRANSFORM_REGISTRY_ALGORITHM_VERSION,
            "transform_apply_algorithm_version": TRANSFORM_APPLY_ALGORITHM_VERSION,
            "scientific_scope": scientific_scope,
        }
        return cls(
            **payload,
            profile_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "profile_id": self.profile_id,
            "budgets": self.budgets,
            "budget_unit": self.budget_unit,
            "schedule_policy_id": self.schedule_policy_id,
            "schedule_seed_base": self.schedule_seed_base,
            "replicate_count": self.replicate_count,
            "ngram_len": self.ngram_len,
            "ruleset_hash": self.ruleset_hash,
            "candidate_scheduler_algorithm_version": self.candidate_scheduler_algorithm_version,
            "tokenizer_geometry_algorithm_version": self.tokenizer_geometry_algorithm_version,
            "hard_invariant_algorithm_version": self.hard_invariant_algorithm_version,
            "transform_registry_algorithm_version": self.transform_registry_algorithm_version,
            "transform_apply_algorithm_version": self.transform_apply_algorithm_version,
            "scientific_scope": self.scientific_scope,
        }


def key_blind_high_coverage_transform_registry(
    identifiers: Sequence[str] = (),
) -> TransformRegistry:
    return TransformRegistry(
        (
            *development_forward_contraction_rules(),
            *development_surface_rules(),
            *development_lexical_rules(),
            *development_syntax_rules(),
        ),
        identifiers,
    )


KEY_BLIND_HIGH_COVERAGE_PROFILE = EffectivenessTransformProfile.create(
    profile_id=KEY_BLIND_HIGH_COVERAGE_PROFILE_ID,
    budgets=KEY_BLIND_HIGH_COVERAGE_BUDGETS,
    budget_unit="operation",
    schedule_policy_id="COVERAGE_GREEDY_KEY_BLIND",
    schedule_seed_base=KEY_BLIND_HIGH_COVERAGE_SEED_BASE,
    replicate_count=1,
    ngram_len=5,
    ruleset_hash=key_blind_high_coverage_transform_registry().ruleset_hash,
    scientific_scope=(
        "Frozen detector-blind and key-blind B16 high-coverage development profile with one "
        "fixed source-index seed per sorted source; exploratory effectiveness evidence only "
        "and not release authorization"
    ),
)


def key_blind_full_pool_coverage_profile(
    budgets: tuple[int, ...],
) -> EffectivenessTransformProfile:
    if not isinstance(budgets, tuple):
        raise TypeError("budgets must be a tuple")
    return EffectivenessTransformProfile.create(
        profile_id=KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID,
        budgets=budgets,
        budget_unit="operation",
        schedule_policy_id="COVERAGE_GREEDY_KEY_BLIND",
        schedule_seed_base=KEY_BLIND_FULL_POOL_COVERAGE_SEED_BASE,
        replicate_count=1,
        ngram_len=5,
        ruleset_hash=key_blind_high_coverage_transform_registry().ruleset_hash,
        scientific_scope=(
            "Frozen detector-blind and key-blind budget-scaled coverage profile over the "
            "development ruleset with one fixed source-index seed per sorted source; "
            "exploratory effectiveness evidence only and not release authorization"
        ),
    )


def resolve_effectiveness_profile(
    profile_id: str,
    budgets: tuple[int, ...] = (),
) -> EffectivenessTransformProfile:
    require_clean_string("profile_id", profile_id)
    if profile_id == KEY_BLIND_HIGH_COVERAGE_PROFILE_ID:
        if budgets:
            raise ValueError("the frozen B16 profile does not accept custom budgets")
        return KEY_BLIND_HIGH_COVERAGE_PROFILE
    if profile_id == KEY_BLIND_FULL_POOL_COVERAGE_PROFILE_ID:
        if not budgets:
            raise ValueError("the full-pool coverage profile requires explicit budgets")
        return key_blind_full_pool_coverage_profile(budgets)
    if profile_id == KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID:
        if not budgets:
            raise ValueError("the coverage completion profile requires explicit budgets")
        return key_blind_coverage_completion_profile(budgets)
    raise ValueError("unknown effectiveness profile id")


def key_blind_coverage_completion_transform_registry(
    identifiers: Sequence[str] = (),
) -> TransformRegistry:
    return TransformRegistry(
        (
            *development_forward_contraction_rules(),
            *coverage_completion_surface_rules(),
            *development_lexical_rules(),
            *development_syntax_rules(),
        ),
        identifiers,
    )


def key_blind_coverage_completion_profile(
    budgets: tuple[int, ...],
) -> EffectivenessTransformProfile:
    if not isinstance(budgets, tuple):
        raise TypeError("budgets must be a tuple")
    return EffectivenessTransformProfile.create(
        profile_id=KEY_BLIND_COVERAGE_COMPLETION_PROFILE_ID,
        budgets=budgets,
        budget_unit="operation",
        schedule_policy_id="COVERAGE_GREEDY_KEY_BLIND",
        schedule_seed_base=KEY_BLIND_COVERAGE_COMPLETION_SEED_BASE,
        replicate_count=1,
        ngram_len=5,
        ruleset_hash=key_blind_coverage_completion_transform_registry().ruleset_hash,
        scientific_scope=(
            "Frozen detector-blind and key-blind coverage-completion profile extending the "
            "development ruleset surface list; exploratory effectiveness evidence only and "
            "not release authorization"
        ),
    )


def validate_effectiveness_profile_registry(
    profile: EffectivenessTransformProfile,
    registry: TransformRegistry,
) -> None:
    if not isinstance(profile, EffectivenessTransformProfile):
        raise TypeError("profile must be an EffectivenessTransformProfile")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    if profile.ruleset_hash != registry.ruleset_hash:
        raise ValueError("effectiveness profile ruleset does not match registry")
