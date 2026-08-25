import json
from pathlib import Path

from fuckmark.cycle8.compare import (
    CYCLE8_U034F_SPACE_ARM_ID,
    CYCLE8_U200C_SPACE_ARM_ID,
    measure_carrier_arm,
    run_fixture_compare,
)
from fuckmark.cycle8.decision import INSUFFICIENT_EVIDENCE, classify_fixture_compare
from fuckmark.cycle8.tokenizer_screen import GPT2_FIXTURE
from fuckmark.hashing import sha256_json
from fuckmark.product.domain import is_supported_product_domain_v1
from fuckmark.cycle8.scoreboard import ProductGate


def test_github_ci_cli_e2e_expects_unchanged_visible_text() -> None:
    text = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "I don't agree" not in text
    assert "I can't stay" not in text
    assert 'test "$output" = "I do not agree and I cannot stay."' in text
    assert 'test "$(printf \'I do not agree.\\n\' | FuckMark)" = "I do not agree."' in text


def test_cycle8_fixture_compare_passes_visible_projection_without_encoder() -> None:
    report = run_fixture_compare(encoder=None)
    assert report["visible_pass_rate"] == "20/20"
    decision = classify_fixture_compare(report)
    assert decision["product_gate"] == ProductGate.PASS.value
    assert decision["decision"] == INSUFFICIENT_EVIDENCE
    screen = next(row for row in report["rows"] if row["source_sample_id"] == "gpt2-screen")
    u034f = screen["arms"][CYCLE8_U034F_SPACE_ARM_ID]
    u200c = screen["arms"][CYCLE8_U200C_SPACE_ARM_ID]
    assert u034f["visible_ok"] is True
    assert u034f["selected_count"] > 0
    assert u034f["sanitizers"]["cf_strip"]["equals_transformed"] is True
    assert u034f["sanitizers"]["nfkc"]["equals_transformed"] is True
    assert u034f["sanitizers"]["ws_collapse"]["equals_transformed"] is True
    assert u200c["sanitizers"]["cf_strip"]["equals_source"] is True
    quote = next(row for row in report["rows"] if row["source_sample_id"] == "quote-interior")
    assert quote["arms"][CYCLE8_U034F_SPACE_ARM_ID]["protected_blocked_count"] > 0


def test_cycle8_url_fixture_keeps_protected_machine_text() -> None:
    source = "See https://example.com/do-not-touch and continue the notes."
    assert is_supported_product_domain_v1(source)
    measurement = measure_carrier_arm(
        arm_id=CYCLE8_U034F_SPACE_ARM_ID,
        source_sample_id="url-protected",
        source_text=source,
    )
    transformed = str(measurement["transformed_text"])
    assert "https://example.com/do-not-touch" in transformed.replace("\u034f", "")
    assert measurement["visible_ok"] is True
    assert measurement["selected_count"] > 0


def test_cycle8_committed_fixture_compare_pins_visibility_and_tokenizer() -> None:
    path = Path(__file__).resolve().parents[1] / "specs" / "cycle8" / "fixture-compare-v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    assert payload["artifact_hash"] == sha256_json(body)
    assert payload["visible_pass_rate"] == "20/20"
    assert payload["encoder"] == "gpt2"
    screen = next(row for row in payload["rows"] if row["source_sample_id"] == "gpt2-screen")
    u034f = screen["arms"][CYCLE8_U034F_SPACE_ARM_ID]
    assert u034f["tokenizer"]["ids_equal"] is False
    assert u034f["tokenizer"]["token_count_delta"] > 0
    decision_path = Path(__file__).resolve().parents[1] / "specs" / "cycle8" / "fixture-decision-v1.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    assert decision["product_gate"] == "VISIBLE_INVARIANT_PASS"
    assert decision["decision"] == INSUFFICIENT_EVIDENCE
    assert GPT2_FIXTURE.startswith("The researchers")
