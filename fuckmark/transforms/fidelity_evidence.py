from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json, sha256_text
from .lexical_audit import BLIND_HUMAN_REVIEW_POLICY_ID
from .schema import CandidateRejectionReason


FIDELITY_EVIDENCE_ALGORITHM_VERSION = "fidelity-evidence-v2"


class FidelityLabel(str, Enum):
    EQUIVALENT_OR_MINOR = "equivalent_or_minor"
    MATERIAL_CHANGE = "material_change"
    CANNOT_JUDGE = "cannot_judge"


class GrammarFixtureDisposition(str, Enum):
    CANDIDATE = "candidate"
    REJECTION = "rejection"


@dataclass(frozen=True, slots=True)
class FidelityReviewSample:
    rule_hash: str
    sample_id: str
    source_text: str
    transformed_text: str
    source_text_hash: str
    transformed_text_hash: str
    sample_hash: str

    def __post_init__(self) -> None:
        require_sha256("rule_hash", self.rule_hash)
        require_clean_string("sample_id", self.sample_id)
        if not isinstance(self.source_text, str) or not self.source_text:
            raise ValueError("source_text must be a non-empty string")
        if not isinstance(self.transformed_text, str) or not self.transformed_text:
            raise ValueError("transformed_text must be a non-empty string")
        if self.source_text == self.transformed_text:
            raise ValueError("review sample must change text")
        require_sha256("source_text_hash", self.source_text_hash)
        require_sha256("transformed_text_hash", self.transformed_text_hash)
        if self.source_text_hash != sha256_text(self.source_text):
            raise ValueError("source_text_hash does not match source_text")
        if self.transformed_text_hash != sha256_text(self.transformed_text):
            raise ValueError("transformed_text_hash does not match transformed_text")
        require_sha256("sample_hash", self.sample_hash)
        if self.sample_hash != sha256_json(self._payload()):
            raise ValueError("sample_hash does not match fidelity review sample")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": self.rule_hash,
            "sample_id": self.sample_id,
            "source_text": self.source_text,
            "transformed_text": self.transformed_text,
            "source_text_hash": self.source_text_hash,
            "transformed_text_hash": self.transformed_text_hash,
        }

    @classmethod
    def create(
        cls,
        rule_hash: str,
        sample_id: str,
        source_text: str,
        transformed_text: str,
    ) -> FidelityReviewSample:
        source_hash = sha256_text(source_text)
        transformed_hash = sha256_text(transformed_text)
        payload = {
            "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": rule_hash,
            "sample_id": sample_id,
            "source_text": source_text,
            "transformed_text": transformed_text,
            "source_text_hash": source_hash,
            "transformed_text_hash": transformed_hash,
        }
        return cls(
            rule_hash,
            sample_id,
            source_text,
            transformed_text,
            source_hash,
            transformed_hash,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class BlindReviewJudgment:
    rule_hash: str
    sample_id: str
    review_sample_hash: str
    reviewer_id: str
    label: FidelityLabel
    judgment_hash: str

    def __post_init__(self) -> None:
        require_sha256("rule_hash", self.rule_hash)
        require_clean_string("sample_id", self.sample_id)
        require_sha256("review_sample_hash", self.review_sample_hash)
        require_clean_string("reviewer_id", self.reviewer_id)
        if not isinstance(self.label, FidelityLabel):
            raise TypeError("label must be a FidelityLabel")
        require_sha256("judgment_hash", self.judgment_hash)
        if self.judgment_hash != sha256_json(self._payload()):
            raise ValueError("judgment_hash does not match blind review judgment")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": self.rule_hash,
            "sample_id": self.sample_id,
            "review_sample_hash": self.review_sample_hash,
            "reviewer_id": self.reviewer_id,
            "label": self.label.value,
        }

    @classmethod
    def create(
        cls,
        sample: FidelityReviewSample,
        reviewer_id: str,
        label: FidelityLabel,
    ) -> BlindReviewJudgment:
        if not isinstance(sample, FidelityReviewSample):
            raise TypeError("sample must be a FidelityReviewSample")
        payload = {
            "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": sample.rule_hash,
            "sample_id": sample.sample_id,
            "review_sample_hash": sample.sample_hash,
            "reviewer_id": reviewer_id,
            "label": label.value if isinstance(label, FidelityLabel) else label,
        }
        return cls(
            sample.rule_hash,
            sample.sample_id,
            sample.sample_hash,
            reviewer_id,
            label,
            sha256_json(payload),
        )


@dataclass(frozen=True, slots=True)
class FidelityAdjudication:
    sample_id: str
    review_sample_hash: str
    label: FidelityLabel
    judgment_hashes: tuple[str, ...]
    adjudication_hash: str

    def __post_init__(self) -> None:
        require_clean_string("sample_id", self.sample_id)
        require_sha256("review_sample_hash", self.review_sample_hash)
        if not isinstance(self.label, FidelityLabel):
            raise TypeError("label must be a FidelityLabel")
        if not isinstance(self.judgment_hashes, tuple):
            raise TypeError("judgment_hashes must be a tuple")
        if len(self.judgment_hashes) not in (2, 3):
            raise ValueError("adjudication must contain two reviewers or one tiebreak reviewer")
        if self.judgment_hashes != tuple(sorted(set(self.judgment_hashes))):
            raise ValueError("judgment_hashes must be unique and canonically ordered")
        for value in self.judgment_hashes:
            require_sha256("judgment_hash", value)
        require_sha256("adjudication_hash", self.adjudication_hash)
        if self.adjudication_hash != sha256_json(self._payload()):
            raise ValueError("adjudication_hash does not match fidelity adjudication")

    def _payload(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "review_sample_hash": self.review_sample_hash,
            "label": self.label.value,
            "judgment_hashes": self.judgment_hashes,
        }


@dataclass(frozen=True, slots=True)
class BlindHumanFidelityAudit:
    algorithm_version: str
    rule_hash: str
    review_policy_id: str
    review_samples: tuple[FidelityReviewSample, ...]
    judgments: tuple[BlindReviewJudgment, ...]
    adjudications: tuple[FidelityAdjudication, ...]
    sample_count: int
    equivalent_or_minor_count: int
    material_change_count: int
    cannot_judge_count: int
    audit_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != FIDELITY_EVIDENCE_ALGORITHM_VERSION:
            raise ValueError("unsupported fidelity evidence algorithm version")
        require_sha256("rule_hash", self.rule_hash)
        if self.review_policy_id != BLIND_HUMAN_REVIEW_POLICY_ID:
            raise ValueError("unsupported blind human review policy")
        if not isinstance(self.review_samples, tuple) or not self.review_samples:
            raise TypeError("review_samples must be a non-empty tuple")
        if not isinstance(self.judgments, tuple) or not self.judgments:
            raise TypeError("judgments must be a non-empty tuple")
        if not isinstance(self.adjudications, tuple) or not self.adjudications:
            raise TypeError("adjudications must be a non-empty tuple")
        expected_samples = tuple(sorted(self.review_samples, key=lambda value: (value.sample_id, value.sample_hash)))
        if self.review_samples != expected_samples:
            raise ValueError("review_samples must be canonically ordered")
        if len({value.sample_id for value in self.review_samples}) != len(self.review_samples):
            raise ValueError("review sample IDs must be unique")
        if len({value.sample_hash for value in self.review_samples}) != len(self.review_samples):
            raise ValueError("review samples must be unique")
        if any(value.rule_hash != self.rule_hash for value in self.review_samples):
            raise ValueError("all review samples must match audit rule hash")
        by_sample_id = {value.sample_id: value for value in self.review_samples}
        expected_judgments = tuple(sorted(self.judgments, key=lambda value: (value.sample_id, value.reviewer_id, value.judgment_hash)))
        if self.judgments != expected_judgments:
            raise ValueError("judgments must be canonically ordered")
        if len({(value.sample_id, value.reviewer_id) for value in self.judgments}) != len(self.judgments):
            raise ValueError("each reviewer may judge a sample at most once")
        if any(value.rule_hash != self.rule_hash for value in self.judgments):
            raise ValueError("all judgments must match audit rule hash")
        for judgment in self.judgments:
            try:
                sample = by_sample_id[judgment.sample_id]
            except KeyError as error:
                raise ValueError("judgment references unknown review sample") from error
            if judgment.review_sample_hash != sample.sample_hash:
                raise ValueError("judgment review sample hash does not match referenced sample")
        if {value.sample_id for value in self.judgments} != set(by_sample_id):
            raise ValueError("every review sample must have judgments")
        expected_adjudications = _adjudicate(self.review_samples, self.judgments)
        if self.adjudications != expected_adjudications:
            raise ValueError("adjudications do not match blind review judgments")
        counts = Counter(value.label for value in self.adjudications)
        if self.sample_count != len(self.review_samples):
            raise ValueError("sample_count does not match review samples")
        if self.sample_count != len(self.adjudications):
            raise ValueError("sample_count does not match adjudications")
        if self.equivalent_or_minor_count != counts[FidelityLabel.EQUIVALENT_OR_MINOR]:
            raise ValueError("equivalent_or_minor_count does not match adjudications")
        if self.material_change_count != counts[FidelityLabel.MATERIAL_CHANGE]:
            raise ValueError("material_change_count does not match adjudications")
        if self.cannot_judge_count != counts[FidelityLabel.CANNOT_JUDGE]:
            raise ValueError("cannot_judge_count does not match adjudications")
        require_sha256("audit_hash", self.audit_hash)
        if self.audit_hash != sha256_json(self._payload()):
            raise ValueError("audit_hash does not match blind human fidelity audit")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "rule_hash": self.rule_hash,
            "review_policy_id": self.review_policy_id,
            "review_samples": self.review_samples,
            "judgments": self.judgments,
            "adjudications": self.adjudications,
            "sample_count": self.sample_count,
            "equivalent_or_minor_count": self.equivalent_or_minor_count,
            "material_change_count": self.material_change_count,
            "cannot_judge_count": self.cannot_judge_count,
        }


def _adjudicate(
    review_samples: tuple[FidelityReviewSample, ...],
    judgments: tuple[BlindReviewJudgment, ...],
) -> tuple[FidelityAdjudication, ...]:
    by_sample_id = {value.sample_id: value for value in review_samples}
    grouped: dict[str, list[BlindReviewJudgment]] = defaultdict(list)
    for value in judgments:
        grouped[value.sample_id].append(value)
    output: list[FidelityAdjudication] = []
    for sample_id in sorted(by_sample_id):
        sample = by_sample_id[sample_id]
        rows = tuple(sorted(grouped.get(sample_id, ()), key=lambda value: (value.reviewer_id, value.judgment_hash)))
        if len(rows) not in (2, 3):
            raise ValueError("each fidelity sample requires exactly two reviewers or one tiebreak reviewer")
        if any(value.review_sample_hash != sample.sample_hash for value in rows):
            raise ValueError("judgment review sample hash does not match referenced sample")
        labels = Counter(value.label for value in rows)
        if len(rows) == 2:
            if len(labels) != 1:
                raise ValueError("disagreeing reviewers require exactly one third tiebreak review")
            label = rows[0].label
        else:
            if len(labels) == 1:
                raise ValueError("a third review is permitted only to resolve disagreement")
            label, count = labels.most_common(1)[0]
            if count != 2:
                raise ValueError("three-way reviewer disagreement cannot be adjudicated")
        hashes = tuple(sorted(value.judgment_hash for value in rows))
        payload = {
            "sample_id": sample_id,
            "review_sample_hash": sample.sample_hash,
            "label": label.value,
            "judgment_hashes": hashes,
        }
        output.append(FidelityAdjudication(sample_id, sample.sample_hash, label, hashes, sha256_json(payload)))
    return tuple(output)


def create_blind_human_fidelity_audit(
    rule_hash: str,
    review_samples: tuple[FidelityReviewSample, ...],
    judgments: tuple[BlindReviewJudgment, ...],
) -> BlindHumanFidelityAudit:
    samples = tuple(sorted(tuple(review_samples), key=lambda value: (value.sample_id, value.sample_hash)))
    ordered = tuple(sorted(tuple(judgments), key=lambda value: (value.sample_id, value.reviewer_id, value.judgment_hash)))
    adjudications = _adjudicate(samples, ordered)
    counts = Counter(value.label for value in adjudications)
    payload = {
        "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
        "rule_hash": rule_hash,
        "review_policy_id": BLIND_HUMAN_REVIEW_POLICY_ID,
        "review_samples": samples,
        "judgments": ordered,
        "adjudications": adjudications,
        "sample_count": len(samples),
        "equivalent_or_minor_count": counts[FidelityLabel.EQUIVALENT_OR_MINOR],
        "material_change_count": counts[FidelityLabel.MATERIAL_CHANGE],
        "cannot_judge_count": counts[FidelityLabel.CANNOT_JUDGE],
    }
    return BlindHumanFidelityAudit(
        FIDELITY_EVIDENCE_ALGORITHM_VERSION,
        rule_hash,
        BLIND_HUMAN_REVIEW_POLICY_ID,
        samples,
        ordered,
        adjudications,
        len(samples),
        counts[FidelityLabel.EQUIVALENT_OR_MINOR],
        counts[FidelityLabel.MATERIAL_CHANGE],
        counts[FidelityLabel.CANNOT_JUDGE],
        sha256_json(payload),
    )


@dataclass(frozen=True, slots=True)
class GrammarFixture:
    rule_hash: str
    fixture_id: str
    source_text: str
    disposition: GrammarFixtureDisposition
    expected_output_text: str | None
    expected_rejection_reason: CandidateRejectionReason | None
    fixture_hash: str

    def __post_init__(self) -> None:
        require_sha256("rule_hash", self.rule_hash)
        require_clean_string("fixture_id", self.fixture_id)
        if not isinstance(self.source_text, str) or not self.source_text:
            raise ValueError("source_text must be a non-empty string")
        if not isinstance(self.disposition, GrammarFixtureDisposition):
            raise TypeError("disposition must be a GrammarFixtureDisposition")
        if self.disposition is GrammarFixtureDisposition.CANDIDATE:
            if not isinstance(self.expected_output_text, str) or not self.expected_output_text:
                raise ValueError("candidate grammar fixtures require expected_output_text")
            if self.expected_output_text == self.source_text:
                raise ValueError("candidate grammar fixture must change text")
            if self.expected_rejection_reason is not None:
                raise ValueError("candidate grammar fixtures cannot name a rejection reason")
        else:
            if self.expected_output_text is not None:
                raise ValueError("rejection grammar fixtures cannot name expected output text")
            if not isinstance(self.expected_rejection_reason, CandidateRejectionReason):
                raise TypeError("rejection grammar fixtures require a CandidateRejectionReason")
        require_sha256("fixture_hash", self.fixture_hash)
        if self.fixture_hash != sha256_json(self._payload()):
            raise ValueError("fixture_hash does not match grammar fixture")

    def _payload(self) -> dict[str, object]:
        return {
            "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": self.rule_hash,
            "fixture_id": self.fixture_id,
            "source_text": self.source_text,
            "disposition": self.disposition.value,
            "expected_output_text": self.expected_output_text,
            "expected_rejection_reason": None if self.expected_rejection_reason is None else self.expected_rejection_reason.value,
        }

    @classmethod
    def candidate(
        cls,
        rule_hash: str,
        fixture_id: str,
        source_text: str,
        expected_output_text: str,
    ) -> GrammarFixture:
        payload = {
            "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": rule_hash,
            "fixture_id": fixture_id,
            "source_text": source_text,
            "disposition": GrammarFixtureDisposition.CANDIDATE.value,
            "expected_output_text": expected_output_text,
            "expected_rejection_reason": None,
        }
        return cls(rule_hash, fixture_id, source_text, GrammarFixtureDisposition.CANDIDATE, expected_output_text, None, sha256_json(payload))

    @classmethod
    def rejection(
        cls,
        rule_hash: str,
        fixture_id: str,
        source_text: str,
        reason: CandidateRejectionReason,
    ) -> GrammarFixture:
        payload = {
            "algorithm_version": FIDELITY_EVIDENCE_ALGORITHM_VERSION,
            "rule_hash": rule_hash,
            "fixture_id": fixture_id,
            "source_text": source_text,
            "disposition": GrammarFixtureDisposition.REJECTION.value,
            "expected_output_text": None,
            "expected_rejection_reason": reason.value if isinstance(reason, CandidateRejectionReason) else reason,
        }
        return cls(rule_hash, fixture_id, source_text, GrammarFixtureDisposition.REJECTION, None, reason, sha256_json(payload))
