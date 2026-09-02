import json
from io import StringIO
from pathlib import Path

import pytest

from fuckmark.cli import main
from fuckmark.cycle8.gate_v2 import (
    CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH,
    CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH,
)
from fuckmark.hashing import sha256_file, sha256_json
from fuckmark.robustness import (
    ATTACK_IDS,
    FREEZE_PATH,
    PROTOCOL_PATH,
    ROBUSTNESS_ALGORITHM_VERSION,
    ROBUSTNESS_EXIT_MISMATCH,
    ROBUSTNESS_EXIT_OK,
    ROBUSTNESS_EXIT_USAGE,
    SEALED_DETECTOR_SCORECARD_HASH,
    SEALED_DETECTOR_SCORECARD_PATH,
    VECTORS_PATH,
    apply_attack,
    apply_required_sanitizer_bundle,
    build_vectors_payload,
    freeze_bindings,
    fixture_ids,
    fixture_source,
    iter_cells,
    load_vectors,
    measure_cell,
    run_robustness_argv,
    run_robustness_bench,
    strip_default_ignorable,
    strip_enclosing_marks,
    strip_nonspacing_marks,
    strip_other_controls,
    unicode_sanitizer,
)


ROOT = Path(__file__).resolve().parents[1]
MIXED_FIXTURES = tuple(name for name in fixture_ids() if name != "digits")


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = run_robustness_argv(argv, out, err)
    return code, out.getvalue(), err.getvalue()


def test_robustness_freeze_binds_protocol_vectors_and_scorecard() -> None:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    payload = load_vectors()
    live = freeze_bindings()
    assert freeze["algorithm_version"] == ROBUSTNESS_ALGORITHM_VERSION
    assert freeze["protocol_id"] == "fuckmark-robustness-bench-v1"
    assert freeze["protocol_sha256"] == sha256_file(PROTOCOL_PATH) == live["protocol_sha256"]
    assert freeze["vectors_file_sha256"] == sha256_file(VECTORS_PATH) == live["vectors_file_sha256"]
    assert freeze["vectors_canonical_sha256"] == sha256_json(payload) == live["vectors_canonical_sha256"]
    assert freeze["sealed_detector_scorecard_path"] == SEALED_DETECTOR_SCORECARD_PATH
    assert freeze["sealed_detector_scorecard_hash"] == SEALED_DETECTOR_SCORECARD_HASH
    assert freeze["sealed_detector_scorecard_file_sha256"] == live["sealed_detector_scorecard_file_sha256"]
    assert payload["algorithm_version"] == ROBUSTNESS_ALGORITHM_VERSION
    assert "fuckmark-robustness-bench-v1" in PROTOCOL_PATH.read_text(encoding="utf-8")
    assert "does **not** rerun" in PROTOCOL_PATH.read_text(encoding="utf-8")


def test_sealed_scorecard_constants_match_gate_v2() -> None:
    assert SEALED_DETECTOR_SCORECARD_PATH == CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_PATH
    assert SEALED_DETECTOR_SCORECARD_HASH == CYCLE8_GATE_V2_CONFIRMATION_SCORECARD_HASH
    scorecard = json.loads((ROOT / SEALED_DETECTOR_SCORECARD_PATH).read_text(encoding="utf-8"))
    assert scorecard["scorecard_hash"] == SEALED_DETECTOR_SCORECARD_HASH
    assert scorecard["identity_watermarked_detected"] == 188
    assert scorecard["mix_watermarked_detected_by_required_sanitizer"]["raw"] == 0
    assert scorecard["visible_pass_rate"] == "192/192"


def test_vectors_replay_all_cells_and_match_live_payload() -> None:
    payload = load_vectors()
    cells = iter_cells()
    assert len(payload["cells"]) == 180
    assert len(cells) == 180
    assert payload["attacks"] == list(ATTACK_IDS)
    assert [item["id"] for item in payload["fixtures"]] == list(fixture_ids())
    expected = {item["id"]: item["expect"] for item in payload["cells"]}
    for cell in cells:
        key = f"{cell.fixture_id}/{cell.attack_id}"
        assert expected[key]["restores_source"] is cell.restores_source
        assert expected[key]["mix_projection_equals_source"] is cell.mix_projection_equals_source
        assert expected[key]["projection_equals_source"] is cell.projection_equals_source
        assert expected[key]["carrier_detected"] is cell.carrier_detected
        assert expected[key]["residual_categories"] == list(cell.residual_categories)
        assert expected[key]["mix_sha256"] == cell.mix_sha256
        assert expected[key]["output_sha256"] == cell.output_sha256
    assert build_vectors_payload() == payload


def test_digits_restore_and_mixed_fixtures_never_restore() -> None:
    report = run_robustness_bench()
    summary = report["summary"]
    assert summary["cells"] == 180
    assert summary["restores_source"] == 18
    assert summary["mix_projection_equals_source"] == 180
    assert summary["mismatches"] == 0
    assert report["sealed_detector_ok"] is True
    digits = [cell for cell in iter_cells(fixtures=("digits",))]
    assert len(digits) == 18
    assert all(cell.restores_source for cell in digits)
    assert all(not cell.carrier_detected for cell in digits)
    mixed = [cell for cell in iter_cells(fixtures=MIXED_FIXTURES)]
    assert mixed
    assert all(not cell.restores_source for cell in mixed)
    assert all(cell.mix_projection_equals_source for cell in mixed)


def test_ascii_prose_mn_me_us_cf_does_not_restore_or_keep_carriers() -> None:
    cell = measure_cell("ascii_prose", "mn_me_us_cf")
    assert cell.restores_source is False
    assert cell.carrier_detected is False
    assert cell.projection_equals_source is False
    assert cell.residual_categories == ()
    identity = measure_cell("ascii_prose", "identity")
    assert identity.carrier_detected is True
    assert identity.restores_source is False
    assert identity.projection_equals_source is True


def test_attacks_match_cycle8_reference_sanitizers() -> None:
    from fuckmark.cycle8.benchmark import (
        strip_default_ignorable as ref_di,
        strip_enclosing_marks as ref_me,
        strip_nonspacing_marks as ref_mn,
        strip_other_controls as ref_cc,
    )
    from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle as ref_bundle
    from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer

    mixed = measure_cell("ascii_prose", "identity").mixed
    assert strip_nonspacing_marks(mixed) == ref_mn(mixed)
    assert strip_default_ignorable(mixed) == ref_di(mixed)
    assert strip_enclosing_marks(mixed) == ref_me(mixed)
    assert strip_other_controls(mixed) == ref_cc(mixed)
    assert unicode_sanitizer(mixed) == lm_watermarking_unicode_sanitizer(mixed)
    assert apply_required_sanitizer_bundle(mixed) == ref_bundle(mixed)
    assert apply_attack("unicode_sanitizer", mixed) == lm_watermarking_unicode_sanitizer(mixed)
    assert apply_attack("required_bundle", mixed) == ref_bundle(mixed)


def test_unknown_fixture_and_attack_raise() -> None:
    with pytest.raises(ValueError, match="unknown robustness fixture"):
        fixture_source("not_a_fixture")
    with pytest.raises(ValueError, match="unknown robustness attack"):
        apply_attack("not_an_attack", "x")
    with pytest.raises(TypeError, match="text must be a string"):
        apply_attack("identity", 1)
    with pytest.raises(ValueError, match="unknown robustness fixtures"):
        iter_cells(fixtures=("nope",))
    with pytest.raises(ValueError, match="unknown robustness attacks"):
        iter_cells(attacks=("nope",))


def test_cli_json_and_main_dispatch() -> None:
    code, out, err = _run(["--json", "--fixture", "digits", "--attack", "identity"])
    assert code == ROBUSTNESS_EXIT_OK
    assert err == ""
    payload = json.loads(out)
    assert payload["algorithm_version"] == ROBUSTNESS_ALGORITHM_VERSION
    assert payload["summary"]["cells"] == 1
    assert payload["summary"]["restores_source"] == 1
    assert payload["summary"]["mismatches"] == 0
    assert payload["sealed_detector_ok"] is True
    assert payload["cells"][0]["id"] == "digits/identity"
    dispatched_out, dispatched_err = StringIO(), StringIO()
    dispatched = main(
        StringIO(""),
        dispatched_out,
        error_stream=dispatched_err,
        argv=("robustness", "--json", "--fixture", "digits"),
    )
    assert dispatched == ROBUSTNESS_EXIT_OK
    report = json.loads(dispatched_out.getvalue())
    assert report["summary"]["cells"] == 18
    assert report["summary"]["restores_source"] == 18


def test_cli_human_report_and_quiet() -> None:
    code, out, err = _run(["--fixture", "digits", "--attack", "nfc"])
    assert code == ROBUSTNESS_EXIT_OK
    assert out == ""
    assert "1 cells" in err
    assert "1 restore the source" in err
    assert "0 mismatches" in err
    assert "Detectors were not rerun" in err
    quiet_code, quiet_out, quiet_err = _run(["-q", "--fixture", "digits", "--attack", "nfc"])
    assert quiet_code == ROBUSTNESS_EXIT_OK
    assert quiet_out == ""
    assert quiet_err == ""


def test_cli_usage_errors() -> None:
    code, _out, err = _run(["--fixture", "not_a_fixture"])
    assert code == ROBUSTNESS_EXIT_USAGE
    assert "unknown robustness fixtures" in err
    attack_code, _out2, attack_err = _run(["--attack", "not_an_attack"])
    assert attack_code == ROBUSTNESS_EXIT_USAGE
    assert "unknown robustness attacks" in attack_err


def test_cli_mismatch_is_exit_one(monkeypatch) -> None:
    monkeypatch.setattr("fuckmark.robustness.load_vectors", lambda: {"cells": []})
    code, out, err = _run(["--json", "--fixture", "digits", "--attack", "identity"])
    assert code == ROBUSTNESS_EXIT_MISMATCH
    payload = json.loads(out)
    assert payload["summary"]["mismatches"] == 1
    assert "digits/identity" in err or payload["mismatches"][0]["id"] == "digits/identity"


def test_cli_help_mentions_robustness_bench(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(argv=("--help",))
    assert result.value.code == 0
    rendered = capsys.readouterr().out
    assert "fuckmark robustness" in rendered
    assert "sanitizer-restore" in rendered
    assert "no detector rerun" in rendered
