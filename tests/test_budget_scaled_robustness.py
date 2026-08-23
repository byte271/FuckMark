from __future__ import annotations

from types import SimpleNamespace

from fuckmark.corpus import CorpusDomain, CorpusSplit, WatermarkLabel
from fuckmark.experiments.effectiveness_plan import build_key_blind_high_coverage_plan
from fuckmark.hashing import sha256_text
from fuckmark.tiny_dev_budget_scaled_robustness import (
    _cf_stripped,
    _forbidden_codepoints,
    build_budget_scaled_robustness_report,
)
from fuckmark.transforms import key_blind_full_pool_coverage_profile


class FakeTokenizer:
    def __call__(
        self,
        text: str,
        *,
        add_special_tokens: bool,
        return_offsets_mapping: bool = False,
    ) -> dict[str, object]:
        assert add_special_tokens is False
        ids = [index + 1 for index in range(len(text))]
        value: dict[str, object] = {"input_ids": ids}
        if return_offsets_mapping:
            value["offset_mapping"] = [(index, index + 1) for index in range(len(text))]
        return value


def _sample(sample_id: str, label: WatermarkLabel, text: str, identity_hash: str):
    token_ids = tuple(index + 1 for index in range(len(text)))
    return SimpleNamespace(
        sample_id=sample_id,
        split=CorpusSplit.ATTACK_DEVELOPMENT,
        label=label,
        prompt_family_id=f"prompt-{sample_id}",
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        text=text,
        text_sha256=sha256_text(text),
        text_only_tokens=SimpleNamespace(token_ids=token_ids),
        model=SimpleNamespace(identity_hash=identity_hash, eos_token_id=50256),
    )


def _corpus(text: str, salt: str):
    identity_hash = sha256_text("fake-tokenizer")
    samples = (
        _sample(f"negative-{salt}", WatermarkLabel.UNWATERMARKED, text, identity_hash),
        _sample(f"positive-{salt}", WatermarkLabel.WATERMARKED, text, identity_hash),
    )
    return SimpleNamespace(
        artifact_hash=sha256_text(f"fake-corpus-{salt}"),
        model_identity_hash=identity_hash,
        manifest=SimpleNamespace(samples=samples, manifest_hash=sha256_text("fake-manifest")),
    )


def test_forbidden_codepoint_audit_detects_hidden_representation() -> None:
    clean = "plain ascii text with spaces only"
    assert _forbidden_codepoints(clean) == ()
    zero_width = "hidden" + chr(0x200C) + "join"
    combining = "combining" + chr(0x0301)
    nbsp = "nbsp" + chr(0x00A0)
    soft_hyphen = "soft" + chr(0x00AD)
    assert _forbidden_codepoints(zero_width) == ("U+200C(Cf)",)
    assert _forbidden_codepoints(combining) == ("U+0301(Mn)",)
    assert _forbidden_codepoints(nbsp) == ("U+00A0(Zs)",)
    assert _forbidden_codepoints(soft_hyphen) == ("U+00AD(Cf)",)
    assert _cf_stripped(zero_width) == "hiddenjoin"
    assert _cf_stripped(clean) == clean


def test_introduced_codepoint_gate_ignores_preexisting_source_characters() -> None:
    from fuckmark.tiny_dev_budget_scaled_robustness import (
        _introduced_forbidden_codepoints,
        _introduced_non_ascii,
        _robustness_row,
    )

    source = "source with\nnewline and " + chr(0x2019) + "curly quote"
    transformed_same = source + " and one more plain ascii word"
    assert _introduced_forbidden_codepoints(source, transformed_same) == ()
    assert _introduced_non_ascii(source, transformed_same) == ()
    transformed_hidden = transformed_same + chr(0x200B)
    assert _introduced_forbidden_codepoints(source, transformed_hidden) == ("U+200B(Cf)",)
    transformed_visible_unicode = transformed_same + chr(0x00E9)
    assert _introduced_non_ascii(source, transformed_visible_unicode) == ("U+00E9",)


def test_normalization_gate_ignores_source_instability_but_flags_introduced_instability() -> None:
    from fuckmark.tiny_dev_budget_scaled_robustness import _robustness_row

    stable_source = "plain stable ascii source text"
    stable_row = _robustness_row(stable_source, stable_source + " edited")
    assert stable_row["gates_pass"] is True
    assert stable_row["introduced_normalization_instability"] == ()
    decomposed_source = "caf" + chr(0x0065) + chr(0x0301) + " source text with several more words here"
    inherited_decomposed = _robustness_row(decomposed_source, decomposed_source + " edited")
    assert inherited_decomposed["normalization_noops"]["nfc"] is False
    assert inherited_decomposed["introduced_normalization_instability"] == ()
    assert inherited_decomposed["gates_pass"] is True
    introduced_unstable = _robustness_row(stable_source, stable_source + " caf" + chr(0x0065) + chr(0x0301))
    assert introduced_unstable["introduced_normalization_instability"] == ("nfc", "nfkc")
    assert introduced_unstable["gates_pass"] is False
    unstable_source = "caf" + chr(0x00E9) + " source text with several more words here"
    inherited_row = _robustness_row(unstable_source, unstable_source + " edited")
    assert inherited_row["normalization_noops"]["nfd"] is False
    assert inherited_row["introduced_normalization_instability"] == ()
    assert inherited_row["gates_pass"] is True


def test_robustness_report_gates_pass_on_rule_transforms() -> None:
    text = "You are not ready, and we do not stop when the system is in use."
    corpus = _corpus(text, "1")
    plan = build_key_blind_high_coverage_plan(
        corpus,
        FakeTokenizer(),
        profile=key_blind_full_pool_coverage_profile((32,)),
        source_code_commit="a" * 40,
    )
    report = build_budget_scaled_robustness_report((corpus,), (plan,))
    assert report["summary"]["row_count"] == 2
    assert report["summary"]["gate_pass_fraction"] == 1.0
    assert report["summary"]["all_normalization_stability_preserved"] is True
    assert report["summary"]["all_cf_strip_noop"] is True
    assert report["summary"]["all_introduced_codepoints_clean"] is True
    assert report["summary"]["corpus_pairwise_text_hash_overlaps"] == {}
    assert all(row["gates_pass"] for row in report["rows"])
    assert report["artifact_hash"]


def test_robustness_report_joins_plans_to_their_own_corpus_by_artifact_hash() -> None:
    identity_hash = sha256_text("fake-tokenizer")
    first_text = "You are not ready, and we do not stop when the system is in use."
    second_text = "A second corpus shares sample IDs but holds different source texts here."
    first = _corpus(first_text, "1")
    second = _corpus(second_text, "1")
    first.artifact_hash = sha256_text("corpus-a")
    second.artifact_hash = sha256_text("corpus-b")
    for corpus, text in ((first, first_text), (second, second_text)):
        for sample in corpus.manifest.samples:
            sample.text = text
            sample.text_sha256 = sha256_text(text)
    plan = build_key_blind_high_coverage_plan(
        first,
        FakeTokenizer(),
        profile=key_blind_full_pool_coverage_profile((16,)),
        source_code_commit="a" * 40,
    )
    report = build_budget_scaled_robustness_report((first, second), (plan,))
    assert all(row["corpus_artifact_hash"] == sha256_text("corpus-a") for row in report["rows"])
    assert report["summary"]["gate_pass_fraction"] == 1.0


def test_robustness_report_detects_cross_corpus_text_overlap() -> None:
    text = "Shared generation text that appears in two corpora at once."
    first = _corpus(text, "1")
    second = _corpus(text, "2")
    plan = build_key_blind_high_coverage_plan(
        first,
        FakeTokenizer(),
        profile=key_blind_full_pool_coverage_profile((16,)),
        source_code_commit="a" * 40,
    )
    report = build_budget_scaled_robustness_report((first, second), (plan,))
    assert report["summary"]["corpus_pairwise_text_hash_overlaps"] == {"0-1": 1}
