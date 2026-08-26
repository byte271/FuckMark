from __future__ import annotations

import os
import platform
import re
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..cli import process_text
from ..experiments.cycle6_confirmation import CYCLE6_THRESHOLD
from ..hashing import sha256_json, sha256_text
from ..product.carrier_invariants import validate_product_carrier_invariants
from ..product.domain import is_supported_product_domain_v1
from ..product.invariants import validate_user_visible_invariants
from ..product.roundtrip import display_column_width, nfc_normalize, roundtrip_report
from ..product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from ..sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters
from ..transforms.cycle7_quote_policy import PRODUCT_VISIBLE_CARRIER_QUOTE_POLICY_ID
from ..transforms.protected import ProtectedSpanExtractor
from ..transforms.registry import historical_visible_edit_transform_registry, release_transform_registry
from ..transforms.schema import InvariantStatus, ProtectedSpanKind
from ..cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from .benchmark_render import clipboard_roundtrip, compare_chrome_surface, compare_pre_payload, xclip_available
from .compare import CYCLE8_BENCHMARK_ARM_IDS, CYCLE8_U034F_LETTER_ARM_ID
from .registry import apply_all_candidates, cycle8_letter_carrier_registry, cycle8_space_carrier_registry
from .sanitize import CYCLE8_SCALE_SANITIZER_VARIANT_IDS, sanitize_cycle8_scale_variant
from .tokenizer_screen import load_gpt2_encoder, resynchronization_metrics
from .unicode_meta import is_default_ignorable_v1


CYCLE8_BENCHMARK_VERSION = "cycle8-letter-system-benchmark-v1"
CYCLE8_BENCHMARK_STRESS_SANITIZER_IDS = ("mn_strip", "default_ignorable_strip", "nfkd")
_WORD_RE = re.compile(r"[A-Za-z]+(?:[''][A-Za-z]+)?")
_MACHINE_KINDS = frozenset(
    {
        ProtectedSpanKind.URL,
        ProtectedSpanKind.EMAIL,
        ProtectedSpanKind.IPV4,
        ProtectedSpanKind.IPV6,
        ProtectedSpanKind.NUMBER,
        ProtectedSpanKind.DATE,
        ProtectedSpanKind.CODE,
        ProtectedSpanKind.MARKDOWN_DESTINATION,
        ProtectedSpanKind.POSIX_PATH,
        ProtectedSpanKind.WINDOWS_PATH,
        ProtectedSpanKind.CLI_FLAG,
        ProtectedSpanKind.IDENTIFIER,
    }
)
_RENDER_FIXTURE_IDS = ("short_paragraph", "quote_heavy")


def benchmark_fixtures() -> tuple[tuple[str, str, str], ...]:
    long_body = (
        "The researchers cannot continue until they do not miss the proof of concept. "
        "Keep every visible word, space, and newline exactly as written. "
    ) * 4
    return (
        ("general_explanatory", "general_explanatory", "Invisible carriers must leave the visible English paragraph unchanged while remaining detector-blind."),
        ("technical_explanation", "technical_explanation", "The scheduler selects non-overlapping insertion sites after ASCII letters and fail-closes when a protected span would change."),
        ("conversational_prose", "conversational_prose", "Look, I do not agree that we should rewrite the sentence. We cannot pretend a contraction is invisible."),
        ("structured_instructional", "structured_instructional", "First, keep the visible text. Second, insert only an approved carrier. Third, refuse any site that would change a URL."),
        ("narrative_prose", "narrative_prose", "She said she would never wait by the river, and he did not answer until the lantern went out."),
        ("short_paragraph", "short_paragraph", "I do not agree."),
        ("sparse_short", "short_paragraph", "OK."),
        ("long_paragraph", "long_paragraph", long_body.strip()),
        ("punctuation_heavy", "punctuation_heavy", "Wait -- we cannot continue: don't stop; (really) we won't, will we? End."),
        ("quote_heavy", "quote_heavy", 'He answered, "They are not finished and we do not agree." Then he left.'),
        ("machine_url", "machine_sensitive", "See https://example.com/do-not-touch and continue the notes."),
        ("machine_email", "machine_sensitive", "Write to docs@example.com if you do not agree with the protocol."),
        ("machine_path", "machine_sensitive", "The log is at /tmp/foo.txt and must not be rewritten by the carrier."),
        ("machine_code", "machine_sensitive", "Use `do_not_touch()` and keep PATH=/usr/bin exact in the snippet."),
        ("machine_shell", "machine_sensitive", "Run echo hello-world if you do not agree with the notes."),
        ("machine_numbers", "machine_sensitive", "Invoice 12345 is due on 2026-08-26 for 12.50 percent of the total."),
        ("machine_markdown", "machine_sensitive", "Read [the contract](https://example.com/do-not-touch) before you continue."),
        ("machine_hash", "machine_sensitive", "Digest sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef is fixed."),
        ("mixed_protected", "machine_sensitive", 'Email docs@example.com, visit https://example.com/a, and keep "do not agree" quoted.'),
        ("newline_paragraphs", "newline_paragraphs", "I do not agree.\nWe cannot continue.\nKeep both line breaks."),
        ("failclosed_latin1_source", "failclosed", "I do not agree with the naive cafe test."),
        ("failclosed_non_ascii", "failclosed", "I do not agree " + chr(0x00E9) + "."),
    )


def strip_nonspacing_marks(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return "".join(character for character in text if unicodedata.category(character) != "Mn")


def strip_default_ignorable(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return "".join(character for character in text if not is_default_ignorable_v1(ord(character)))


def sanitize_benchmark_stress(variant_id: str, text: str) -> str:
    if variant_id == "mn_strip":
        return strip_nonspacing_marks(text)
    if variant_id == "default_ignorable_strip":
        return strip_default_ignorable(text)
    if variant_id == "nfkd":
        return unicodedata.normalize("NFKD", text)
    raise ValueError("unknown benchmark stress sanitizer")


def apply_historical_visible_edit(text: str) -> str:
    registry = historical_visible_edit_transform_registry()
    enumeration = registry.enumerate(text)
    selected: list[str] = []
    occupied_until = 0
    for candidate in enumeration.candidates:
        if candidate.start < occupied_until:
            continue
        selected.append(candidate.candidate_id)
        occupied_until = candidate.end
        if len(selected) >= 32:
            break
    if not selected:
        return text
    try:
        return registry.apply(enumeration, tuple(selected)).output_text
    except ValueError:
        return text


def cycle6_style_visible_spaces(text: str) -> str:
    return text.replace(" ", "  ")


def _visible_word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    var_x = sum((value - mean_x) ** 2 for value in xs)
    var_y = sum((value - mean_y) ** 2 for value in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    cov = sum((left - mean_x) * (right - mean_y) for left, right in zip(xs, ys))
    return cov / (var_x * var_y) ** 0.5


def _quantile(ordered: Sequence[float], q: float) -> float | None:
    if not ordered:
        return None
    if q <= 0:
        return float(ordered[0])
    if q >= 1:
        return float(ordered[-1])
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    frac = position - low
    return float(ordered[low]) * (1.0 - frac) + float(ordered[high]) * frac


def _score_distribution(values: Sequence[float], *, threshold: float) -> dict[str, object]:
    if not values:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "stdev": None,
            "min": None,
            "max": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "threshold": threshold,
            "max_gap_below_threshold": None,
        }
    ordered = tuple(sorted(float(value) for value in values))
    mean = statistics.fmean(ordered)
    stdev = statistics.pstdev(ordered) if len(ordered) > 1 else 0.0
    maximum = ordered[-1]
    return {
        "n": len(ordered),
        "mean": mean,
        "median": _quantile(ordered, 0.5),
        "stdev": stdev,
        "min": ordered[0],
        "max": maximum,
        "p10": _quantile(ordered, 0.10),
        "p25": _quantile(ordered, 0.25),
        "p75": _quantile(ordered, 0.75),
        "p90": _quantile(ordered, 0.90),
        "p95": _quantile(ordered, 0.95),
        "threshold": threshold,
        "max_gap_below_threshold": threshold - maximum,
    }


def enrich_detector_artifact(artifact: Mapping[str, object], *, transformed_arm_id: str) -> dict[str, object]:
    threshold = float(artifact["threshold"])
    scored_rows = tuple(artifact["scored_rows"])
    arm_rows = tuple(row for row in scored_rows if row["arm_id"] == transformed_arm_id)
    watermarked = tuple(row for row in arm_rows if row["label"] == "watermarked")
    unwatermarked = tuple(row for row in arm_rows if row["label"] == "unwatermarked")
    raw_wm_scores = tuple(float(row["sanitizers"]["raw"]["score"]) for row in watermarked)
    raw_uw_scores = tuple(float(row["sanitizers"]["raw"]["score"]) for row in unwatermarked)
    closest = None
    if watermarked:
        closest_row = max(watermarked, key=lambda row: float(row["sanitizers"]["raw"]["score"]))
        closest = {
            "sample_id": closest_row["sample_id"],
            "domain": closest_row["domain"],
            "score": float(closest_row["sanitizers"]["raw"]["score"]),
            "detected": bool(closest_row["sanitizers"]["raw"]["detected"]),
            "gap_below_threshold": threshold - float(closest_row["sanitizers"]["raw"]["score"]),
            "inserted_count": int(closest_row["geometry"]["inserted_count"]),
        }
    domains: dict[str, dict[str, object]] = {}
    for row in watermarked:
        domain = str(row["domain"])
        bucket = domains.setdefault(
            domain,
            {"watermarked_n": 0, "raw_detected": 0, "scores": []},
        )
        bucket["watermarked_n"] = int(bucket["watermarked_n"]) + 1
        bucket["raw_detected"] = int(bucket["raw_detected"]) + int(bool(row["sanitizers"]["raw"]["detected"]))
        scores = list(bucket["scores"])
        scores.append(float(row["sanitizers"]["raw"]["score"]))
        bucket["scores"] = scores
    domain_rows = []
    for domain, bucket in sorted(domains.items()):
        scores = tuple(float(value) for value in bucket["scores"])
        domain_rows.append(
            {
                "domain": domain,
                "watermarked_n": bucket["watermarked_n"],
                "raw_detected": bucket["raw_detected"],
                "scores": _score_distribution(scores, threshold=threshold),
            }
        )
    tokenizer_deltas = []
    tokenizer_original = []
    tokenizer_transformed = []
    inserted_wm = []
    for row in arm_rows:
        tokenizer = row["geometry"].get("tokenizer")
        if isinstance(tokenizer, Mapping) and tokenizer.get("token_count_delta") is not None:
            tokenizer_deltas.append(int(tokenizer["token_count_delta"]))
            tokenizer_original.append(int(tokenizer["original_token_count"]))
            tokenizer_transformed.append(int(tokenizer["transformed_token_count"]))
    for row in watermarked:
        inserted_wm.append(int(row["geometry"]["inserted_count"]))
    cap_binds = sum(1 for value in inserted_wm if value >= 192)
    payload = {
        "algorithm_version": CYCLE8_BENCHMARK_VERSION,
        "seed_base": artifact["seed_base"],
        "pair_count": artifact["pair_count"],
        "topic": artifact.get("topic"),
        "artifact_hash": artifact.get("artifact_hash"),
        "arm_id": transformed_arm_id,
        "model": artifact.get("model"),
        "model_revision": artifact.get("model_revision"),
        "threshold": threshold,
        "detector_access_used_for_selection": artifact.get("detector_access_used_for_selection"),
        "pristine_watermarked_detected": sum(bool(row["pristine_detected"]) for row in watermarked),
        "pristine_unwatermarked_detected": sum(bool(row["pristine_detected"]) for row in unwatermarked),
        "raw_watermarked_detected": sum(bool(row["sanitizers"]["raw"]["detected"]) for row in watermarked),
        "raw_unwatermarked_detected": sum(bool(row["sanitizers"]["raw"]["detected"]) for row in unwatermarked),
        "raw_watermarked_scores": _score_distribution(raw_wm_scores, threshold=threshold),
        "raw_unwatermarked_scores": _score_distribution(raw_uw_scores, threshold=threshold),
        "closest_watermarked_row": closest,
        "domains": domain_rows,
        "visible_pass": sum(bool(row["geometry"]["visible_ok"]) for row in arm_rows),
        "visible_total": len(arm_rows),
        "inserted_count_mean": (
            sum(int(row["geometry"]["inserted_count"]) for row in arm_rows) / len(arm_rows) if arm_rows else 0
        ),
        "utf8_overhead_mean": (
            sum(int(row["geometry"]["utf8_overhead"]) for row in arm_rows) / len(arm_rows) if arm_rows else 0
        ),
        "token_count_delta_mean": (sum(tokenizer_deltas) / len(tokenizer_deltas) if tokenizer_deltas else None),
        "token_count_delta_max": (max(tokenizer_deltas) if tokenizer_deltas else None),
        "original_token_count_mean": (
            sum(tokenizer_original) / len(tokenizer_original) if tokenizer_original else None
        ),
        "transformed_token_count_mean": (
            sum(tokenizer_transformed) / len(tokenizer_transformed) if tokenizer_transformed else None
        ),
        "transformed_token_count_max": (max(tokenizer_transformed) if tokenizer_transformed else None),
        "gpt2_context_limit": 1024,
        "approaches_gpt2_context_limit": (
            max(tokenizer_transformed) >= 960 if tokenizer_transformed else None
        ),
        "cap_bind_watermarked": cap_binds,
        "inserted_count_vs_score_pearson": _pearson(
            tuple(float(value) for value in inserted_wm),
            raw_wm_scores,
        ),
        "token_delta_vs_score_pearson": _pearson(
            tuple(float(row["geometry"]["tokenizer"]["token_count_delta"]) for row in watermarked if isinstance(row["geometry"].get("tokenizer"), Mapping)),
            tuple(float(row["sanitizers"]["raw"]["score"]) for row in watermarked if isinstance(row["geometry"].get("tokenizer"), Mapping)),
        ),
        "sanitizers": {},
    }
    sanitizer_ids = tuple(artifact["sanitizer_ids"])
    sanitizers = {}
    for variant in sanitizer_ids:
        sanitizers[variant] = {
            "watermarked_detected": sum(bool(row["sanitizers"][variant]["detected"]) for row in watermarked),
            "unwatermarked_detected": sum(bool(row["sanitizers"][variant]["detected"]) for row in unwatermarked),
            "equals_transformed_rate": (
                f"{sum(bool(row['sanitizers'][variant]['equals_transformed']) for row in arm_rows)}/{len(arm_rows)}"
            ),
            "equals_source_rate": (
                f"{sum(bool(row['sanitizers'][variant]['equals_source']) for row in arm_rows)}/{len(arm_rows)}"
            ),
        }
    payload["sanitizers"] = sanitizers
    return {**payload, "stats_hash": sha256_json(payload)}


def _visible_contract(original: str, transformed: str, approved: tuple[int, ...]) -> dict[str, object]:
    projected = project_visible_v1(transformed, approved)
    reasons: list[str] = []
    if projected != original:
        reasons.append("visible_projection_mismatch")
    if not is_carrier_insertion_v1(original, transformed, approved):
        reasons.append("not_carrier_insertion")
    if original.replace(" ", "") != projected.replace(" ", "") and "visible_projection_mismatch" not in reasons:
        reasons.append("visible_characters_changed")
    if original.count(" ") != projected.count(" "):
        reasons.append("visible_spaces_changed")
    if original.count("\n") != projected.count("\n"):
        reasons.append("line_breaks_changed")
    punctuation_original = "".join(ch for ch in original if not ch.isalnum() and ch not in " \t\r\n")
    punctuation_projected = "".join(ch for ch in projected if not ch.isalnum() and ch not in " \t\r\n")
    if punctuation_original != punctuation_projected:
        reasons.append("punctuation_changed")
    if "".join(ch for ch in original if not ch.isspace()) != "".join(ch for ch in projected if not ch.isspace()):
        reasons.append("character_order_changed")
    product = validate_user_visible_invariants(original, transformed, approved)
    return {
        "visible_ok": not reasons and product.status is InvariantStatus.PASS,
        "reasons": tuple(reasons),
        "product_invariant": product.status.value,
        "display_column_width_equal": display_column_width(original) == display_column_width(transformed),
        "newline_count_equal": original.count("\n") == transformed.count("\n"),
        "ascii_space_count_equal": original.count(" ") == transformed.count(" "),
    }


def _protected_report(original: str, transformed: str) -> dict[str, object]:
    extractor = ProtectedSpanExtractor()
    original_spans = extractor.extract(original).spans
    failures: list[dict[str, object]] = []
    checked = 0
    for span in original_spans:
        if not any(kind in _MACHINE_KINDS for kind in span.kinds):
            continue
        checked += 1
        fragment = span.exact_text
        if fragment not in transformed:
            failures.append(
                {
                    "kinds": tuple(kind.value for kind in span.kinds),
                    "start": span.start,
                    "end": span.end,
                    "fragment_sha256": sha256_text(fragment),
                }
            )
    return {
        "checked_spans": checked,
        "intact_spans": checked - len(failures),
        "failures": tuple(failures),
        "pass": not failures,
    }


def measure_fixture_row(fixture_id: str, category: str, source: str, encoder=None) -> dict[str, object]:
    supported = is_supported_product_domain_v1(source)
    letter_registry = cycle8_letter_carrier_registry(0x034F)
    expensive = len(source) > 500
    if supported:
        letter_text = apply_all_candidates(letter_registry, source)
        space_text = apply_all_candidates(cycle8_space_carrier_registry(0x034F), source)
        u200c_text = (
            source if expensive else apply_all_candidates(cycle8_space_carrier_registry(0x200C), source)
        )
    else:
        letter_text = source
        space_text = source
        u200c_text = source
    historical = source if (not supported or expensive) else apply_historical_visible_edit(source)
    spaced = cycle6_style_visible_spaces(source) if supported else source
    approved = (0x034F,)
    letter_visible = _visible_contract(source, letter_text, approved)
    letter_protected = _protected_report(source, letter_text)
    letter_product = validate_product_carrier_invariants(
        source,
        letter_text,
        approved_carriers=approved,
        include_quotations=False,
    ) if supported else None
    frozen_hard_pass = None
    if supported:
        from ..transforms.hard_invariants import validate_hard_invariants

        frozen_hard_pass = validate_hard_invariants(source, letter_text).status is InvariantStatus.PASS
    sanitizers = {}
    for variant in CYCLE8_SCALE_SANITIZER_VARIANT_IDS:
        cleaned = sanitize_cycle8_scale_variant(variant, letter_text)
        sanitizers[variant] = {
            "equals_source": cleaned == source,
            "equals_transformed": cleaned == letter_text,
            "visible_ok": is_carrier_insertion_v1(source, cleaned, approved) if supported else cleaned == source,
            "carrier_survives": letter_text.count("\u034f") > 0 and cleaned.count("\u034f") == letter_text.count("\u034f"),
        }
    stress = {}
    for variant in CYCLE8_BENCHMARK_STRESS_SANITIZER_IDS:
        cleaned = sanitize_benchmark_stress(variant, letter_text)
        stress[variant] = {
            "equals_source": cleaned == source,
            "equals_transformed": cleaned == letter_text,
            "carrier_survives": letter_text.count("\u034f") > 0 and cleaned.count("\u034f") == letter_text.count("\u034f"),
            "visible_projection_equals_source": project_visible_v1(cleaned, approved) == source,
        }
    visible_words = _visible_word_count(source)
    visible_chars = len(source)
    inserted = letter_text.count("\u034f") - source.count("\u034f")
    utf8_overhead = len(letter_text.encode("utf-8")) - len(source.encode("utf-8"))
    tokenizer = None
    if encoder is not None and supported and visible_chars <= 800:
        tokenizer = resynchronization_metrics(encoder(source), encoder(letter_text))
    search_break = "do not" in source and "do not" not in letter_text
    return {
        "fixture_id": fixture_id,
        "category": category,
        "supported_product_domain": supported,
        "source_sha256": sha256_text(source),
        "source_chars": visible_chars,
        "source_visible_words": visible_words,
        "letter": {
            "transformed_sha256": sha256_text(letter_text),
            "inserted_count": inserted,
            "utf8_overhead": utf8_overhead,
            "inserted_per_visible_word": (inserted / visible_words) if visible_words else None,
            "inserted_per_visible_char": (inserted / visible_chars) if visible_chars else None,
            "percent_utf8_growth": (utf8_overhead / max(len(source.encode("utf-8")), 1)) * 100.0,
            "visible": letter_visible,
            "protected": letter_protected,
            "product_carrier_invariant": None if letter_product is None else letter_product.status.value,
            "frozen_hard_invariant_pass": frozen_hard_pass,
            "quote_policy_id": letter_registry.quote_policy_id,
            "max_selected": letter_registry.max_selected,
            "search_literal_do_not_breaks": search_break,
            "tokenizer": tokenizer,
            "fail_closed_identity": supported and letter_text == source and inserted == 0 and visible_chars >= 12,
        },
        "baselines": {
            "identity_equals_source": True,
            "space_x1_visible_ok": is_carrier_insertion_v1(source, space_text, approved) if supported else True,
            "space_x1_inserted": space_text.count("\u034f") - source.count("\u034f") if supported else 0,
            "u200c_measured": supported and not expensive,
            "u200c_visible_ok": (
                True
                if not supported or expensive
                else is_carrier_insertion_v1(source, u200c_text, (0x200C,))
            ),
            "u200c_cf_strip_equals_source": (
                True if not supported or expensive else strip_unicode_format_characters(u200c_text) == source
            ),
            "historical_visible_edit_measured": supported and not expensive,
            "historical_visible_edit_equals_source": historical == source,
            "historical_visible_edit_product_disqualified": historical != source,
            "cycle6_spacing_equals_source": spaced == source,
            "cycle6_spacing_product_disqualified": spaced != source,
            "cli_process_text_equals_source": process_text(source) == source,
        },
        "sanitizers": sanitizers,
        "stress_sanitizers": stress,
        "roundtrip": roundtrip_report(source, letter_text, approved) if supported else None,
    }


def run_determinism(source: str, repeats: int = 5) -> dict[str, object]:
    registry = cycle8_letter_carrier_registry(0x034F)
    hashes = []
    for _ in range(repeats):
        hashes.append(sha256_text(apply_all_candidates(registry, source)))
    return {
        "repeats": repeats,
        "unique_hashes": len(set(hashes)),
        "deterministic": len(set(hashes)) == 1,
        "output_sha256": hashes[0] if hashes else None,
    }


def run_performance() -> dict[str, object]:
    registry = cycle8_letter_carrier_registry(0x034F)
    cases = {
        "short": "I do not agree.",
        "medium": ("The researchers cannot continue until they do not miss the proof of concept. ") * 4,
        "long": ("The researchers cannot continue until they do not miss the proof of concept. ") * 8,
    }

    def _bench(text: str, loops: int) -> dict[str, object]:
        apply_all_candidates(registry, text)
        started = time.perf_counter()
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        for _ in range(loops):
            apply_all_candidates(registry, text)
        elapsed = time.perf_counter() - started
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mean_ms = (elapsed / loops) * 1000.0
        chars = len(text)
        enum_started = time.perf_counter()
        registry.enumerate(text)
        enum_elapsed = time.perf_counter() - enum_started
        cli_started = time.perf_counter()
        process_text(text)
        cli_elapsed = time.perf_counter() - cli_started
        return {
            "chars": chars,
            "loops": loops,
            "transform_mean_ms": mean_ms,
            "transform_chars_per_s": chars / (elapsed / loops) if elapsed else None,
            "enumerate_mean_ms": enum_elapsed * 1000.0,
            "cli_identity_mean_ms": cli_elapsed * 1000.0,
            "ru_maxrss_kb": max(rss_before, rss_after),
        }

    return {
        "algorithm_version": CYCLE8_BENCHMARK_VERSION,
        "short": _bench(cases["short"], 12),
        "medium": _bench(cases["medium"], 2),
        "long": _bench(cases["long"], 1),
        "host": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


def run_platform_roundtrips(source: str, transformed: str) -> dict[str, object]:
    utf8_ok = transformed.encode("utf-8").decode("utf-8") == transformed
    with tempfile.TemporaryDirectory(prefix="fuckmark-bench-io-") as directory:
        path = Path(directory) / "sample.txt"
        path.write_text(transformed, encoding="utf-8", newline="\n")
        file_read = path.read_text(encoding="utf-8")
        try:
            pipe = subprocess.run(
                [sys.executable, "-m", "fuckmark.cli", "--stdin", "-q"],
                input=transformed,
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            cli_out = pipe.stdout
            cli_code = pipe.returncode
        except subprocess.TimeoutExpired:
            cli_out = ""
            cli_code = 124
        shell = subprocess.run(["cat"], input=transformed, capture_output=True, text=True, check=True)
        vim_path = Path(directory) / "vim.txt"
        vim_default_path = Path(directory) / "vim-default.txt"
        vim_path.write_text(transformed, encoding="utf-8", newline="\n")
        vim_default_path.write_text(transformed, encoding="utf-8", newline="\n")
        vim = shutil_which_vim()
        vim_text = None
        vim_status = "UNKNOWN"
        vim_default_text = None
        vim_default_status = "UNKNOWN"
        if vim is not None:
            completed = subprocess.run(
                [vim, "-n", "-u", "NONE", "--not-a-term", "-c", "set binary noeol", "-c", "wq", str(vim_path)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if completed.returncode == 0:
                vim_text = vim_path.read_text(encoding="utf-8")
                vim_status = "VERIFIED" if vim_text == transformed else "REJECTED"
            else:
                vim_status = "UNKNOWN"
            default = subprocess.run(
                [vim, "-n", "-u", "NONE", "--not-a-term", "-c", "wq", str(vim_default_path)],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if default.returncode == 0:
                vim_default_text = vim_default_path.read_text(encoding="utf-8")
                vim_default_status = "VERIFIED" if vim_default_text == transformed else "REJECTED"
            else:
                vim_default_status = "UNKNOWN"
    clip = clipboard_roundtrip(transformed)
    clip_status = "UNKNOWN" if clip is None else ("VERIFIED" if clip == transformed else "REJECTED")
    return {
        "utf8_file": {
            "carrier_survives": file_read == transformed,
            "visible_projection_preserved": project_visible_v1(file_read, (0x034F,)) == source,
            "normalization_occurred": file_read != transformed,
            "status": "VERIFIED" if file_read == transformed else "REJECTED",
        },
        "cli_stdin": {
            "exit_code": cli_code,
            "carrier_survives": cli_out == transformed,
            "visible_projection_preserved": project_visible_v1(cli_out, (0x034F,)) == source,
            "normalization_occurred": cli_out != transformed,
            "status": "VERIFIED" if cli_out == transformed and cli_code == 0 else "REJECTED",
        },
        "shell_pipe_cat": {
            "carrier_survives": shell.stdout == transformed,
            "visible_projection_preserved": project_visible_v1(shell.stdout, (0x034F,)) == source,
            "normalization_occurred": shell.stdout != transformed,
            "status": "VERIFIED" if shell.stdout == transformed else "REJECTED",
        },
        "clipboard_xclip": {
            "available": xclip_available(),
            "carrier_survives": None if clip is None else clip == transformed,
            "visible_projection_preserved": None if clip is None else project_visible_v1(clip, (0x034F,)) == source,
            "normalization_occurred": None if clip is None else clip != transformed,
            "status": clip_status,
        },
        "vim_binary_noeol": {
            "status": vim_status,
            "carrier_survives": None if vim_text is None else vim_text == transformed,
            "visible_projection_preserved": None if vim_text is None else project_visible_v1(vim_text, (0x034F,)) == source,
            "normalization_occurred": None if vim_text is None else vim_text != transformed,
        },
        "vim_default_save": {
            "status": vim_default_status,
            "carrier_survives": None if vim_default_text is None else vim_default_text.count("\u034f") == transformed.count("\u034f"),
            "visible_projection_preserved": None if vim_default_text is None else project_visible_v1(vim_default_text, (0x034F,)) == source,
            "normalization_occurred": None if vim_default_text is None else vim_default_text != transformed,
            "detail": "ordinary vim wq may append a trailing newline",
        },
        "latin1": {
            "carrier_survives": False,
            "status": "REJECTED",
            "detail": "U+034F cannot roundtrip through latin-1",
        },
        "nfc": {
            "carrier_survives": nfc_normalize(transformed) == transformed,
            "visible_projection_preserved": project_visible_v1(nfc_normalize(transformed), (0x034F,)) == source,
            "normalization_occurred": nfc_normalize(transformed) != transformed,
            "status": "VERIFIED" if nfc_normalize(transformed) == transformed else "REJECTED",
        },
        "nfkc": {
            "carrier_survives": nfkc_normalize(transformed) == transformed,
            "visible_projection_preserved": project_visible_v1(nfkc_normalize(transformed), (0x034F,)) == source,
            "normalization_occurred": nfkc_normalize(transformed) != transformed,
            "status": "VERIFIED" if nfkc_normalize(transformed) == transformed else "REJECTED",
        },
        "cf_strip": {
            "carrier_survives": strip_unicode_format_characters(transformed) == transformed,
            "visible_projection_preserved": project_visible_v1(strip_unicode_format_characters(transformed), (0x034F,)) == source,
            "normalization_occurred": strip_unicode_format_characters(transformed) != transformed,
            "status": "VERIFIED" if strip_unicode_format_characters(transformed) == transformed else "REJECTED",
        },
        "ws_collapse": {
            "carrier_survives": collapse_horizontal_ascii_whitespace(transformed) == transformed,
            "visible_projection_preserved": project_visible_v1(collapse_horizontal_ascii_whitespace(transformed), (0x034F,)) == source,
            "normalization_occurred": collapse_horizontal_ascii_whitespace(transformed) != transformed,
            "status": "VERIFIED" if collapse_horizontal_ascii_whitespace(transformed) == transformed else "REJECTED",
        },
        "utf8_in_memory": {"carrier_survives": utf8_ok, "status": "VERIFIED" if utf8_ok else "REJECTED"},
    }


def shutil_which_vim() -> str | None:
    import shutil

    return shutil.which("vim")


def _tiktoken_version() -> str | None:
    try:
        import tiktoken
    except ImportError:
        return None
    return getattr(tiktoken, "__version__", None)


def run_rendering(source: str, transformed: str, *, extra_surfaces: bool) -> dict[str, object]:
    pre = compare_pre_payload(source, transformed)
    payload = {
        "chromium_pre": pre,
        "webkit_safari": {"status": "UNKNOWN", "detail": "Safari is not available on this Linux host"},
        "terminal_pixels": {"status": "UNKNOWN", "detail": "terminal pixel capture is not instrumented"},
        "terminal_display_width": {
            "status": "VERIFIED" if display_column_width(source) == display_column_width(transformed) else "REJECTED",
            "equal": display_column_width(source) == display_column_width(transformed),
        },
    }
    if extra_surfaces:
        payload["chromium_textarea"] = compare_chrome_surface(source, transformed, "textarea")
        payload["chromium_contenteditable"] = compare_chrome_surface(source, transformed, "contenteditable")
    else:
        payload["chromium_textarea"] = {"status": "UNKNOWN", "detail": "not measured on this fixture"}
        payload["chromium_contenteditable"] = {"status": "UNKNOWN", "detail": "not measured on this fixture"}
    return payload


def environment_payload() -> dict[str, object]:
    import torch

    payload = {
        "algorithm_version": CYCLE8_BENCHMARK_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "torch": getattr(torch, "__version__", None),
        "torch_cuda": bool(torch.cuda.is_available()) if hasattr(torch, "cuda") else False,
        "threshold": CYCLE6_THRESHOLD,
        "model": "openai-community/gpt2",
        "model_revision": "607a30d783dfa663caf39e06633721c8d4cfcd7e",
        "comparison": "score >= threshold",
        "fpr_assumption": "frozen Cycle 6 GPT-2 / Hugging Face SynthID Weighted Mean threshold 0.5570987654320988",
        "release_cli_algorithm_version": "release-cli-v4",
        "letter_quote_policy_id": PRODUCT_VISIBLE_CARRIER_QUOTE_POLICY_ID,
        "release_registry_empty": release_transform_registry().rules == (),
        "benchmark_arm_ids": CYCLE8_BENCHMARK_ARM_IDS,
        "tiktoken": _tiktoken_version(),
        "hostname": platform.node(),
    }
    return {**payload, "environment_hash": sha256_json(payload)}


def run_local_system_benchmark(*, include_render: bool = True) -> dict[str, object]:
    encoder = load_gpt2_encoder()
    rows = []
    visible_pass = 0
    visible_total = 0
    visible_failures: list[dict[str, object]] = []
    protected_pass = 0
    protected_total = 0
    render_rows = []
    for fixture_id, category, source in benchmark_fixtures():
        row = measure_fixture_row(fixture_id, category, source, encoder=encoder)
        rows.append(row)
        if row["supported_product_domain"]:
            visible_total += 1
            if row["letter"]["visible"]["visible_ok"]:
                visible_pass += 1
            else:
                visible_failures.append(
                    {
                        "fixture_id": fixture_id,
                        "reasons": row["letter"]["visible"]["reasons"],
                    }
                )
            protected_total += 1
            if row["letter"]["protected"]["pass"]:
                protected_pass += 1
        if include_render and fixture_id in _RENDER_FIXTURE_IDS and row["supported_product_domain"]:
            transformed = apply_all_candidates(cycle8_letter_carrier_registry(0x034F), source)
            render_rows.append(
                {
                    "fixture_id": fixture_id,
                    "render": run_rendering(source, transformed, extra_surfaces=fixture_id == "short_paragraph"),
                }
            )
    short_source = "I do not agree."
    short_transformed = apply_all_candidates(cycle8_letter_carrier_registry(0x034F), short_source)
    inserted_rows = [row for row in rows if row["letter"]["inserted_count"] > 0]
    mn_kills = all(not row["stress_sanitizers"]["mn_strip"]["carrier_survives"] for row in inserted_rows)
    di_kills = all(
        not row["stress_sanitizers"]["default_ignorable_strip"]["carrier_survives"] for row in inserted_rows
    )
    cf_survives = all(row["sanitizers"]["cf_strip"]["carrier_survives"] for row in inserted_rows)
    search_breaks = [
        row["fixture_id"] for row in rows if row["letter"].get("search_literal_do_not_breaks")
    ]
    fail_closed = [
        row["fixture_id"]
        for row in rows
        if (not row["supported_product_domain"]) or row["letter"].get("fail_closed_identity")
    ]
    payload = {
        "algorithm_version": CYCLE8_BENCHMARK_VERSION,
        "mechanism_id": CYCLE8_U034F_LETTER_ARM_ID,
        "visible_pass": visible_pass,
        "visible_total": visible_total,
        "visible_pass_rate": f"{visible_pass}/{visible_total}",
        "visible_failures": visible_failures,
        "protected_pass": protected_pass,
        "protected_total": protected_total,
        "protected_pass_rate": f"{protected_pass}/{protected_total}",
        "release_registry_empty": release_transform_registry().rules == (),
        "cli_identity": process_text("I do not agree.") == "I do not agree.",
        "determinism": run_determinism(short_source),
        "performance": run_performance(),
        "roundtrips": run_platform_roundtrips(short_source, short_transformed),
        "rendering": render_rows,
        "stress": {
            "mn_strip_removes_carrier": mn_kills,
            "default_ignorable_strip_removes_carrier": di_kills,
            "cf_strip_preserves_carrier": cf_survives,
            "search_literal_do_not_breaks": search_breaks,
            "fail_closed_fixture_ids": fail_closed,
        },
        "fixtures": rows,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}
