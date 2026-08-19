from __future__ import annotations

import math
from dataclasses import dataclass

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from .mid_dev_quality import word_edit_rate
from .residual_signal_geometry import ResidualSignalGeometry


STRUCTURAL_LEVERAGE_ALGORITHM_VERSION = "residual-structural-leverage-v1"


def character_edit_distance(left: str, right: str) -> int:
    if not isinstance(left, str) or not isinstance(right, str):
        raise TypeError("character edit inputs must be strings")
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for index, left_value in enumerate(left, start=1):
        current = [index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def character_edit_rate(source: str, transformed: str) -> float:
    if not isinstance(source, str) or not isinstance(transformed, str):
        raise TypeError("character edit inputs must be strings")
    if not source:
        return 0.0 if not transformed else 1.0
    return min(1.0, character_edit_distance(source, transformed) / len(source))


def _leverage(reduction: float, cost: float) -> float | None:
    if cost <= 0.0:
        return None
    return reduction / cost


@dataclass(frozen=True, slots=True)
class StructuralLeverageSidecar:
    algorithm_version: str
    variant_hash: str
    geometry_hash: str
    operation_count: int
    visible_word_edit_rate: float
    visible_character_edit_rate: float
    token_edit_distance: int
    residual_inherited_fraction: float
    new_context_opportunity_fraction: float
    valid_denominator_ratio: float
    rif_reduction: float | None
    rif_reduction_per_operation: float | None
    rif_reduction_per_word_edit_rate: float | None
    rif_reduction_per_character_edit_rate: float | None
    rif_reduction_per_token_edit: float | None
    sidecar_hash: str

    def __post_init__(self) -> None:
        if self.algorithm_version != STRUCTURAL_LEVERAGE_ALGORITHM_VERSION:
            raise ValueError("unsupported structural leverage version")
        require_sha256("variant_hash", self.variant_hash)
        require_sha256("geometry_hash", self.geometry_hash)
        require_sha256("sidecar_hash", self.sidecar_hash)
        require_int("operation_count", self.operation_count)
        require_int("token_edit_distance", self.token_edit_distance)
        if self.operation_count < 0 or self.token_edit_distance < 0:
            raise ValueError("cost counts must be non-negative")
        for name in (
            "visible_word_edit_rate",
            "visible_character_edit_rate",
            "residual_inherited_fraction",
            "new_context_opportunity_fraction",
            "valid_denominator_ratio",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise TypeError(f"{name} must be finite")
            if name != "valid_denominator_ratio" and not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
            if name == "valid_denominator_ratio" and float(value) < 0.0:
                raise ValueError("valid_denominator_ratio must be non-negative")
        for name in (
            "rif_reduction",
            "rif_reduction_per_operation",
            "rif_reduction_per_word_edit_rate",
            "rif_reduction_per_character_edit_rate",
            "rif_reduction_per_token_edit",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
            ):
                raise TypeError(f"{name} must be finite or None")
        if self.sidecar_hash != sha256_json(self.payload()):
            raise ValueError("sidecar_hash does not match structural leverage sidecar")

    def payload(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "sidecar_hash"}


def build_structural_leverage_sidecar(
    *,
    variant_hash: str,
    source_text: str,
    transformed_text: str,
    geometry: ResidualSignalGeometry,
    operation_count: int,
) -> StructuralLeverageSidecar:
    require_sha256("variant_hash", variant_hash)
    if not isinstance(source_text, str) or not isinstance(transformed_text, str):
        raise TypeError("source and transformed text must be strings")
    if not isinstance(geometry, ResidualSignalGeometry):
        raise TypeError("geometry must be ResidualSignalGeometry")
    require_int("operation_count", operation_count)
    if operation_count < 0:
        raise ValueError("operation_count must be non-negative")
    word_rate = word_edit_rate(source_text, transformed_text)
    char_rate = character_edit_rate(source_text, transformed_text)
    token_distance = geometry.alignment_distance
    reduction = None
    if geometry.root_valid_observation_count > 0:
        reduction = 1.0 - geometry.residual_inherited_fraction
    payload = {
        "algorithm_version": STRUCTURAL_LEVERAGE_ALGORITHM_VERSION,
        "variant_hash": variant_hash,
        "geometry_hash": geometry.geometry_hash,
        "operation_count": operation_count,
        "visible_word_edit_rate": word_rate,
        "visible_character_edit_rate": char_rate,
        "token_edit_distance": token_distance,
        "residual_inherited_fraction": geometry.residual_inherited_fraction,
        "new_context_opportunity_fraction": geometry.new_context_opportunity_fraction,
        "valid_denominator_ratio": geometry.valid_denominator_ratio,
        "rif_reduction": reduction,
        "rif_reduction_per_operation": None if reduction is None else _leverage(reduction, float(operation_count)),
        "rif_reduction_per_word_edit_rate": None if reduction is None else _leverage(reduction, word_rate),
        "rif_reduction_per_character_edit_rate": None if reduction is None else _leverage(reduction, char_rate),
        "rif_reduction_per_token_edit": None if reduction is None else _leverage(reduction, float(token_distance)),
    }
    return StructuralLeverageSidecar(**payload, sidecar_hash=sha256_json(payload))
