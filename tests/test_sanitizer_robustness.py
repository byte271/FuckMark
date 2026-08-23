import pytest

from fuckmark.sanitizer_robustness import (
    SANITIZER_VARIANT_IDS,
    evaluate_sanitizer_robustness,
    introduced_invisible_codepoint_count,
    sanitize_variant,
)


def test_sanitize_variant_nfkc_and_cf_strip_compose():
    text = "a\u200cb"
    assert sanitize_variant("raw", text) == text
    assert "\u200c" not in sanitize_variant("cf_strip", text)
    assert sanitize_variant("nfkc_cf_strip", "ﬁle") == "file"


def test_sanitize_variant_rejects_unknown_ids():
    with pytest.raises(ValueError):
        sanitize_variant("bogus", "x")


def test_introduced_invisible_codepoint_counts_only_new_marks():
    original = "plain ascii text"
    transformed = "plain\u200b ascii\u200c text"
    assert introduced_invisible_codepoint_count(original, transformed) == 2
    assert introduced_invisible_codepoint_count(transformed, transformed) == 0


def test_evaluate_sanitizer_robustness_reports_every_variant():
    entries = [
        {"source_sample_id": "s1", "text": "First sample sentence. Another sentence follows it.", "invisible_introduced": 0},
        {"source_sample_id": "s2", "text": "Second sample sentence. More content appears here.", "invisible_introduced": 1},
    ]
    report = evaluate_sanitizer_robustness(
        condition_id="unit",
        arm="visible-only",
        entries=entries,
        scorer=lambda text: 0.6 if "s1" in text else 0.4,
        threshold=0.5570987654320988,
    )
    assert len(report.rows) == 2
    for row in report.rows:
        assert tuple(variant.variant_id for variant in row.variants) == SANITIZER_VARIANT_IDS
    summary = report.summaries[0]
    assert summary.row_count == 2
    assert summary.detected_per_variant[0] >= 0
    raw_scores = {row.source_sample_id: row.variants[0].score for row in report.rows}
    assert raw_scores is not None
    assert report.detector_access_observed is False
    assert report.secret_access_observed is False


def test_evaluate_sanitizer_robustness_records_scoring_errors():
    def broken_scorer(text):
        raise RuntimeError("detector unavailable")

    report = evaluate_sanitizer_robustness(
        condition_id="unit-error",
        arm="arm",
        entries=[{"source_sample_id": "s1", "text": "Text that cannot be scored.", "invisible_introduced": 0}],
        scorer=broken_scorer,
        threshold=0.5,
    )
    row = report.rows[0]
    assert all(variant.error == "RuntimeError" for variant in row.variants)
    assert all(variant.score is None for variant in row.variants)
    summary = report.summaries[0]
    assert summary.error_per_variant == (1, 1, 1, 1)
