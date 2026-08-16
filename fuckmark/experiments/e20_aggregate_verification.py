from __future__ import annotations

from ..corpus import CorpusManifest
from .confirmatory import ConfirmatoryPreregistration
from .e20_aggregate import E20AggregateBundle, build_e20_aggregate_bundle
from .e20_bundle import E20ResultBundle
from .e20_conditions import E20ConditionPlan
from .e20_execution import E20ExecutionAuthorization


class E20AggregateVerificationError(ValueError):
    pass


def verify_e20_aggregate_bundle(
    aggregate: E20AggregateBundle,
    result_bundle: E20ResultBundle,
    preregistration: ConfirmatoryPreregistration,
    corpus_manifest: CorpusManifest,
    condition_plan: E20ConditionPlan,
    authorization: E20ExecutionAuthorization,
) -> None:
    if not isinstance(aggregate, E20AggregateBundle):
        raise TypeError("aggregate must be an E20AggregateBundle")
    expected = build_e20_aggregate_bundle(
        result_bundle,
        preregistration,
        corpus_manifest,
        condition_plan,
        authorization,
    )
    if aggregate != expected:
        raise E20AggregateVerificationError(
            "E20 aggregate bundle does not replay exactly from the sealed result bundle and confirmatory inputs"
        )
