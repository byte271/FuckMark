from __future__ import annotations

from .adapters import WatermarkAdapter
from .native_observations import NativeObservationBatch, build_native_observations


class NativeObservationVerificationError(ValueError):
    pass


def verify_native_observation_batch(
    batch: NativeObservationBatch,
    adapter: WatermarkAdapter,
) -> None:
    if not isinstance(batch, NativeObservationBatch):
        raise TypeError("batch must be a NativeObservationBatch")
    if not isinstance(adapter, WatermarkAdapter):
        raise TypeError("adapter must satisfy WatermarkAdapter")
    expected = build_native_observations(
        batch.sample_id,
        batch.token_ids,
        batch.eos_token_id,
        adapter,
    )
    if batch != expected:
        raise NativeObservationVerificationError(
            "native observation batch does not replay exactly from the supplied adapter"
        )
