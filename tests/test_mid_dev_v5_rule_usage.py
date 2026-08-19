import ast
from pathlib import Path

from fuckmark.experiments.mid_dev_v5_rule_usage import (
    LEGACY_TRACE_KIND,
    NORMALIZED_TRACE_KIND,
    MidDevV5RuleUsageTrace,
)
from fuckmark.hashing import sha256_text


def test_rule_usage_trace_binds_selection_trace_and_rule_sequence():
    value = MidDevV5RuleUsageTrace.create(
        trace_kind=LEGACY_TRACE_KIND,
        selection_trace_hash=sha256_text("selection-trace"),
        sample_id="sample-0001",
        rule_hashes=(sha256_text("rule-a"), sha256_text("rule-b")),
    )
    assert value.trace_kind == LEGACY_TRACE_KIND
    assert len(value.rule_hashes) == 2
    assert MidDevV5RuleUsageTrace.create(
        trace_kind=NORMALIZED_TRACE_KIND,
        selection_trace_hash=sha256_text("selection-trace-2"),
        sample_id="sample-0002",
        rule_hashes=(),
    ).rule_hashes == ()


def test_rule_usage_replay_module_does_not_import_detector_scoring():
    path = Path("fuckmark/experiments/mid_dev_v5_rule_usage.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any("detector" in name.lower() for name in imports)
    assert not any("scoring" in name.lower() for name in imports)
