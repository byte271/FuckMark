from __future__ import annotations

from collections.abc import Sequence

from ..transforms.cycle7_quote_policy import (
    CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID,
    CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID,
)
from ..transforms.effectiveness_profile import content_region_destruction_surface_rules
from ..transforms.registry import TransformRegistry
from .durable_rules import cycle7_durable_rules


CYCLE7_DURABLE_REGISTRY_ID = "cycle7-durable-catalog-v4"
CYCLE7_COMBINED_REGISTRY_ID = "cycle7-durable-plus-cycle6-spacing-v3"
CYCLE7_STAGE_B_DURABLE_REGISTRY_ID = "cycle7-durable-catalog-v3"


def cycle7_durable_transform_registry(identifiers: Sequence[str] = ()) -> TransformRegistry:
    return TransformRegistry(
        cycle7_durable_rules(),
        identifiers,
        quote_policy_id=CYCLE7_QUOTE_SAFE_DURABLE_POLICY_ID,
    )


def cycle7_combined_transform_registry(identifiers: Sequence[str] = ()) -> TransformRegistry:
    return TransformRegistry(
        (*cycle7_durable_rules(), *content_region_destruction_surface_rules()),
        identifiers,
        quote_policy_id=CYCLE7_QUOTE_SAFE_MIXED_POLICY_ID,
    )
