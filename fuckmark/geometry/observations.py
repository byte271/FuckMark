from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .._validation import normalize_token_sequence, require_clean_string, require_int, require_sha256
from ..alignment import AlignmentResult
from ..hashing import sha256_json, sha256_text


OBSERVATION_ALGORITHM_VERSION = "occurrence-aware-root-observations-v1"
SURVIVAL_ALGORITHM_VERSION = "observation-survival-v1"


class TokenTrack(str, Enum):
    DECODED_TEXT = "decoded_text"


class PromptBoundaryMode(str, Enum):
    GENERATED_ONLY = "generated_only"


class SurvivalReportStatus(str, Enum):
    OK = "OK"
    NO_ELIGIBLE_OBSERVATIONS = "NO_ELIGIBLE_OBSERVATIONS"


class ObservationDisposition(str, Enum):
    ROOT_INELIGIBLE = "ROOT_INELIGIBLE"
    SURVIVED = "SURVIVED"
    UNMAPPED = "UNMAPPED"
    AMBIGUOUS = "AMBIGUOUS"
    NONCONTIGUOUS_OR_CHANGED = "NONCONTIGUOUS_OR_CHANGED"
    NEWLY_MASKED = "NEWLY_MASKED"


@dataclass(frozen=True, slots=True)
class GeometryConfig:
    algorithm_version: str
    tokenizer_identity_hash: str
    ngram_len: int
    token_track: TokenTrack
    prompt_boundary_mode: PromptBoundaryMode
    repetition_mask_policy_id: str
    config_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        require_sha256("tokenizer_identity_hash", self.tokenizer_identity_hash)
        require_int("ngram_len", self.ngram_len)
        if self.ngram_len <= 0:
            raise ValueError("ngram_len must be positive")
        if not isinstance(self.token_track, TokenTrack):
            raise TypeError("token_track must be a TokenTrack")
        if not isinstance(self.prompt_boundary_mode, PromptBoundaryMode):
            raise TypeError("prompt_boundary_mode must be a PromptBoundaryMode")
        require_clean_string("repetition_mask_policy_id", self.repetition_mask_policy_id)
        require_sha256("config_hash", self.config_hash)
        if self.config_hash != sha256_json(self.payload()):
            raise ValueError("config_hash does not match GeometryConfig payload")

    @classmethod
    def create(
        cls,
        *,
        tokenizer_identity_hash: str,
        ngram_len: int,
        repetition_mask_policy_id: str,
        token_track: TokenTrack = TokenTrack.DECODED_TEXT,
        prompt_boundary_mode: PromptBoundaryMode = PromptBoundaryMode.GENERATED_ONLY,
        algorithm_version: str = "counterfactual-geometry-v1",
    ) -> GeometryConfig:
        payload = {
            "algorithm_version": algorithm_version,
            "tokenizer_identity_hash": tokenizer_identity_hash,
            "ngram_len": ngram_len,
            "token_track": token_track.value if isinstance(token_track, TokenTrack) else token_track,
            "prompt_boundary_mode": (
                prompt_boundary_mode.value
                if isinstance(prompt_boundary_mode, PromptBoundaryMode)
                else prompt_boundary_mode
            ),
            "repetition_mask_policy_id": repetition_mask_policy_id,
        }
        return cls(
            algorithm_version=algorithm_version,
            tokenizer_identity_hash=tokenizer_identity_hash,
            ngram_len=ngram_len,
            token_track=token_track,
            prompt_boundary_mode=prompt_boundary_mode,
            repetition_mask_policy_id=repetition_mask_policy_id,
            config_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "tokenizer_identity_hash": self.tokenizer_identity_hash,
            "ngram_len": self.ngram_len,
            "token_track": self.token_track.value,
            "prompt_boundary_mode": self.prompt_boundary_mode.value,
            "repetition_mask_policy_id": self.repetition_mask_policy_id,
        }


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    source_sample_id: str
    observation_index: int
    token_start: int
    token_end_exclusive: int
    token_ids: tuple[int, ...]
    eligible: bool
    token_track: TokenTrack
    prompt_boundary_mode: PromptBoundaryMode
    occurrence_hash: str

    def __post_init__(self) -> None:
        require_clean_string("source_sample_id", self.source_sample_id)
        require_int("observation_index", self.observation_index)
        require_int("token_start", self.token_start)
        require_int("token_end_exclusive", self.token_end_exclusive)
        if self.observation_index < 0 or self.token_start < 0:
            raise ValueError("observation indices must be non-negative")
        if self.token_end_exclusive <= self.token_start:
            raise ValueError("token interval must be non-empty")
        normalized = normalize_token_sequence("token_ids", self.token_ids)
        if normalized != self.token_ids:
            raise ValueError("token_ids must already be a tuple")
        if len(self.token_ids) != self.token_end_exclusive - self.token_start:
            raise ValueError("token_ids length does not match token interval")
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be a boolean")
        if not isinstance(self.token_track, TokenTrack):
            raise TypeError("token_track must be a TokenTrack")
        if not isinstance(self.prompt_boundary_mode, PromptBoundaryMode):
            raise TypeError("prompt_boundary_mode must be a PromptBoundaryMode")
        require_sha256("occurrence_hash", self.occurrence_hash)
        if self.occurrence_hash != sha256_json(self.payload()):
            raise ValueError("occurrence_hash does not match ObservationRecord payload")

    @classmethod
    def create(
        cls,
        *,
        source_sample_id: str,
        observation_index: int,
        token_start: int,
        token_ids: Sequence[int],
        eligible: bool,
        token_track: TokenTrack,
        prompt_boundary_mode: PromptBoundaryMode,
    ) -> ObservationRecord:
        tokens = normalize_token_sequence("token_ids", token_ids)
        payload = {
            "source_sample_id": source_sample_id,
            "observation_index": observation_index,
            "token_start": token_start,
            "token_end_exclusive": token_start + len(tokens),
            "token_ids": tokens,
            "eligible": eligible,
            "token_track": token_track.value if isinstance(token_track, TokenTrack) else token_track,
            "prompt_boundary_mode": (
                prompt_boundary_mode.value
                if isinstance(prompt_boundary_mode, PromptBoundaryMode)
                else prompt_boundary_mode
            ),
        }
        return cls(
            source_sample_id=source_sample_id,
            observation_index=observation_index,
            token_start=token_start,
            token_end_exclusive=token_start + len(tokens),
            token_ids=tokens,
            eligible=eligible,
            token_track=token_track,
            prompt_boundary_mode=prompt_boundary_mode,
            occurrence_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "source_sample_id": self.source_sample_id,
            "observation_index": self.observation_index,
            "token_start": self.token_start,
            "token_end_exclusive": self.token_end_exclusive,
            "token_ids": self.token_ids,
            "eligible": self.eligible,
            "token_track": self.token_track.value,
            "prompt_boundary_mode": self.prompt_boundary_mode.value,
        }


@dataclass(frozen=True, slots=True)
class RootObservationSet:
    algorithm_version: str
    source_sample_id: str
    source_text_hash: str
    root_token_hash: str
    token_count: int
    ngram_len: int
    geometry_config_hash: str
    observations: tuple[ObservationRecord, ...]
    root_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        require_clean_string("source_sample_id", self.source_sample_id)
        require_sha256("source_text_hash", self.source_text_hash)
        require_sha256("root_token_hash", self.root_token_hash)
        require_int("token_count", self.token_count)
        if self.token_count < 0:
            raise ValueError("token_count must be non-negative")
        require_int("ngram_len", self.ngram_len)
        if self.ngram_len <= 0:
            raise ValueError("ngram_len must be positive")
        require_sha256("geometry_config_hash", self.geometry_config_hash)
        if not isinstance(self.observations, tuple) or any(
            not isinstance(item, ObservationRecord) for item in self.observations
        ):
            raise TypeError("observations must be a tuple of ObservationRecord values")
        require_sha256("root_hash", self.root_hash)
        if self.root_hash != sha256_json(self.payload()):
            raise ValueError("root_hash does not match RootObservationSet payload")

    @property
    def eligible_count(self) -> int:
        return sum(item.eligible for item in self.observations)

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "source_sample_id": self.source_sample_id,
            "source_text_hash": self.source_text_hash,
            "root_token_hash": self.root_token_hash,
            "token_count": self.token_count,
            "ngram_len": self.ngram_len,
            "geometry_config_hash": self.geometry_config_hash,
            "observation_occurrence_hashes": tuple(item.occurrence_hash for item in self.observations),
        }


@dataclass(frozen=True, slots=True)
class ObservationSurvivalReport:
    algorithm_version: str
    status: SurvivalReportStatus
    root_observation_count: int
    root_eligible_count: int
    surviving_count: int
    destroyed_count: int
    newly_masked_count: int
    unmapped_count: int
    ambiguous_count: int
    survival_ratio: float
    destruction_ratio: float
    survival_bitmap_hash: str
    report_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if not isinstance(self.status, SurvivalReportStatus):
            raise TypeError("status must be a SurvivalReportStatus")
        for name in (
            "root_observation_count",
            "root_eligible_count",
            "surviving_count",
            "destroyed_count",
            "newly_masked_count",
            "unmapped_count",
            "ambiguous_count",
        ):
            value = getattr(self, name)
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.root_eligible_count > self.root_observation_count:
            raise ValueError("root_eligible_count cannot exceed root_observation_count")
        if self.surviving_count + self.destroyed_count != self.root_eligible_count:
            raise ValueError("survival counts must partition root eligible observations")
        for name in ("newly_masked_count", "unmapped_count", "ambiguous_count"):
            if getattr(self, name) > self.destroyed_count:
                raise ValueError(f"{name} cannot exceed destroyed_count")
        for name in ("survival_ratio", "destruction_ratio"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a real number")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if abs((self.survival_ratio + self.destruction_ratio) - 1.0) > 1e-12:
            raise ValueError("survival and destruction ratios must sum to one")
        if self.root_eligible_count == 0:
            if self.status is not SurvivalReportStatus.NO_ELIGIBLE_OBSERVATIONS:
                raise ValueError("zero eligible observations require explicit status")
            if self.survival_ratio != 1.0 or self.destruction_ratio != 0.0:
                raise ValueError("zero eligible observations use neutral 1.0/0.0 ratios")
        elif self.status is not SurvivalReportStatus.OK:
            raise ValueError("non-empty eligible observations require OK status")
        require_sha256("survival_bitmap_hash", self.survival_bitmap_hash)
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self.payload()):
            raise ValueError("report_hash does not match ObservationSurvivalReport payload")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "status": self.status.value,
            "root_observation_count": self.root_observation_count,
            "root_eligible_count": self.root_eligible_count,
            "surviving_count": self.surviving_count,
            "destroyed_count": self.destroyed_count,
            "newly_masked_count": self.newly_masked_count,
            "unmapped_count": self.unmapped_count,
            "ambiguous_count": self.ambiguous_count,
            "survival_ratio": self.survival_ratio,
            "destruction_ratio": self.destruction_ratio,
            "survival_bitmap_hash": self.survival_bitmap_hash,
        }


def window_count(token_count: int, ngram_len: int) -> int:
    require_int("token_count", token_count)
    require_int("ngram_len", ngram_len)
    if token_count < 0:
        raise ValueError("token_count must be non-negative")
    if ngram_len <= 0:
        raise ValueError("ngram_len must be positive")
    return max(0, token_count - ngram_len + 1)


def normalize_window_eligibility(
    token_count: int,
    ngram_len: int,
    values: Sequence[bool] | None,
) -> tuple[bool, ...]:
    count = window_count(token_count, ngram_len)
    if values is None:
        return (True,) * count
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("window eligibility must be a sequence of booleans")
    output = tuple(values)
    if len(output) != count:
        raise ValueError("window eligibility length does not match token geometry")
    if any(not isinstance(value, bool) for value in output):
        raise TypeError("window eligibility must contain only booleans")
    return output


def build_root_observations(
    *,
    source_sample_id: str,
    source_text: str,
    root_tokens: Sequence[int],
    config: GeometryConfig,
    eligible_windows: Sequence[bool] | None = None,
) -> RootObservationSet:
    require_clean_string("source_sample_id", source_sample_id)
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    if not isinstance(config, GeometryConfig):
        raise TypeError("config must be a GeometryConfig")
    tokens = normalize_token_sequence("root_tokens", root_tokens)
    eligibility = normalize_window_eligibility(len(tokens), config.ngram_len, eligible_windows)
    observations = tuple(
        ObservationRecord.create(
            source_sample_id=source_sample_id,
            observation_index=index,
            token_start=index,
            token_ids=tokens[index : index + config.ngram_len],
            eligible=eligibility[index],
            token_track=config.token_track,
            prompt_boundary_mode=config.prompt_boundary_mode,
        )
        for index in range(len(eligibility))
    )
    payload = {
        "algorithm_version": OBSERVATION_ALGORITHM_VERSION,
        "source_sample_id": source_sample_id,
        "source_text_hash": sha256_text(source_text),
        "root_token_hash": sha256_json(tokens),
        "token_count": len(tokens),
        "ngram_len": config.ngram_len,
        "geometry_config_hash": config.config_hash,
        "observation_occurrence_hashes": tuple(item.occurrence_hash for item in observations),
    }
    return RootObservationSet(
        algorithm_version=OBSERVATION_ALGORITHM_VERSION,
        source_sample_id=source_sample_id,
        source_text_hash=payload["source_text_hash"],
        root_token_hash=payload["root_token_hash"],
        token_count=len(tokens),
        ngram_len=config.ngram_len,
        geometry_config_hash=config.config_hash,
        observations=observations,
        root_hash=sha256_json(payload),
    )


def compute_observation_survival(
    *,
    root: RootObservationSet,
    root_tokens: Sequence[int],
    transformed_tokens: Sequence[int],
    transformed_eligible_windows: Sequence[bool] | None,
    alignment: AlignmentResult,
    ambiguous_original_indices: frozenset[int] = frozenset(),
) -> ObservationSurvivalReport:
    if not isinstance(root, RootObservationSet):
        raise TypeError("root must be a RootObservationSet")
    original = normalize_token_sequence("root_tokens", root_tokens)
    transformed = normalize_token_sequence("transformed_tokens", transformed_tokens)
    if root.token_count != len(original) or root.root_token_hash != sha256_json(original):
        raise ValueError("root token sequence does not match RootObservationSet")
    if not isinstance(alignment, AlignmentResult):
        raise TypeError("alignment must be an AlignmentResult")
    if len(alignment.original_to_transformed) != len(original):
        raise ValueError("alignment original length does not match root token sequence")
    if len(alignment.transformed_to_original) != len(transformed):
        raise ValueError("alignment transformed length does not match transformed token sequence")
    if not isinstance(ambiguous_original_indices, frozenset):
        raise TypeError("ambiguous_original_indices must be a frozenset")
    for index in ambiguous_original_indices:
        require_int("ambiguous original index", index)
        if not 0 <= index < len(original):
            raise ValueError("ambiguous original index is out of bounds")
    if root.observations and any(len(item.token_ids) != root.ngram_len for item in root.observations):
        raise ValueError("root observations use inconsistent ngram lengths")
    output_eligibility = normalize_window_eligibility(
        len(transformed), root.ngram_len, transformed_eligible_windows
    )
    dispositions: list[ObservationDisposition] = []
    surviving = newly_masked = unmapped = ambiguous = 0
    for observation in root.observations:
        if not observation.eligible:
            dispositions.append(ObservationDisposition.ROOT_INELIGIBLE)
            continue
        mapped = tuple(
            alignment.original_to_transformed[index]
            for index in range(observation.token_start, observation.token_end_exclusive)
        )
        if any(position is None for position in mapped):
            unmapped += 1
            dispositions.append(ObservationDisposition.UNMAPPED)
            continue
        positions = tuple(int(position) for position in mapped if position is not None)
        expected = tuple(range(positions[0], positions[0] + len(positions)))
        if positions != expected:
            dispositions.append(ObservationDisposition.NONCONTIGUOUS_OR_CHANGED)
            continue
        if any(
            index in ambiguous_original_indices
            for index in range(observation.token_start, observation.token_end_exclusive)
        ):
            ambiguous += 1
            dispositions.append(ObservationDisposition.AMBIGUOUS)
            continue
        if positions[-1] >= len(transformed) or tuple(transformed[position] for position in positions) != observation.token_ids:
            dispositions.append(ObservationDisposition.NONCONTIGUOUS_OR_CHANGED)
            continue
        mapped_start = positions[0]
        if mapped_start >= len(output_eligibility) or not output_eligibility[mapped_start]:
            newly_masked += 1
            dispositions.append(ObservationDisposition.NEWLY_MASKED)
            continue
        surviving += 1
        dispositions.append(ObservationDisposition.SURVIVED)
    eligible = root.eligible_count
    destroyed = eligible - surviving
    if eligible == 0:
        status = SurvivalReportStatus.NO_ELIGIBLE_OBSERVATIONS
        survival_ratio = 1.0
        destruction_ratio = 0.0
    else:
        status = SurvivalReportStatus.OK
        survival_ratio = surviving / eligible
        destruction_ratio = destroyed / eligible
    bitmap_hash = sha256_json(tuple(item.value for item in dispositions))
    payload = {
        "algorithm_version": SURVIVAL_ALGORITHM_VERSION,
        "status": status.value,
        "root_observation_count": len(root.observations),
        "root_eligible_count": eligible,
        "surviving_count": surviving,
        "destroyed_count": destroyed,
        "newly_masked_count": newly_masked,
        "unmapped_count": unmapped,
        "ambiguous_count": ambiguous,
        "survival_ratio": survival_ratio,
        "destruction_ratio": destruction_ratio,
        "survival_bitmap_hash": bitmap_hash,
    }
    return ObservationSurvivalReport(
        algorithm_version=SURVIVAL_ALGORITHM_VERSION,
        status=status,
        root_observation_count=len(root.observations),
        root_eligible_count=eligible,
        surviving_count=surviving,
        destroyed_count=destroyed,
        newly_masked_count=newly_masked,
        unmapped_count=unmapped,
        ambiguous_count=ambiguous,
        survival_ratio=survival_ratio,
        destruction_ratio=destruction_ratio,
        survival_bitmap_hash=bitmap_hash,
        report_hash=sha256_json(payload),
    )
