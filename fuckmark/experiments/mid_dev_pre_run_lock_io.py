from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from ..config import canonical_json_text
from ..corpus.tiny_dev_io import _mapping
from .mid_dev_plan_io import MID_DEV_PLAN_JSON_MAX_BYTES, MidDevPlanJsonError, _parse_json
from .mid_dev_pre_run_lock import PreRunScientificLock


_PRE_RUN_FIELDS = tuple(field.name for field in fields(PreRunScientificLock))
_STRING_TUPLE_FIELDS = frozenset(
    {
        "calibration_audit_artifact_hashes",
        "candidate_rule_hashes",
        "normalized_primary_cells",
        "stop_rules",
        "primary_metrics",
        "primary_comparisons",
        "ineligibility_rules",
        "quality_gates",
        "fallback_logic",
    }
)
_INT_TUPLE_FIELDS = frozenset({"target_lengths", "legacy_budgets"})


def parse_pre_run_scientific_lock_json(
    text: str,
    *,
    require_canonical: bool = True,
) -> PreRunScientificLock:
    decoded = _parse_json(text)
    try:
        data = _mapping("pre_run_scientific_lock", decoded, _PRE_RUN_FIELDS)
        values = dict(data)
        for name in _STRING_TUPLE_FIELDS:
            raw = values[name]
            if not isinstance(raw, list) or any(not isinstance(value, str) for value in raw):
                raise TypeError(f"{name} must be a JSON array of strings")
            values[name] = tuple(raw)
        for name in _INT_TUPLE_FIELDS:
            raw = values[name]
            if not isinstance(raw, list) or any(isinstance(value, bool) or not isinstance(value, int) for value in raw):
                raise TypeError(f"{name} must be a JSON array of integers")
            values[name] = tuple(raw)
        lock = PreRunScientificLock(**values)
    except Exception as error:
        if isinstance(error, MidDevPlanJsonError):
            raise
        raise MidDevPlanJsonError("pre-run scientific lock failed validation") from error
    if require_canonical and text not in (
        canonical_json_text(lock),
        canonical_json_text(lock) + "\n",
    ):
        raise MidDevPlanJsonError("pre-run scientific lock JSON is not canonical")
    return lock


def load_pre_run_scientific_lock_json(path: str | Path) -> PreRunScientificLock:
    file_path = Path(path)
    if file_path.stat().st_size > MID_DEV_PLAN_JSON_MAX_BYTES:
        raise MidDevPlanJsonError("pre-run scientific lock JSON exceeds the size limit")
    return parse_pre_run_scientific_lock_json(file_path.read_text(encoding="utf-8"))
