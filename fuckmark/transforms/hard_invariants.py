from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from .._validation import require_sha256
from ..hashing import sha256_json, sha256_text
from .invariants import validate_protected_invariants
from .protected_artifacts import ProtectedInvariantReport, UserProtectedRange
from .schema import HardInvariantReason, InvariantStatus

HARD_INVARIANT_ALGORITHM_VERSION = "hard-invariant-validator-v4"
_WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
_CONTRACTED_NEGATIONS = {
    "don't": ("do:not", None), "doesn't": ("does:not", None), "didn't": ("did:not", None),
    "can't": ("can:not", "can"), "won't": ("will:not", "will"), "shouldn't": ("should:not", "should"),
    "wouldn't": ("would:not", "would"), "couldn't": ("could:not", "could"), "mustn't": ("must:not", "must"),
    "isn't": ("is:not", None), "aren't": ("are:not", None), "wasn't": ("was:not", None), "weren't": ("were:not", None),
    "haven't": ("have:not", None), "hasn't": ("has:not", None), "hadn't": ("had:not", None),
}
_EXPANDED_NEGATION_AUX = {"do": None, "does": None, "did": None, "can": "can", "will": "will", "should": "should", "would": "would", "could": "could", "must": "must", "is": None, "are": None, "was": None, "were": None, "have": None, "has": None, "had": None}
_UNAMBIGUOUS_CONTRACTED_COPULAS = {"you're": "are", "we're": "are", "they're": "are"}
_MODAL_WORDS = frozenset(("can", "will", "should", "would", "could", "must", "may", "might", "shall"))
_STANDALONE_NEGATIONS = frozenset(("never", "no", "neither", "nor", "none", "nothing", "nobody", "nowhere", "without"))
_OBLIGATION_WORDS = frozenset(("must", "required", "mandatory", "obliged", "obligated"))
_PERMISSION_WORDS = frozenset(("may", "allowed", "permitted"))

@dataclass(frozen=True, slots=True)
class HardInvariantSignature:
    negations: tuple[str, ...]
    modalities: tuple[str, ...]
    signature_hash: str

    def __post_init__(self) -> None:
        negations = tuple(self.negations)
        modalities = tuple(self.modalities)
        if any(not isinstance(value, str) or not value for value in negations):
            raise ValueError("negations must contain non-empty strings")
        if any(not isinstance(value, str) or not value for value in modalities):
            raise ValueError("modalities must contain non-empty strings")
        object.__setattr__(self, "negations", negations)
        object.__setattr__(self, "modalities", modalities)
        require_sha256("signature_hash", self.signature_hash)
        if self.signature_hash != sha256_json({"algorithm_version": HARD_INVARIANT_ALGORITHM_VERSION, "negations": negations, "modalities": modalities}):
            raise ValueError("signature_hash does not match hard invariant signature")

@dataclass(frozen=True, slots=True)
class HardInvariantReport:
    status: InvariantStatus
    original_hash: str
    transformed_hash: str
    protected_report: ProtectedInvariantReport
    original_signature: HardInvariantSignature
    transformed_signature: HardInvariantSignature
    reasons: tuple[HardInvariantReason, ...]
    report_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, InvariantStatus):
            raise TypeError("status must be an InvariantStatus")
        require_sha256("original_hash", self.original_hash)
        require_sha256("transformed_hash", self.transformed_hash)
        if not isinstance(self.protected_report, ProtectedInvariantReport):
            raise TypeError("protected_report must be a ProtectedInvariantReport")
        if not isinstance(self.original_signature, HardInvariantSignature) or not isinstance(self.transformed_signature, HardInvariantSignature):
            raise TypeError("hard invariant signatures have invalid types")
        reasons = tuple(self.reasons)
        if any(not isinstance(value, HardInvariantReason) for value in reasons):
            raise TypeError("reasons must contain HardInvariantReason values")
        if reasons != tuple(sorted(set(reasons), key=lambda value: value.value)):
            raise ValueError("reasons must be unique and sorted")
        object.__setattr__(self, "reasons", reasons)
        if self.protected_report.original_hash != self.original_hash or self.protected_report.transformed_hash != self.transformed_hash:
            raise ValueError("protected report hashes must match hard invariant report")
        expected = []
        if self.protected_report.status is InvariantStatus.FAIL:
            expected.append(HardInvariantReason.PROTECTED_CONTENT_CHANGED)
        if self.original_signature.negations != self.transformed_signature.negations:
            expected.append(HardInvariantReason.NEGATION_CHANGED)
        if self.original_signature.modalities != self.transformed_signature.modalities:
            expected.append(HardInvariantReason.MODALITY_CHANGED)
        expected_reasons = tuple(sorted(expected, key=lambda value: value.value))
        expected_status = InvariantStatus.PASS if not expected_reasons else InvariantStatus.FAIL
        if reasons != expected_reasons or self.status is not expected_status:
            raise ValueError("hard invariant status or reasons do not match component reports")
        require_sha256("report_hash", self.report_hash)
        if self.report_hash != sha256_json(self._payload()):
            raise ValueError("report_hash does not match hard invariant report")

    def _payload(self) -> dict[str, object]:
        return {"algorithm_version": HARD_INVARIANT_ALGORITHM_VERSION, "status": self.status.value, "original_hash": self.original_hash, "transformed_hash": self.transformed_hash, "protected_report": self.protected_report, "original_signature": self.original_signature, "transformed_signature": self.transformed_signature, "reasons": tuple(value.value for value in self.reasons)}


def _normalized_words(text: str) -> tuple[str, ...]:
    return tuple(match.group().replace("’", "'").lower() for match in _WORD_RE.finditer(text))


def hard_invariant_signature(text: str) -> HardInvariantSignature:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    words = _normalized_words(text)
    negations = []
    modalities = []
    index = 0
    while index < len(words):
        word = words[index]
        contracted = _CONTRACTED_NEGATIONS.get(word)
        if contracted is not None:
            negation, modality = contracted
            negations.append(negation)
            if modality is not None:
                modalities.append(modality)
            index += 1
            continue
        if word == "cannot":
            negations.append("can:not")
            modalities.append("can")
            index += 1
            continue
        contracted_copula = _UNAMBIGUOUS_CONTRACTED_COPULAS.get(word)
        if contracted_copula is not None and index + 1 < len(words) and words[index + 1] == "not":
            negations.append(f"{contracted_copula}:not")
            index += 2
            continue
        if word in _EXPANDED_NEGATION_AUX and index + 1 < len(words) and words[index + 1] == "not":
            negations.append(f"{word}:not")
            modality = _EXPANDED_NEGATION_AUX[word]
            if modality is not None:
                modalities.append(modality)
            index += 2
            continue
        if word == "not":
            negations.append("not")
        elif word in _STANDALONE_NEGATIONS:
            negations.append(word)
        if word in _MODAL_WORDS:
            modalities.append(word)
        if word in _OBLIGATION_WORDS:
            modalities.append(f"obligation:{word}")
        if word in _PERMISSION_WORDS:
            modalities.append(f"permission:{word}")
        if word == "have" and index + 1 < len(words) and words[index + 1] == "to":
            modalities.append("obligation:have_to")
        if word == "need" and index + 1 < len(words) and words[index + 1] == "to":
            modalities.append("obligation:need_to")
        index += 1
    negation_tuple = tuple(negations)
    modality_tuple = tuple(modalities)
    return HardInvariantSignature(negation_tuple, modality_tuple, sha256_json({"algorithm_version": HARD_INVARIANT_ALGORITHM_VERSION, "negations": negation_tuple, "modalities": modality_tuple}))


def validate_hard_invariants(original: str, transformed: str, identifiers: Sequence[str] = (), user_ranges: Sequence[UserProtectedRange] = ()) -> HardInvariantReport:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    protected_report = validate_protected_invariants(original, transformed, identifiers, user_ranges)
    original_signature = hard_invariant_signature(original)
    transformed_signature = hard_invariant_signature(transformed)
    reasons = []
    if protected_report.status is InvariantStatus.FAIL:
        reasons.append(HardInvariantReason.PROTECTED_CONTENT_CHANGED)
    if original_signature.negations != transformed_signature.negations:
        reasons.append(HardInvariantReason.NEGATION_CHANGED)
    if original_signature.modalities != transformed_signature.modalities:
        reasons.append(HardInvariantReason.MODALITY_CHANGED)
    normalized_reasons = tuple(sorted(reasons, key=lambda value: value.value))
    status = InvariantStatus.PASS if not normalized_reasons else InvariantStatus.FAIL
    original_hash = sha256_text(original)
    transformed_hash = sha256_text(transformed)
    payload = {"algorithm_version": HARD_INVARIANT_ALGORITHM_VERSION, "status": status.value, "original_hash": original_hash, "transformed_hash": transformed_hash, "protected_report": protected_report, "original_signature": original_signature, "transformed_signature": transformed_signature, "reasons": tuple(value.value for value in normalized_reasons)}
    return HardInvariantReport(status, original_hash, transformed_hash, protected_report, original_signature, transformed_signature, normalized_reasons, sha256_json(payload))
