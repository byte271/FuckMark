from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from .schema import InvariantStatus, ProtectedSpanKind


PROTECTED_INVARIANT_ALGORITHM_VERSION = "protected-invariant-validator-v2"


@dataclass(frozen=True, slots=True)
class UserProtectedRange:
    start: int
    end: int
    label: str
    range_hash: str

    def __post_init__(self) -> None:
        require_int("start", self.start)
        require_int("end", self.end)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("user protected range must satisfy 0 <= start < end")
        require_clean_string("label", self.label)
        require_sha256("range_hash", self.range_hash)
        if self.range_hash != sha256_json({"start": self.start, "end": self.end, "label": self.label}):
            raise ValueError("range_hash does not match user protected range")

    @classmethod
    def create(cls, start: int, end: int, label: str) -> UserProtectedRange:
        return cls(start, end, label, sha256_json({"start": start, "end": end, "label": label}))


@dataclass(frozen=True, slots=True)
class ProtectedSpan:
    start: int
    end: int
    kinds: tuple[ProtectedSpanKind, ...]
    exact_text: str
    text_hash: str
    span_hash: str

    def __post_init__(self) -> None:
        require_int("start", self.start)
        require_int("end", self.end)
        if self.start < 0 or self.end <= self.start:
            raise ValueError("protected span must satisfy 0 <= start < end")
        if not isinstance(self.exact_text, str) or not self.exact_text:
            raise ValueError("exact_text must be a non-empty string")
        if self.end - self.start != len(self.exact_text):
            raise ValueError("protected span geometry does not match exact_text")
        kinds = tuple(self.kinds)
        if not kinds or any(not isinstance(kind, ProtectedSpanKind) for kind in kinds):
            raise TypeError("kinds must contain ProtectedSpanKind values")
        normalized_kinds = tuple(sorted(set(kinds), key=lambda kind: kind.value))
        if kinds != normalized_kinds:
            raise ValueError("kinds must be unique and sorted by value")
        object.__setattr__(self, "kinds", kinds)
        require_sha256("text_hash", self.text_hash)
        require_sha256("span_hash", self.span_hash)
        if self.text_hash != sha256_text(self.exact_text):
            raise ValueError("text_hash does not match exact_text")
        if self.span_hash != sha256_json(self._payload()):
            raise ValueError("span_hash does not match protected span")

    def _payload(self) -> dict[str, object]:
        return {
            "start": self.start,
            "end": self.end,
            "kinds": tuple(kind.value for kind in self.kinds),
            "exact_text": self.exact_text,
            "text_hash": self.text_hash,
        }


@dataclass(frozen=True, slots=True)
class ProtectedSpanManifest:
    algorithm_version: str
    input_hash: str
    identifiers: tuple[str, ...]
    user_ranges: tuple[UserProtectedRange, ...]
    spans: tuple[ProtectedSpan, ...]
    manifest_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        require_sha256("input_hash", self.input_hash)
        identifiers = tuple(self.identifiers)
        if any(not isinstance(value, str) or not value for value in identifiers):
            raise ValueError("identifiers must contain non-empty strings")
        if identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("identifiers must be unique and sorted")
        ranges = tuple(self.user_ranges)
        if any(not isinstance(value, UserProtectedRange) for value in ranges):
            raise TypeError("user_ranges must contain UserProtectedRange values")
        if ranges != tuple(sorted(ranges, key=lambda value: (value.start, value.end, value.label, value.range_hash))):
            raise ValueError("user_ranges must be canonically ordered")
        if len({(value.start, value.end) for value in ranges}) != len(ranges):
            raise ValueError("user_ranges must not duplicate protected geometry")
        spans = tuple(self.spans)
        if any(not isinstance(value, ProtectedSpan) for value in spans):
            raise TypeError("spans must contain ProtectedSpan values")
        if spans != tuple(sorted(spans, key=lambda value: (value.start, value.end, value.span_hash))):
            raise ValueError("spans must be canonically ordered")
        for left, right in zip(spans, spans[1:]):
            if left.end > right.start:
                raise ValueError("protected spans must not overlap after merging")
        object.__setattr__(self, "identifiers", identifiers)
        object.__setattr__(self, "user_ranges", ranges)
        object.__setattr__(self, "spans", spans)
        require_sha256("manifest_hash", self.manifest_hash)
        if self.manifest_hash != sha256_json(self._payload()):
            raise ValueError("manifest_hash does not match protected span manifest")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "input_hash": self.input_hash,
            "identifiers": self.identifiers,
            "user_ranges": self.user_ranges,
            "spans": self.spans,
        }


@dataclass(frozen=True, slots=True)
class InvariantDifference:
    kind: ProtectedSpanKind
    exact_text: str
    original_count: int
    transformed_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ProtectedSpanKind):
            raise TypeError("kind must be a ProtectedSpanKind")
        if not isinstance(self.exact_text, str) or not self.exact_text:
            raise ValueError("exact_text must be non-empty")
        require_int("original_count", self.original_count)
        require_int("transformed_count", self.transformed_count)
        if self.original_count < 0 or self.transformed_count < 0 or self.original_count == self.transformed_count:
            raise ValueError("invariant difference counts must be non-negative and unequal")


@dataclass(frozen=True, slots=True)
class ProtectedInvariantReport:
    status: InvariantStatus
    original_hash: str
    transformed_hash: str
    differences: tuple[InvariantDifference, ...]
    report_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, InvariantStatus):
            raise TypeError("status must be an InvariantStatus")
        require_sha256("original_hash", self.original_hash)
        require_sha256("transformed_hash", self.transformed_hash)
        differences = tuple(self.differences)
        if any(not isinstance(value, InvariantDifference) for value in differences):
            raise TypeError("differences must contain InvariantDifference values")
        object.__setattr__(self, "differences", differences)
        if differences != tuple(sorted(differences, key=lambda value: (value.kind.value, value.exact_text))):
            raise ValueError("differences must be canonically ordered")
        keys = tuple((value.kind, value.exact_text) for value in differences)
        if len(set(keys)) != len(keys):
            raise ValueError("differences must not duplicate protected keys")
        if self.original_hash == self.transformed_hash and differences:
            raise ValueError("identical text hashes cannot contain invariant differences")
        expected_status = InvariantStatus.PASS if not differences else InvariantStatus.FAIL
        if self.status is not expected_status:
            raise ValueError("status does not match invariant differences")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match invariant report")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": PROTECTED_INVARIANT_ALGORITHM_VERSION,
            "status": self.status.value,
            "original_hash": self.original_hash,
            "transformed_hash": self.transformed_hash,
            "differences": self.differences,
        }
