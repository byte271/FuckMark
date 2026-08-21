from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .._validation import (
    require_bool,
    require_clean_string,
    require_int,
    require_sha256,
)
from ..hashing import sha256_json, sha256_text
from ..transforms import InvariantStatus, TransformRegistry, validate_hard_invariants
from ..transforms.candidate_artifacts import CandidateEnumeration, TransformCandidate
from .diverse_beam_corpus import DiverseBeamFrozenCorpus


NORMALIZATION_PROFILE_ALGORITHM_VERSION = "normalization-profile-v1"
NORMALIZATION_CANDIDATE_ROW_VERSION = "normalization-candidate-survival-row-v1"
NORMALIZATION_BUDGET_WITNESS_VERSION = "normalization-budget-witness-v1"
NORMALIZATION_SAMPLE_PROFILE_VERSION = "normalization-sample-profile-v1"
NORMALIZATION_SAMPLE_SUMMARY_VERSION = "normalization-sample-summary-v1"
NORMALIZATION_SURVIVAL_BENCHMARK_VERSION = "normalization-survival-benchmark-v1"
NORMALIZATION_SURVIVAL_BUDGETS = (1, 2, 4, 6)
NORMALIZATION_DURABLE_CHOICE_MIN_FRACTION = 0.5
NORMALIZATION_DURABLE_CHOICE_MIN_BUDGET = 2
N0_IDENTITY = "N0_IDENTITY"
N1_WHITESPACE_COLLAPSE = "N1_WHITESPACE_COLLAPSE"
N2_LINE_ENDINGS_LF = "N2_LINE_ENDINGS_LF"
N3_UNICODE_NFC = "N3_UNICODE_NFC"
N4_COPY_PASTE_WHITESPACE = "N4_COPY_PASTE_WHITESPACE"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_HORIZONTAL_RUN_RE = re.compile(r"[ \t]+")
_TRAILING_HORIZONTAL_RE = re.compile(r"[ \t]+(?=\r\n|\r|\n|$)")


@dataclass(frozen=True, slots=True)
class NormalizationProfile:
    profile_id: str
    ordinal: int
    canonicalize_line_endings: bool
    remove_trailing_horizontal_whitespace: bool
    collapse_horizontal_whitespace: bool
    unicode_normalization_form: str | None
    profile_hash: str

    def __post_init__(self) -> None:
        require_clean_string("profile_id", self.profile_id)
        require_int("ordinal", self.ordinal)
        if self.ordinal < 0:
            raise ValueError("normalization profile ordinal must be non-negative")
        for name in (
            "canonicalize_line_endings",
            "remove_trailing_horizontal_whitespace",
            "collapse_horizontal_whitespace",
        ):
            require_bool(name, getattr(self, name))
        if self.unicode_normalization_form not in (None, "NFC"):
            raise ValueError("unsupported Unicode normalization form")
        require_sha256("profile_hash", self.profile_hash)
        if self.profile_hash != sha256_json(self.payload()):
            raise ValueError("normalization profile hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        profile_id: str,
        ordinal: int,
        canonicalize_line_endings: bool,
        remove_trailing_horizontal_whitespace: bool,
        collapse_horizontal_whitespace: bool,
        unicode_normalization_form: str | None,
    ) -> NormalizationProfile:
        payload = {
            "algorithm_version": NORMALIZATION_PROFILE_ALGORITHM_VERSION,
            "profile_id": profile_id,
            "ordinal": ordinal,
            "canonicalize_line_endings": canonicalize_line_endings,
            "remove_trailing_horizontal_whitespace": remove_trailing_horizontal_whitespace,
            "collapse_horizontal_whitespace": collapse_horizontal_whitespace,
            "unicode_normalization_form": unicode_normalization_form,
        }
        return cls(
            profile_id=profile_id,
            ordinal=ordinal,
            canonicalize_line_endings=canonicalize_line_endings,
            remove_trailing_horizontal_whitespace=remove_trailing_horizontal_whitespace,
            collapse_horizontal_whitespace=collapse_horizontal_whitespace,
            unicode_normalization_form=unicode_normalization_form,
            profile_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": NORMALIZATION_PROFILE_ALGORITHM_VERSION,
            "profile_id": self.profile_id,
            "ordinal": self.ordinal,
            "canonicalize_line_endings": self.canonicalize_line_endings,
            "remove_trailing_horizontal_whitespace": self.remove_trailing_horizontal_whitespace,
            "collapse_horizontal_whitespace": self.collapse_horizontal_whitespace,
            "unicode_normalization_form": self.unicode_normalization_form,
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "profile_hash": self.profile_hash}


def normalization_profiles() -> tuple[NormalizationProfile, ...]:
    rows = (
        (N0_IDENTITY, False, False, False, None),
        (N1_WHITESPACE_COLLAPSE, False, True, True, None),
        (N2_LINE_ENDINGS_LF, True, False, False, None),
        (N3_UNICODE_NFC, False, False, False, "NFC"),
        (N4_COPY_PASTE_WHITESPACE, True, True, True, None),
    )
    return tuple(
        NormalizationProfile.create(
            profile_id=profile_id,
            ordinal=ordinal,
            canonicalize_line_endings=line_endings,
            remove_trailing_horizontal_whitespace=trailing,
            collapse_horizontal_whitespace=collapse,
            unicode_normalization_form=unicode_form,
        )
        for ordinal, (profile_id, line_endings, trailing, collapse, unicode_form) in enumerate(
            rows
        )
    )


def normalize_text(text: str, profile: NormalizationProfile) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(profile, NormalizationProfile):
        raise TypeError("profile must be a NormalizationProfile")
    output = text
    if profile.canonicalize_line_endings:
        output = output.replace("\r\n", "\n").replace("\r", "\n")
    if profile.remove_trailing_horizontal_whitespace:
        output = _TRAILING_HORIZONTAL_RE.sub("", output)
    if profile.collapse_horizontal_whitespace:
        output = _HORIZONTAL_RUN_RE.sub(" ", output)
    if profile.unicode_normalization_form is not None:
        output = unicodedata.normalize(profile.unicode_normalization_form, output)
    return output


@dataclass(frozen=True, slots=True)
class NormalizationCandidateRow:
    sample_id: str
    source_text_hash: str
    candidate_id: str
    rule_id: str
    rule_hash: str
    family: str
    tier: str
    start: int
    end: int
    transformed_text_hash: str
    invariant_safe: bool
    invariant_report_hash: str
    profile_id: str
    profile_hash: str
    normalized_source_hash: str
    normalized_output_hash: str
    survives: bool
    row_hash: str

    def __post_init__(self) -> None:
        for name in ("sample_id", "rule_id", "family", "tier", "profile_id"):
            require_clean_string(name, getattr(self, name))
        for name in (
            "source_text_hash",
            "candidate_id",
            "rule_hash",
            "transformed_text_hash",
            "invariant_report_hash",
            "profile_hash",
            "normalized_source_hash",
            "normalized_output_hash",
            "row_hash",
        ):
            require_sha256(name, getattr(self, name))
        require_int("start", self.start)
        require_int("end", self.end)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("candidate row geometry is invalid")
        require_bool("invariant_safe", self.invariant_safe)
        require_bool("survives", self.survives)
        if self.survives != (self.normalized_source_hash != self.normalized_output_hash):
            raise ValueError("candidate survival flag does not match normalized hashes")
        if self.row_hash != sha256_json(self.payload()):
            raise ValueError("normalization candidate row hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": NORMALIZATION_CANDIDATE_ROW_VERSION,
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name != "row_hash"
            },
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "row_hash": self.row_hash}


@dataclass(frozen=True, slots=True)
class NormalizationBudgetWitness:
    budget: int
    reachable: bool
    candidate_ids: tuple[str, ...]
    normalized_output_hash: str | None
    witness_hash: str

    def __post_init__(self) -> None:
        require_int("budget", self.budget)
        if self.budget not in NORMALIZATION_SURVIVAL_BUDGETS:
            raise ValueError("normalization witness budget drifted")
        require_bool("reachable", self.reachable)
        if not isinstance(self.candidate_ids, tuple):
            raise TypeError("candidate_ids must be a tuple")
        for value in self.candidate_ids:
            require_sha256("candidate_id", value)
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("normalization witness candidate IDs must be unique")
        if self.reachable:
            if len(self.candidate_ids) != self.budget:
                raise ValueError("reachable witness must bind its exact budget")
            require_sha256("normalized_output_hash", self.normalized_output_hash)
        elif self.candidate_ids or self.normalized_output_hash is not None:
            raise ValueError("unreachable witness cannot bind candidate output")
        require_sha256("witness_hash", self.witness_hash)
        if self.witness_hash != sha256_json(self.payload()):
            raise ValueError("normalization budget witness hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        budget: int,
        candidate_ids: Sequence[str] = (),
        normalized_output_hash: str | None = None,
    ) -> NormalizationBudgetWitness:
        ids = tuple(candidate_ids)
        reachable = bool(ids)
        payload = {
            "algorithm_version": NORMALIZATION_BUDGET_WITNESS_VERSION,
            "budget": budget,
            "reachable": reachable,
            "candidate_ids": ids,
            "normalized_output_hash": normalized_output_hash,
        }
        return cls(
            budget=budget,
            reachable=reachable,
            candidate_ids=ids,
            normalized_output_hash=normalized_output_hash,
            witness_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": NORMALIZATION_BUDGET_WITNESS_VERSION,
            "budget": self.budget,
            "reachable": self.reachable,
            "candidate_ids": self.candidate_ids,
            "normalized_output_hash": self.normalized_output_hash,
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "witness_hash": self.witness_hash}


@dataclass(frozen=True, slots=True)
class NormalizationSampleProfile:
    profile_id: str
    profile_hash: str
    invariant_safe_surviving_count: int
    independent_invariant_safe_surviving_count: int
    verified_compatible_prefix_count: int
    witness_search_rejection_count: int
    witnesses: tuple[NormalizationBudgetWitness, ...]
    summary_hash: str

    def __post_init__(self) -> None:
        require_clean_string("profile_id", self.profile_id)
        require_sha256("profile_hash", self.profile_hash)
        for name in (
            "invariant_safe_surviving_count",
            "independent_invariant_safe_surviving_count",
            "verified_compatible_prefix_count",
            "witness_search_rejection_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (
            self.independent_invariant_safe_surviving_count
            > self.invariant_safe_surviving_count
        ):
            raise ValueError("independent surviving count exceeds safe surviving count")
        if (
            self.verified_compatible_prefix_count
            > self.independent_invariant_safe_surviving_count
        ):
            raise ValueError("verified compatible count exceeds independent opportunity")
        if self.verified_compatible_prefix_count > max(NORMALIZATION_SURVIVAL_BUDGETS):
            raise ValueError("verified compatible prefix exceeds the benchmark budget")
        if not isinstance(self.witnesses, tuple) or any(
            not isinstance(value, NormalizationBudgetWitness) for value in self.witnesses
        ):
            raise TypeError("witnesses must contain NormalizationBudgetWitness values")
        if tuple(value.budget for value in self.witnesses) != NORMALIZATION_SURVIVAL_BUDGETS:
            raise ValueError("normalization sample profile budgets drifted")
        for witness in self.witnesses:
            if witness.reachable != (
                self.verified_compatible_prefix_count >= witness.budget
            ):
                raise ValueError("normalization witness reachability disagrees with opportunity")
        require_sha256("summary_hash", self.summary_hash)
        if self.summary_hash != sha256_json(self.payload()):
            raise ValueError("normalization sample profile hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": NORMALIZATION_SAMPLE_PROFILE_VERSION,
            "profile_id": self.profile_id,
            "profile_hash": self.profile_hash,
            "invariant_safe_surviving_count": self.invariant_safe_surviving_count,
            "independent_invariant_safe_surviving_count": (
                self.independent_invariant_safe_surviving_count
            ),
            "verified_compatible_prefix_count": self.verified_compatible_prefix_count,
            "witness_search_rejection_count": self.witness_search_rejection_count,
            "witnesses": tuple(value.as_dict() for value in self.witnesses),
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "summary_hash": self.summary_hash}


@dataclass(frozen=True, slots=True)
class NormalizationSampleSummary:
    sample_id: str
    source_text_hash: str
    enumeration_hash: str
    raw_candidate_count: int
    independent_candidate_count: int
    enumeration_rejection_count: int
    invariant_safe_count: int
    independent_invariant_safe_count: int
    invariant_rejection_count: int
    profiles: tuple[NormalizationSampleProfile, ...]
    summary_hash: str

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        for name in ("source_text_hash", "enumeration_hash", "summary_hash"):
            require_sha256(name, getattr(self, name))
        for name in (
            "raw_candidate_count",
            "independent_candidate_count",
            "enumeration_rejection_count",
            "invariant_safe_count",
            "independent_invariant_safe_count",
            "invariant_rejection_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.independent_candidate_count > self.raw_candidate_count:
            raise ValueError("independent candidate count exceeds raw candidates")
        if self.independent_invariant_safe_count > self.invariant_safe_count:
            raise ValueError("independent invariant-safe count exceeds safe candidates")
        if self.invariant_safe_count + self.invariant_rejection_count != self.raw_candidate_count:
            raise ValueError("sample invariant accounting is inconsistent")
        if not isinstance(self.profiles, tuple) or any(
            not isinstance(value, NormalizationSampleProfile) for value in self.profiles
        ):
            raise TypeError("profiles must contain NormalizationSampleProfile values")
        expected_profiles = normalization_profiles()
        if tuple(value.profile_hash for value in self.profiles) != tuple(
            value.profile_hash for value in expected_profiles
        ):
            raise ValueError("sample normalization profiles drifted")
        if any(
            value.invariant_safe_surviving_count > self.invariant_safe_count
            for value in self.profiles
        ):
            raise ValueError("profile safe-surviving count exceeds invariant-safe count")
        if self.summary_hash != sha256_json(self.payload()):
            raise ValueError("normalization sample summary hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": NORMALIZATION_SAMPLE_SUMMARY_VERSION,
            "sample_id": self.sample_id,
            "source_text_hash": self.source_text_hash,
            "enumeration_hash": self.enumeration_hash,
            "raw_candidate_count": self.raw_candidate_count,
            "independent_candidate_count": self.independent_candidate_count,
            "enumeration_rejection_count": self.enumeration_rejection_count,
            "invariant_safe_count": self.invariant_safe_count,
            "independent_invariant_safe_count": self.independent_invariant_safe_count,
            "invariant_rejection_count": self.invariant_rejection_count,
            "profiles": tuple(value.as_dict() for value in self.profiles),
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.payload(), "summary_hash": self.summary_hash}


def _maximum_nonoverlapping_candidates(
    candidates: Sequence[TransformCandidate],
) -> tuple[TransformCandidate, ...]:
    ordered = tuple(
        sorted(candidates, key=lambda value: (value.end, value.start, value.candidate_id))
    )
    output = []
    cursor = -1
    for candidate in ordered:
        if candidate.start < cursor:
            continue
        output.append(candidate)
        cursor = candidate.end
    return tuple(output)


def _candidate_output(source_text: str, candidate: TransformCandidate) -> str:
    if source_text[candidate.start : candidate.end] != candidate.source_text:
        raise RuntimeError("candidate source text does not match its recorded geometry")
    return (
        source_text[: candidate.start]
        + candidate.replacement_text
        + source_text[candidate.end :]
    )


def _selection_output(
    source_text: str,
    candidates: Sequence[TransformCandidate],
) -> str:
    ordered = tuple(
        sorted(candidates, key=lambda value: (value.start, value.end, value.candidate_id))
    )
    chunks = []
    cursor = 0
    for candidate in ordered:
        if candidate.start < cursor:
            raise RuntimeError("normalization witness candidates overlap")
        if source_text[candidate.start : candidate.end] != candidate.source_text:
            raise RuntimeError("candidate source text does not match its recorded geometry")
        chunks.append(source_text[cursor : candidate.start])
        chunks.append(candidate.replacement_text)
        cursor = candidate.end
    chunks.append(source_text[cursor:])
    return "".join(chunks)


def _normalized_witness_hash(
    *,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    profile: NormalizationProfile,
    candidates: Sequence[TransformCandidate],
    invariant_cache: dict[tuple[str, ...], bool],
) -> str | None:
    candidate_ids = tuple(value.candidate_id for value in candidates)
    output_text = _selection_output(source_text, candidates)
    invariant_safe = invariant_cache.get(candidate_ids)
    if invariant_safe is None:
        report = validate_hard_invariants(
            source_text,
            output_text,
            registry.identifiers,
            enumeration.protected_manifest.user_ranges,
        )
        invariant_safe = report.status is InvariantStatus.PASS
        invariant_cache[candidate_ids] = invariant_safe
    if not invariant_safe:
        return None
    normalized_output = normalize_text(output_text, profile)
    normalized_source = normalize_text(source_text, profile)
    if normalized_output == normalized_source:
        return None
    return sha256_text(normalized_output)


def _verified_compatible_prefix(
    *,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    profile: NormalizationProfile,
    candidates: Sequence[TransformCandidate],
    invariant_cache: dict[tuple[str, ...], bool],
) -> tuple[tuple[TransformCandidate, ...], int]:
    selected = []
    rejected = 0
    for candidate in candidates:
        trial = (*selected, candidate)
        if (
            _normalized_witness_hash(
                source_text=source_text,
                registry=registry,
                enumeration=enumeration,
                profile=profile,
                candidates=trial,
                invariant_cache=invariant_cache,
            )
            is None
        ):
            rejected += 1
            continue
        selected.append(candidate)
        if len(selected) == max(NORMALIZATION_SURVIVAL_BUDGETS):
            break
    return tuple(selected), rejected


def _validated_witness(
    *,
    source_text: str,
    registry: TransformRegistry,
    enumeration: CandidateEnumeration,
    profile: NormalizationProfile,
    candidates: Sequence[TransformCandidate],
    budget: int,
    invariant_cache: dict[tuple[str, ...], bool],
) -> NormalizationBudgetWitness:
    selected = tuple(candidates[:budget])
    if len(selected) < budget:
        return NormalizationBudgetWitness.create(budget=budget)
    normalized_output_hash = _normalized_witness_hash(
        source_text=source_text,
        registry=registry,
        enumeration=enumeration,
        profile=profile,
        candidates=selected,
        invariant_cache=invariant_cache,
    )
    if normalized_output_hash is None:
        raise RuntimeError("verified normalization witness no longer replays")
    return NormalizationBudgetWitness.create(
        budget=budget,
        candidate_ids=tuple(value.candidate_id for value in selected),
        normalized_output_hash=normalized_output_hash,
    )


def benchmark_normalization_source(
    *,
    sample_id: str,
    source_text: str,
    registry: TransformRegistry,
) -> tuple[NormalizationSampleSummary, tuple[NormalizationCandidateRow, ...]]:
    require_clean_string("sample_id", sample_id)
    if not isinstance(source_text, str) or not source_text:
        raise ValueError("source_text must be a non-empty string")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    profiles = normalization_profiles()
    enumeration = registry.enumerate(source_text)
    source_hash = sha256_text(source_text)
    safe_candidates = []
    candidate_rows = []
    surviving_by_profile: dict[str, list[TransformCandidate]] = defaultdict(list)
    invariant_cache: dict[tuple[str, ...], bool] = {}
    normalized_source_hashes = {
        profile.profile_id: sha256_text(normalize_text(source_text, profile))
        for profile in profiles
    }
    for candidate in enumeration.candidates:
        transformed_text = _candidate_output(source_text, candidate)
        invariant_report = validate_hard_invariants(
            source_text,
            transformed_text,
            registry.identifiers,
            enumeration.protected_manifest.user_ranges,
        )
        invariant_safe = invariant_report.status is InvariantStatus.PASS
        invariant_cache[(candidate.candidate_id,)] = invariant_safe
        if invariant_safe:
            safe_candidates.append(candidate)
        transformed_hash = sha256_text(transformed_text)
        for profile in profiles:
            normalized_source_hash = normalized_source_hashes[profile.profile_id]
            normalized_output_hash = sha256_text(normalize_text(transformed_text, profile))
            survives = normalized_source_hash != normalized_output_hash
            row_fields = {
                "sample_id": sample_id,
                "source_text_hash": source_hash,
                "candidate_id": candidate.candidate_id,
                "rule_id": candidate.rule_id,
                "rule_hash": candidate.rule_hash,
                "family": candidate.family.value,
                "tier": candidate.tier.value,
                "start": candidate.start,
                "end": candidate.end,
                "transformed_text_hash": transformed_hash,
                "invariant_safe": invariant_safe,
                "invariant_report_hash": invariant_report.report_hash,
                "profile_id": profile.profile_id,
                "profile_hash": profile.profile_hash,
                "normalized_source_hash": normalized_source_hash,
                "normalized_output_hash": normalized_output_hash,
                "survives": survives,
            }
            payload = {
                "algorithm_version": NORMALIZATION_CANDIDATE_ROW_VERSION,
                **row_fields,
            }
            candidate_rows.append(
                NormalizationCandidateRow(
                    **row_fields,
                    row_hash=sha256_json(payload),
                )
            )
            if invariant_safe and survives:
                surviving_by_profile[profile.profile_id].append(candidate)
    profile_summaries = []
    replayed_selections = set()
    for profile in profiles:
        surviving = tuple(surviving_by_profile[profile.profile_id])
        independent = _maximum_nonoverlapping_candidates(surviving)
        compatible, witness_search_rejections = _verified_compatible_prefix(
            source_text=source_text,
            registry=registry,
            enumeration=enumeration,
            profile=profile,
            candidates=independent,
            invariant_cache=invariant_cache,
        )
        compatible_ids = tuple(value.candidate_id for value in compatible)
        if compatible_ids and compatible_ids not in replayed_selections:
            replay = registry.apply(enumeration, compatible_ids)
            if replay.output_text != _selection_output(source_text, compatible):
                raise RuntimeError("registry witness replay disagrees with direct application")
            replayed_selections.add(compatible_ids)
        witnesses = tuple(
            _validated_witness(
                source_text=source_text,
                registry=registry,
                enumeration=enumeration,
                profile=profile,
                candidates=compatible,
                budget=budget,
                invariant_cache=invariant_cache,
            )
            for budget in NORMALIZATION_SURVIVAL_BUDGETS
        )
        payload = {
            "algorithm_version": NORMALIZATION_SAMPLE_PROFILE_VERSION,
            "profile_id": profile.profile_id,
            "profile_hash": profile.profile_hash,
            "invariant_safe_surviving_count": len(surviving),
            "independent_invariant_safe_surviving_count": len(independent),
            "verified_compatible_prefix_count": len(compatible),
            "witness_search_rejection_count": witness_search_rejections,
            "witnesses": tuple(value.as_dict() for value in witnesses),
        }
        profile_summaries.append(
            NormalizationSampleProfile(
                profile_id=profile.profile_id,
                profile_hash=profile.profile_hash,
                invariant_safe_surviving_count=len(surviving),
                independent_invariant_safe_surviving_count=len(independent),
                verified_compatible_prefix_count=len(compatible),
                witness_search_rejection_count=witness_search_rejections,
                witnesses=witnesses,
                summary_hash=sha256_json(payload),
            )
        )
    independent_raw = _maximum_nonoverlapping_candidates(enumeration.candidates)
    independent_safe = _maximum_nonoverlapping_candidates(safe_candidates)
    payload = {
        "algorithm_version": NORMALIZATION_SAMPLE_SUMMARY_VERSION,
        "sample_id": sample_id,
        "source_text_hash": source_hash,
        "enumeration_hash": enumeration.enumeration_hash,
        "raw_candidate_count": len(enumeration.candidates),
        "independent_candidate_count": len(independent_raw),
        "enumeration_rejection_count": len(enumeration.rejections),
        "invariant_safe_count": len(safe_candidates),
        "independent_invariant_safe_count": len(independent_safe),
        "invariant_rejection_count": len(enumeration.candidates) - len(safe_candidates),
        "profiles": tuple(value.as_dict() for value in profile_summaries),
    }
    summary = NormalizationSampleSummary(
        sample_id=sample_id,
        source_text_hash=source_hash,
        enumeration_hash=enumeration.enumeration_hash,
        raw_candidate_count=len(enumeration.candidates),
        independent_candidate_count=len(independent_raw),
        enumeration_rejection_count=len(enumeration.rejections),
        invariant_safe_count=len(safe_candidates),
        independent_invariant_safe_count=len(independent_safe),
        invariant_rejection_count=len(enumeration.candidates) - len(safe_candidates),
        profiles=tuple(profile_summaries),
        summary_hash=sha256_json(payload),
    )
    return summary, tuple(candidate_rows)


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _aggregate_rows(
    rows: Sequence[NormalizationCandidateRow],
    key_name: str,
) -> tuple[dict[str, object], ...]:
    grouped: dict[tuple[str, str], list[NormalizationCandidateRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.profile_id, getattr(row, key_name))].append(row)
    output = []
    for (profile_id, label), values in sorted(grouped.items()):
        safe = sum(value.invariant_safe for value in values)
        surviving = sum(value.survives for value in values)
        safe_surviving = sum(value.invariant_safe and value.survives for value in values)
        output.append(
            {
                "profile_id": profile_id,
                key_name: label,
                "candidate_count": len(values),
                "invariant_safe_count": safe,
                "surviving_count": surviving,
                "invariant_safe_surviving_count": safe_surviving,
                "invariant_safe_survival_rate": _rate(safe_surviving, safe),
            }
        )
    return tuple(output)


def _family_release_assessments(
    family_rows: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    n4 = {
        value["family"]: value
        for value in family_rows
        if value["profile_id"] == N4_COPY_PASTE_WHITESPACE
    }
    output = []
    for family, value in sorted(n4.items()):
        safe = value["invariant_safe_count"]
        surviving = value["invariant_safe_surviving_count"]
        if safe == 0 or surviving == 0:
            status = "NORMALIZATION_FRAGILE_OR_UNOBSERVED"
        elif surviving == safe:
            status = "NORMALIZATION_DURABLE_FIDELITY_QUALIFICATION_REQUIRED"
        else:
            status = "MIXED_NORMALIZATION_SURVIVAL_FIDELITY_QUALIFICATION_REQUIRED"
        output.append(
            {
                "family": family,
                "n4_invariant_safe_count": safe,
                "n4_invariant_safe_surviving_count": surviving,
                "n4_survival_rate": _rate(surviving, safe),
                "release_assessment": status,
            }
        )
    return tuple(output)


def _exact_budget_counts(
    summaries: Sequence[NormalizationSampleSummary],
) -> Counter[tuple[str, int]]:
    counts: Counter[tuple[str, int]] = Counter()
    for summary in summaries:
        for profile in summary.profiles:
            for witness in profile.witnesses:
                if witness.reachable:
                    counts[(profile.profile_id, witness.budget)] += 1
    return counts


def _mandatory_conclusions(
    family_rows: Sequence[dict[str, object]],
    summaries: Sequence[NormalizationSampleSummary],
) -> dict[str, object]:
    profile_counts = _exact_budget_counts(summaries)
    n4_b2_count = profile_counts[(N4_COPY_PASTE_WHITESPACE, 2)]
    durable_fraction = n4_b2_count / len(summaries)
    scheduler_answer = (
        "ENOUGH_DURABLE_CHOICE_FOR_MATCHED_SCHEDULER_EXPERIMENT"
        if durable_fraction >= NORMALIZATION_DURABLE_CHOICE_MIN_FRACTION
        else "INSUFFICIENT_DURABLE_CHOICE_FOR_SCHEDULER_PREFERENCE"
    )
    by_profile_family = {
        (value["profile_id"], value["family"]): value for value in family_rows
    }

    def family_conclusion(value: dict[str, object] | None) -> dict[str, object]:
        safe = 0 if value is None else value["invariant_safe_count"]
        surviving = 0 if value is None else value["invariant_safe_surviving_count"]
        return {
            "invariant_safe_count": safe,
            "invariant_safe_surviving_count": surviving,
            "survival_rate": _rate(surviving, safe),
            "disappearance_rate": _rate(safe - surviving, safe),
        }

    return {
        "surface_v4_n1": family_conclusion(
            by_profile_family.get((N1_WHITESPACE_COLLAPSE, "orthography"))
        ),
        "surface_v4_n4": family_conclusion(
            by_profile_family.get((N4_COPY_PASTE_WHITESPACE, "orthography"))
        ),
        "durable_contractions_n1": family_conclusion(
            by_profile_family.get((N1_WHITESPACE_COLLAPSE, "contraction"))
        ),
        "durable_contractions_n4": family_conclusion(
            by_profile_family.get((N4_COPY_PASTE_WHITESPACE, "contraction"))
        ),
        "family_release_assessments": _family_release_assessments(family_rows),
        "durable_choice_minimum_budget": NORMALIZATION_DURABLE_CHOICE_MIN_BUDGET,
        "durable_choice_minimum_sample_fraction": NORMALIZATION_DURABLE_CHOICE_MIN_FRACTION,
        "n4_b2_reachable_sample_count": n4_b2_count,
        "n4_b2_reachable_sample_fraction": durable_fraction,
        "survival_aware_scheduler_answer": scheduler_answer,
    }


def build_normalization_survival_benchmark(
    corpus: DiverseBeamFrozenCorpus,
    registry: TransformRegistry,
    *,
    benchmark_source_code_commit: str,
    source_workflow_run_id: int,
) -> dict[str, object]:
    if not isinstance(corpus, DiverseBeamFrozenCorpus):
        raise TypeError("corpus must be a DiverseBeamFrozenCorpus")
    if not isinstance(registry, TransformRegistry):
        raise TypeError("registry must be a TransformRegistry")
    if _GIT_SHA_RE.fullmatch(benchmark_source_code_commit) is None:
        raise ValueError("benchmark_source_code_commit must be a lowercase Git SHA")
    require_int("source_workflow_run_id", source_workflow_run_id)
    if source_workflow_run_id <= 0:
        raise ValueError("source_workflow_run_id must be positive")
    summaries = []
    candidate_rows = []
    for sample in corpus.samples:
        summary, rows = benchmark_normalization_source(
            sample_id=sample.sample_id,
            source_text=sample.text,
            registry=registry,
        )
        summaries.append(summary)
        candidate_rows.extend(rows)
    ordered_summaries = tuple(sorted(summaries, key=lambda value: value.sample_id))
    ordered_rows = tuple(
        sorted(
            candidate_rows,
            key=lambda value: (
                value.sample_id,
                value.candidate_id,
                value.profile_id,
            ),
        )
    )
    family_rows = _aggregate_rows(ordered_rows, "family")
    rule_rows = _aggregate_rows(ordered_rows, "rule_id")
    profile_counts = _exact_budget_counts(ordered_summaries)

    payload = {
        "algorithm_version": NORMALIZATION_SURVIVAL_BENCHMARK_VERSION,
        "benchmark_source_code_commit": benchmark_source_code_commit,
        "source_corpus_commit": corpus.source_code_commit,
        "source_corpus_hash": corpus.artifact_hash,
        "source_workflow_run_id": source_workflow_run_id,
        "source_sample_count": len(corpus.samples),
        "source_samples_per_target_length": corpus.samples_per_target_length,
        "ruleset_hash": registry.ruleset_hash,
        "normalization_profiles": tuple(value.as_dict() for value in normalization_profiles()),
        "budgets": NORMALIZATION_SURVIVAL_BUDGETS,
        "candidate_row_count": len(ordered_rows),
        "candidate_rows": tuple(value.as_dict() for value in ordered_rows),
        "sample_summaries": tuple(value.as_dict() for value in ordered_summaries),
        "family_summaries": family_rows,
        "rule_summaries": rule_rows,
        "exact_budget_reachable_sample_counts": tuple(
            {
                "profile_id": profile.profile_id,
                "budget": budget,
                "reachable_sample_count": profile_counts[(profile.profile_id, budget)],
                "sample_count": len(ordered_summaries),
            }
            for profile in normalization_profiles()
            for budget in NORMALIZATION_SURVIVAL_BUDGETS
        ),
        "mandatory_conclusions": _mandatory_conclusions(
            family_rows, ordered_summaries
        ),
        "detector_access_observed": False,
        "secret_access_observed": False,
        "scientific_scope": (
            "Detector-blind normalization-survival opportunity benchmark; "
            "no release authorization"
        ),
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _schema_object(
    value: object,
    *,
    name: str,
    expected_keys: set[str],
    algorithm_version: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object")
    if set(value) != expected_keys:
        raise ValueError(f"{name} keys do not match the frozen schema")
    if value["algorithm_version"] != algorithm_version:
        raise ValueError(f"unsupported {name} version")
    return value


def _parse_candidate_row(value: object) -> NormalizationCandidateRow:
    expected = set(NormalizationCandidateRow.__dataclass_fields__) | {
        "algorithm_version"
    }
    row = _schema_object(
        value,
        name="normalization candidate row",
        expected_keys=expected,
        algorithm_version=NORMALIZATION_CANDIDATE_ROW_VERSION,
    )
    fields = {key: item for key, item in row.items() if key != "algorithm_version"}
    return NormalizationCandidateRow(**fields)


def _parse_budget_witness(value: object) -> NormalizationBudgetWitness:
    expected = set(NormalizationBudgetWitness.__dataclass_fields__) | {
        "algorithm_version"
    }
    row = _schema_object(
        value,
        name="normalization budget witness",
        expected_keys=expected,
        algorithm_version=NORMALIZATION_BUDGET_WITNESS_VERSION,
    )
    candidate_ids = row["candidate_ids"]
    if not isinstance(candidate_ids, list):
        raise TypeError("normalization witness candidate_ids must be a list")
    return NormalizationBudgetWitness(
        budget=row["budget"],
        reachable=row["reachable"],
        candidate_ids=tuple(candidate_ids),
        normalized_output_hash=row["normalized_output_hash"],
        witness_hash=row["witness_hash"],
    )


def _parse_sample_profile(value: object) -> NormalizationSampleProfile:
    expected = set(NormalizationSampleProfile.__dataclass_fields__) | {
        "algorithm_version"
    }
    row = _schema_object(
        value,
        name="normalization sample profile",
        expected_keys=expected,
        algorithm_version=NORMALIZATION_SAMPLE_PROFILE_VERSION,
    )
    witnesses = row["witnesses"]
    if not isinstance(witnesses, list):
        raise TypeError("normalization profile witnesses must be a list")
    return NormalizationSampleProfile(
        profile_id=row["profile_id"],
        profile_hash=row["profile_hash"],
        invariant_safe_surviving_count=row["invariant_safe_surviving_count"],
        independent_invariant_safe_surviving_count=row[
            "independent_invariant_safe_surviving_count"
        ],
        verified_compatible_prefix_count=row["verified_compatible_prefix_count"],
        witness_search_rejection_count=row["witness_search_rejection_count"],
        witnesses=tuple(_parse_budget_witness(item) for item in witnesses),
        summary_hash=row["summary_hash"],
    )


def _parse_sample_summary(value: object) -> NormalizationSampleSummary:
    expected = set(NormalizationSampleSummary.__dataclass_fields__) | {
        "algorithm_version"
    }
    row = _schema_object(
        value,
        name="normalization sample summary",
        expected_keys=expected,
        algorithm_version=NORMALIZATION_SAMPLE_SUMMARY_VERSION,
    )
    profiles = row["profiles"]
    if not isinstance(profiles, list):
        raise TypeError("normalization summary profiles must be a list")
    return NormalizationSampleSummary(
        sample_id=row["sample_id"],
        source_text_hash=row["source_text_hash"],
        enumeration_hash=row["enumeration_hash"],
        raw_candidate_count=row["raw_candidate_count"],
        independent_candidate_count=row["independent_candidate_count"],
        enumeration_rejection_count=row["enumeration_rejection_count"],
        invariant_safe_count=row["invariant_safe_count"],
        independent_invariant_safe_count=row["independent_invariant_safe_count"],
        invariant_rejection_count=row["invariant_rejection_count"],
        profiles=tuple(_parse_sample_profile(item) for item in profiles),
        summary_hash=row["summary_hash"],
    )


def _maximum_interval_row_count(
    rows: Sequence[NormalizationCandidateRow],
) -> int:
    ordered = sorted(rows, key=lambda item: (item.end, item.start, item.candidate_id))
    count = 0
    cursor = -1
    for row in ordered:
        if row.start < cursor:
            continue
        count += 1
        cursor = row.end
    return count


def _validate_loaded_rows(
    candidate_rows: Sequence[NormalizationCandidateRow],
    summaries: Sequence[NormalizationSampleSummary],
) -> None:
    if tuple(candidate_rows) != tuple(
        sorted(
            candidate_rows,
            key=lambda value: (
                value.sample_id,
                value.candidate_id,
                value.profile_id,
            ),
        )
    ):
        raise ValueError("normalization candidate rows are not canonically ordered")
    if tuple(summaries) != tuple(sorted(summaries, key=lambda value: value.sample_id)):
        raise ValueError("normalization sample summaries are not canonically ordered")
    summary_by_id = {value.sample_id: value for value in summaries}
    if len(summary_by_id) != len(summaries):
        raise ValueError("normalization sample IDs must be unique")
    rows_by_sample: dict[str, list[NormalizationCandidateRow]] = defaultdict(list)
    for row in candidate_rows:
        summary = summary_by_id.get(row.sample_id)
        if summary is None:
            raise ValueError("normalization candidate row references an unknown sample")
        if row.source_text_hash != summary.source_text_hash:
            raise ValueError("normalization candidate row source hash drifted")
        rows_by_sample[row.sample_id].append(row)
    expected_profile_ids = tuple(value.profile_id for value in normalization_profiles())
    for summary in summaries:
        sample_rows = rows_by_sample[summary.sample_id]
        if len(sample_rows) != summary.raw_candidate_count * len(expected_profile_ids):
            raise ValueError("normalization sample candidate row accounting drifted")
        grouped: dict[str, list[NormalizationCandidateRow]] = defaultdict(list)
        for row in sample_rows:
            grouped[row.candidate_id].append(row)
        if len(grouped) != summary.raw_candidate_count:
            raise ValueError("normalization sample candidate identity accounting drifted")
        for values in grouped.values():
            if tuple(sorted(value.profile_id for value in values)) != expected_profile_ids:
                raise ValueError("normalization candidate profile coverage drifted")
            invariant_fields = {
                (
                    value.rule_id,
                    value.rule_hash,
                    value.family,
                    value.tier,
                    value.start,
                    value.end,
                    value.transformed_text_hash,
                    value.invariant_safe,
                    value.invariant_report_hash,
                )
                for value in values
            }
            if len(invariant_fields) != 1:
                raise ValueError("normalization candidate attribution drifted across profiles")
        n0_rows = [value for value in sample_rows if value.profile_id == N0_IDENTITY]
        safe_n0_rows = [value for value in n0_rows if value.invariant_safe]
        if sum(value.invariant_safe for value in n0_rows) != summary.invariant_safe_count:
            raise ValueError("normalization invariant-safe candidate accounting drifted")
        if _maximum_interval_row_count(n0_rows) != summary.independent_candidate_count:
            raise ValueError("normalization independent candidate accounting drifted")
        if (
            _maximum_interval_row_count(safe_n0_rows)
            != summary.independent_invariant_safe_count
        ):
            raise ValueError("normalization independent invariant-safe accounting drifted")
        for profile_summary in summary.profiles:
            profile_rows = [
                value for value in sample_rows if value.profile_id == profile_summary.profile_id
            ]
            surviving = [
                value for value in profile_rows if value.invariant_safe and value.survives
            ]
            if len(surviving) != profile_summary.invariant_safe_surviving_count:
                raise ValueError("normalization profile survivor accounting drifted")
            if (
                _maximum_interval_row_count(surviving)
                != profile_summary.independent_invariant_safe_surviving_count
            ):
                raise ValueError("normalization independent survivor accounting drifted")
            by_id = {value.candidate_id: value for value in surviving}
            for witness in profile_summary.witnesses:
                if any(candidate_id not in by_id for candidate_id in witness.candidate_ids):
                    raise ValueError("normalization witness references a non-surviving candidate")
                selected = [by_id[candidate_id] for candidate_id in witness.candidate_ids]
                if _maximum_interval_row_count(selected) != len(selected):
                    raise ValueError("normalization witness candidates overlap")


def load_normalization_survival_benchmark(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs)
    if not isinstance(value, dict):
        raise TypeError("normalization benchmark must be a JSON object")
    expected = {
        "algorithm_version",
        "benchmark_source_code_commit",
        "source_corpus_commit",
        "source_corpus_hash",
        "source_workflow_run_id",
        "source_sample_count",
        "source_samples_per_target_length",
        "ruleset_hash",
        "normalization_profiles",
        "budgets",
        "candidate_row_count",
        "candidate_rows",
        "sample_summaries",
        "family_summaries",
        "rule_summaries",
        "exact_budget_reachable_sample_counts",
        "mandatory_conclusions",
        "detector_access_observed",
        "secret_access_observed",
        "scientific_scope",
        "artifact_hash",
    }
    if set(value) != expected:
        raise ValueError("normalization benchmark keys do not match the frozen schema")
    if value["algorithm_version"] != NORMALIZATION_SURVIVAL_BENCHMARK_VERSION:
        raise ValueError("unsupported normalization benchmark version")
    for name in ("benchmark_source_code_commit", "source_corpus_commit"):
        if not isinstance(value[name], str) or _GIT_SHA_RE.fullmatch(value[name]) is None:
            raise ValueError(f"{name} must be a lowercase Git SHA")
    for name in ("source_corpus_hash", "ruleset_hash", "artifact_hash"):
        require_sha256(name, value[name])
    require_int("source_sample_count", value["source_sample_count"])
    require_int("source_workflow_run_id", value["source_workflow_run_id"])
    require_int(
        "source_samples_per_target_length", value["source_samples_per_target_length"]
    )
    require_int("candidate_row_count", value["candidate_row_count"])
    if (
        value["source_sample_count"] <= 0
        or value["source_workflow_run_id"] <= 0
        or value["candidate_row_count"] < 0
    ):
        raise ValueError("normalization benchmark counts are invalid")
    if value["budgets"] != list(NORMALIZATION_SURVIVAL_BUDGETS):
        raise ValueError("normalization benchmark budgets drifted")
    expected_profiles = [profile.as_dict() for profile in normalization_profiles()]
    if value["normalization_profiles"] != expected_profiles:
        raise ValueError("normalization benchmark profiles drifted")
    for name in (
        "candidate_rows",
        "sample_summaries",
        "family_summaries",
        "rule_summaries",
        "exact_budget_reachable_sample_counts",
    ):
        if not isinstance(value[name], list):
            raise TypeError(f"{name} must be a list")
    if len(value["candidate_rows"]) != value["candidate_row_count"]:
        raise ValueError("normalization candidate row count mismatch")
    if len(value["sample_summaries"]) != value["source_sample_count"]:
        raise ValueError("normalization sample summary count mismatch")
    if len(value["exact_budget_reachable_sample_counts"]) != (
        len(normalization_profiles()) * len(NORMALIZATION_SURVIVAL_BUDGETS)
    ):
        raise ValueError("normalization exact-budget cells are incomplete")
    candidate_rows = tuple(_parse_candidate_row(item) for item in value["candidate_rows"])
    summaries = tuple(_parse_sample_summary(item) for item in value["sample_summaries"])
    _validate_loaded_rows(candidate_rows, summaries)
    expected_family_summaries = list(_aggregate_rows(candidate_rows, "family"))
    expected_rule_summaries = list(_aggregate_rows(candidate_rows, "rule_id"))
    if value["family_summaries"] != expected_family_summaries:
        raise ValueError("normalization family summaries do not replay")
    if value["rule_summaries"] != expected_rule_summaries:
        raise ValueError("normalization rule summaries do not replay")
    profile_counts = _exact_budget_counts(summaries)
    expected_budget_counts = [
        {
            "profile_id": profile.profile_id,
            "budget": budget,
            "reachable_sample_count": profile_counts[(profile.profile_id, budget)],
            "sample_count": len(summaries),
        }
        for profile in normalization_profiles()
        for budget in NORMALIZATION_SURVIVAL_BUDGETS
    ]
    if value["exact_budget_reachable_sample_counts"] != expected_budget_counts:
        raise ValueError("normalization exact-budget counts do not replay")
    if sha256_json(value["mandatory_conclusions"]) != sha256_json(
        _mandatory_conclusions(expected_family_summaries, summaries)
    ):
        raise ValueError("normalization mandatory conclusions do not replay")
    for name in ("detector_access_observed", "secret_access_observed"):
        require_bool(name, value[name])
        if value[name]:
            raise ValueError("normalization benchmark observed prohibited access")
    if (
        value["scientific_scope"]
        != "Detector-blind normalization-survival opportunity benchmark; no release authorization"
    ):
        raise ValueError("normalization benchmark scientific scope drifted")
    payload = {key: item for key, item in value.items() if key != "artifact_hash"}
    if value["artifact_hash"] != sha256_json(payload):
        raise ValueError("normalization benchmark artifact hash mismatch")
    return value
