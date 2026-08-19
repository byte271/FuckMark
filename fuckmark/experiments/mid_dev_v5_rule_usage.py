from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .._validation import require_int, require_sha256
from ..hashing import sha256_json
from .context_survival_plan import _context_registry
from .mid_dev_plan_builder import MidDevSelectionTraceArtifact
from .mid_dev_plan_v5 import MidDevDevelopmentPlanV5
from .mid_dev_v5_builder import (
    MidDevNormalizedTraceArtifact,
    _replay_rule_hashes,
)


MID_DEV_V5_RULE_USAGE_TRACE_VERSION = "mid-dev-v5-rule-usage-trace-v1"
MID_DEV_V5_RULE_USAGE_ARTIFACT_VERSION = "mid-dev-v5-rule-usage-artifact-v1"
LEGACY_TRACE_KIND = "LEGACY_V4"
NORMALIZED_TRACE_KIND = "NORMALIZED_V5"


@dataclass(frozen=True, slots=True)
class MidDevV5RuleUsageTrace:
    trace_kind: str
    selection_trace_hash: str
    sample_id: str
    rule_hashes: tuple[str, ...]
    trace_hash: str

    def __post_init__(self) -> None:
        if self.trace_kind not in {LEGACY_TRACE_KIND, NORMALIZED_TRACE_KIND}:
            raise ValueError("unsupported rule-usage trace kind")
        require_sha256("selection_trace_hash", self.selection_trace_hash)
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        if not isinstance(self.rule_hashes, tuple):
            raise TypeError("rule_hashes must be a tuple")
        for value in self.rule_hashes:
            require_sha256("rule_hash", value)
        require_sha256("trace_hash", self.trace_hash)
        if self.trace_hash != sha256_json(self.payload()):
            raise ValueError("rule-usage trace hash mismatch")

    @classmethod
    def create(
        cls,
        *,
        trace_kind: str,
        selection_trace_hash: str,
        sample_id: str,
        rule_hashes: tuple[str, ...],
    ) -> "MidDevV5RuleUsageTrace":
        payload = {
            "algorithm_version": MID_DEV_V5_RULE_USAGE_TRACE_VERSION,
            "trace_kind": trace_kind,
            "selection_trace_hash": selection_trace_hash,
            "sample_id": sample_id,
            "rule_hashes": rule_hashes,
        }
        return cls(
            trace_kind=trace_kind,
            selection_trace_hash=selection_trace_hash,
            sample_id=sample_id,
            rule_hashes=rule_hashes,
            trace_hash=sha256_json(payload),
        )

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_RULE_USAGE_TRACE_VERSION,
            "trace_kind": self.trace_kind,
            "selection_trace_hash": self.selection_trace_hash,
            "sample_id": self.sample_id,
            "rule_hashes": self.rule_hashes,
        }


@dataclass(frozen=True, slots=True)
class MidDevV5RuleUsageArtifact:
    development_plan_hash: str
    legacy_trace_artifact_hash: str
    normalized_trace_artifact_hash: str
    selection_attestation_hash: str
    candidate_registry_hash: str
    traces: tuple[MidDevV5RuleUsageTrace, ...]
    rule_usage_counts: tuple[tuple[str, int], ...]
    artifact_hash: str

    def __post_init__(self) -> None:
        for name in (
            "development_plan_hash",
            "legacy_trace_artifact_hash",
            "normalized_trace_artifact_hash",
            "selection_attestation_hash",
            "candidate_registry_hash",
            "artifact_hash",
        ):
            require_sha256(name, getattr(self, name))
        if not isinstance(self.traces, tuple) or len(self.traces) != 8136:
            raise ValueError("rule-usage artifact requires 5688 legacy + 2448 normalized traces")
        if any(not isinstance(value, MidDevV5RuleUsageTrace) for value in self.traces):
            raise TypeError("rule-usage artifact contains invalid trace")
        selection_hashes = tuple(value.selection_trace_hash for value in self.traces)
        if len(set(selection_hashes)) != len(selection_hashes):
            raise ValueError("selection trace hashes must be unique across rule-usage artifact")
        if tuple(sorted(self.rule_usage_counts)) != self.rule_usage_counts:
            raise ValueError("rule usage counts must be canonically sorted")
        observed: dict[str, int] = {}
        for trace in self.traces:
            for rule_hash in trace.rule_hashes:
                observed[rule_hash] = observed.get(rule_hash, 0) + 1
        expected = tuple(sorted(observed.items()))
        if self.rule_usage_counts != expected:
            raise ValueError("rule usage counts do not reproduce trace rows")
        for rule_hash, count in self.rule_usage_counts:
            require_sha256("rule_hash", rule_hash)
            require_int("rule_usage_count", count)
            if count <= 0:
                raise ValueError("rule usage counts must be positive")
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("rule-usage artifact hash mismatch")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": MID_DEV_V5_RULE_USAGE_ARTIFACT_VERSION,
            "development_plan_hash": self.development_plan_hash,
            "legacy_trace_artifact_hash": self.legacy_trace_artifact_hash,
            "normalized_trace_artifact_hash": self.normalized_trace_artifact_hash,
            "selection_attestation_hash": self.selection_attestation_hash,
            "candidate_registry_hash": self.candidate_registry_hash,
            "trace_hashes": tuple(value.trace_hash for value in self.traces),
            "rule_usage_counts": self.rule_usage_counts,
        }


def build_mid_dev_v5_rule_usage_artifact(
    corpus: Any,
    plan: MidDevDevelopmentPlanV5,
    legacy_traces: MidDevSelectionTraceArtifact,
    normalized_traces: MidDevNormalizedTraceArtifact,
) -> MidDevV5RuleUsageArtifact:
    if legacy_traces.plan_hash != plan.legacy_plan.plan_hash:
        raise ValueError("legacy trace artifact does not bind embedded legacy plan")
    if normalized_traces.development_plan_hash != plan.plan_hash:
        raise ValueError("normalized trace artifact does not bind v5 plan")
    attestation = plan.legacy_plan.selection_attestation
    if (
        attestation.detector_access_observed
        or attestation.secret_access_observed
        or attestation.detector_query_count
        or attestation.secret_query_count
    ):
        raise ValueError("legacy selection attestation is contaminated")
    samples = {sample.sample_id: sample for sample in corpus.manifest.samples}
    if len(samples) != 72:
        raise ValueError("rule-usage replay requires exactly 72 source samples")
    legacy_plan_trace_hashes = {row.selection_trace_hash for row in plan.legacy_plan.rows}
    normalized_plan_trace_hashes = {row.selection_trace_hash for row in plan.normalized_rows}
    if legacy_plan_trace_hashes != {trace.trace_hash for trace in legacy_traces.traces}:
        raise ValueError("legacy plan/trace coverage is incomplete")
    if normalized_plan_trace_hashes != {trace.trace_hash for trace in normalized_traces.traces}:
        raise ValueError("normalized plan/trace coverage is incomplete")
    if legacy_plan_trace_hashes & normalized_plan_trace_hashes:
        raise ValueError("legacy and normalized selection trace hashes overlap")
    registry = _context_registry()
    materialized: list[MidDevV5RuleUsageTrace] = []
    for trace in legacy_traces.traces:
        source = samples.get(trace.sample_id)
        if source is None:
            raise ValueError("legacy trace references unknown sample")
        rule_hashes = _replay_rule_hashes(registry, source.text, trace.operation_hashes)
        if len(rule_hashes) != len(trace.operation_hashes):
            raise ValueError("legacy rule replay length mismatch")
        materialized.append(
            MidDevV5RuleUsageTrace.create(
                trace_kind=LEGACY_TRACE_KIND,
                selection_trace_hash=trace.trace_hash,
                sample_id=trace.sample_id,
                rule_hashes=rule_hashes,
            )
        )
    for trace in normalized_traces.traces:
        if trace.detector_access_observed or trace.secret_access_observed:
            raise ValueError("normalized selection trace is contaminated")
        materialized.append(
            MidDevV5RuleUsageTrace.create(
                trace_kind=NORMALIZED_TRACE_KIND,
                selection_trace_hash=trace.trace_hash,
                sample_id=trace.sample_id,
                rule_hashes=trace.rule_hashes,
            )
        )
    traces = tuple(
        sorted(
            materialized,
            key=lambda value: (value.trace_kind, value.sample_id, value.selection_trace_hash),
        )
    )
    counts: dict[str, int] = {}
    for trace in traces:
        for rule_hash in trace.rule_hashes:
            counts[rule_hash] = counts.get(rule_hash, 0) + 1
    rule_usage_counts = tuple(sorted(counts.items()))
    payload = {
        "algorithm_version": MID_DEV_V5_RULE_USAGE_ARTIFACT_VERSION,
        "development_plan_hash": plan.plan_hash,
        "legacy_trace_artifact_hash": legacy_traces.artifact_hash,
        "normalized_trace_artifact_hash": normalized_traces.artifact_hash,
        "selection_attestation_hash": attestation.attestation_hash,
        "candidate_registry_hash": registry.ruleset_hash,
        "trace_hashes": tuple(value.trace_hash for value in traces),
        "rule_usage_counts": rule_usage_counts,
    }
    return MidDevV5RuleUsageArtifact(
        development_plan_hash=plan.plan_hash,
        legacy_trace_artifact_hash=legacy_traces.artifact_hash,
        normalized_trace_artifact_hash=normalized_traces.artifact_hash,
        selection_attestation_hash=attestation.attestation_hash,
        candidate_registry_hash=registry.ruleset_hash,
        traces=traces,
        rule_usage_counts=rule_usage_counts,
        artifact_hash=sha256_json(payload),
    )
