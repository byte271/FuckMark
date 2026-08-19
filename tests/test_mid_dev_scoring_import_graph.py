from __future__ import annotations

import json
import subprocess
import sys


def test_production_middev_scorer_does_not_transitively_load_selection_modules() -> None:
    code = (
        "import json,sys; "
        "import fuckmark.mid_dev_context_survival_score_hf; "
        "forbidden=('mid_dev_context_survival','mid_dev_freeze','mid_dev_plan_builder','mid_dev_context_survival_plan_hf','mid_dev_plan_io','tiny_dev_transform_hf','scheduling.state_search','scheduling.beam_v2','scheduling.context_survival'); "
        "loaded=sorted(name for name in sys.modules if any(value in name for value in forbidden)); "
        "print(json.dumps(loaded)); "
        "raise SystemExit(1 if loaded else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    loaded = json.loads(result.stdout or "[]")
    assert result.returncode == 0, loaded
    assert loaded == []
