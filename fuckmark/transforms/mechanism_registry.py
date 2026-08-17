from __future__ import annotations

from collections.abc import Sequence

from .mechanism_rules import mechanism_stress_rules
from .registry import TransformRegistry
from .rules import default_contraction_rules


def mechanism_stress_transform_registry(identifiers: Sequence[str] = ()) -> TransformRegistry:
    return TransformRegistry((*default_contraction_rules(), *mechanism_stress_rules()), identifiers)
