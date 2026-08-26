from __future__ import annotations

import json
from pathlib import Path

from ..cli import process_text
from ..cycle7.whitespace_collapse import collapse_horizontal_ascii_whitespace
from ..hashing import sha256_json, sha256_text
from ..product.roundtrip import nfc_normalize
from ..product.visible_projection import is_carrier_insertion_v1, project_visible_v1
from ..sanitizer_robustness import nfkc_normalize, strip_unicode_format_characters
from ..transforms.registry import release_transform_registry
from .benchmark import (
    CYCLE6_THRESHOLD,
    enrich_detector_artifact,
    environment_payload,
    run_rendering,
    strip_default_ignorable,
    strip_nonspacing_marks,
)
from .compare import CYCLE8_LETTER_ALT_ARM_ID, CYCLE8_MIX_ARM_IDS, CYCLE8_U034F_LETTER_ARM_ID
from .letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix


CYCLE8_MIX_SCORECARD_VERSION = "cycle8-mix-margin-scorecard-v1"
_PRIMARY = Path("evidence/cycle8-mix-1020000-n64-2026-08-26/detector-compare.json")
_REPLICA = Path("evidence/cycle8-mix-1030000-n64-2026-08-26/detector-compare.json")
_RENDER_FIXTURES = (
    ("short_paragraph", "I do not agree.", True),
    ("quote_heavy", 'He answered, "They are not finished and we do not agree." Then he left.', False),
    ("machine_url", "See https://example.com/do-not-touch and continue the notes.", False),
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compact(row: dict[str, object]) -> dict[str, object]:
    scores = row["raw_watermarked_scores"]
    return {
        "seed_base": row["seed_base"],
        "pair_count": row["pair_count"],
        "topic": row.get("topic"),
        "artifact_hash": row.get("artifact_hash"),
        "raw_watermarked_detected": row["raw_watermarked_detected"],
        "raw_unwatermarked_detected": row["raw_unwatermarked_detected"],
        "pristine_watermarked_detected": row["pristine_watermarked_detected"],
        "visible_pass": f"{row['visible_pass']}/{row['visible_total']}",
        "mean": scores["mean"],
        "median": scores["median"],
        "min": scores["min"],
        "max": scores["max"],
        "max_gap_below_threshold": scores["max_gap_below_threshold"],
        "closest": row.get("closest_watermarked_row"),
        "inserted_count_mean": row["inserted_count_mean"],
        "utf8_overhead_mean": row["utf8_overhead_mean"],
        "token_count_delta_mean": row.get("token_count_delta_mean"),
        "transformed_token_count_max": row.get("transformed_token_count_max"),
        "cap_bind_watermarked": row.get("cap_bind_watermarked"),
        "domains": [
            {
                "domain": item["domain"],
                "watermarked_n": item["watermarked_n"],
                "raw_detected": item["raw_detected"],
                "max": item["scores"]["max"],
            }
            for item in row.get("domains") or ()
        ],
        "sanitizers": row.get("sanitizers"),
    }


def _merge_domains(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets: dict[str, dict[str, object]] = {}
    for row in rows:
        for item in row.get("domains") or ():
            domain = str(item["domain"])
            bucket = buckets.setdefault(
                domain,
                {"domain": domain, "watermarked_n": 0, "raw_detected": 0, "max": None},
            )
            bucket["watermarked_n"] = int(bucket["watermarked_n"]) + int(item["watermarked_n"])
            bucket["raw_detected"] = int(bucket["raw_detected"]) + int(item["raw_detected"])
            maximum = item["scores"]["max"]
            if maximum is not None:
                previous = bucket["max"]
                bucket["max"] = maximum if previous is None else max(float(previous), float(maximum))
    return [buckets[key] for key in sorted(buckets)]


def _frozen_sanitizers_match_raw(rows: list[dict[str, object]]) -> bool:
    for row in rows:
        raw = int(row["raw_watermarked_detected"])
        sanitizers = row.get("sanitizers") or {}
        for payload in sanitizers.values():
            if int(payload["watermarked_detected"]) != raw:
                return False
    return bool(rows)


def run_mix_local_measurements() -> dict[str, object]:
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    hashes = tuple(sha256_text(apply_letter_alternating_mix(source)) for _ in range(5))
    visible_pass = 0
    visible_total = 0
    render_rows = []
    for fixture_id, text, extra in _RENDER_FIXTURES:
        applied = apply_letter_alternating_mix(text)
        visible_total += 1
        if is_carrier_insertion_v1(text, applied, LETTER_MIX_APPROVED_CARRIERS) and project_visible_v1(
            applied, LETTER_MIX_APPROVED_CARRIERS
        ) == text:
            visible_pass += 1
        render_rows.append(
            {
                "fixture_id": fixture_id,
                "render": run_rendering(text, applied, extra_surfaces=extra),
            }
        )
    mn_removed = strip_nonspacing_marks(transformed)
    di_removed = strip_default_ignorable(transformed)
    payload = {
        "algorithm_version": CYCLE8_MIX_SCORECARD_VERSION,
        "mechanism_id": CYCLE8_LETTER_ALT_ARM_ID,
        "visible_pass": visible_pass,
        "visible_total": visible_total,
        "visible_pass_rate": f"{visible_pass}/{visible_total}",
        "release_registry_empty": release_transform_registry().rules == (),
        "cli_identity": process_text(source) == source,
        "cli_preserves_transformed": process_text(transformed) == transformed,
        "determinism": {
            "repeats": 5,
            "unique_hashes": len(set(hashes)),
            "deterministic": len(set(hashes)) == 1,
            "output_sha256": hashes[0],
        },
        "roundtrips": {
            "utf8_in_memory": transformed.encode("utf-8").decode("utf-8") == transformed,
            "nfc": nfc_normalize(transformed) == transformed,
            "nfkc": nfkc_normalize(transformed) == transformed,
            "cf_strip": strip_unicode_format_characters(transformed) == transformed,
            "ws_collapse": collapse_horizontal_ascii_whitespace(transformed) == transformed,
            "latin1": False,
        },
        "stress": {
            "mn_strip_removes_carrier": "\u034f" not in mn_removed and "\ufe00" not in mn_removed,
            "default_ignorable_strip_removes_carrier": "\u034f" not in di_removed and "\ufe00" not in di_removed,
        },
        "rendering": render_rows,
        "projected_equals_source": project_visible_v1(transformed, LETTER_MIX_APPROVED_CARRIERS) == source,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _render_status(local: dict[str, object]) -> dict[str, object]:
    rendering = local.get("rendering") or []
    summary = {
        "chromium_pre": "UNKNOWN",
        "chromium_textarea": "UNKNOWN",
        "chromium_contenteditable": "UNKNOWN",
        "webkit_safari": "UNKNOWN",
        "terminal_pixels": "UNKNOWN",
        "rows": [],
    }
    for row in rendering:
        render = row["render"]
        summary["rows"].append(
            {
                "fixture_id": row["fixture_id"],
                "chromium_pre": render["chromium_pre"].get("status"),
                "chromium_textarea": render["chromium_textarea"].get("status"),
                "chromium_contenteditable": render["chromium_contenteditable"].get("status"),
                "terminal_display_width": render["terminal_display_width"].get("status"),
                "terminal_pixels": render["terminal_pixels"].get("status"),
                "webkit_safari": render["webkit_safari"].get("status"),
            }
        )
        pre = render["chromium_pre"].get("status")
        if pre == "REJECTED":
            summary["chromium_pre"] = "REJECTED"
        elif pre == "VERIFIED" and summary["chromium_pre"] != "REJECTED":
            summary["chromium_pre"] = "VERIFIED"
        textarea = render["chromium_textarea"].get("status")
        if textarea == "REJECTED":
            summary["chromium_textarea"] = "REJECTED"
        elif textarea == "VERIFIED" and summary["chromium_textarea"] != "REJECTED":
            summary["chromium_textarea"] = "VERIFIED"
        editable = render["chromium_contenteditable"].get("status")
        if editable == "REJECTED":
            summary["chromium_contenteditable"] = "REJECTED"
        elif editable == "VERIFIED" and summary["chromium_contenteditable"] != "REJECTED":
            summary["chromium_contenteditable"] = "VERIFIED"
        if render["webkit_safari"].get("status") == "UNKNOWN":
            summary["webkit_safari"] = "UNKNOWN"
        if render["terminal_pixels"].get("status") == "UNKNOWN":
            summary["terminal_pixels"] = "UNKNOWN"
    return summary


def build_mix_margin_scorecard(*, local: dict[str, object]) -> dict[str, object]:
    primary = _load(_PRIMARY)
    replica = _load(_REPLICA)
    mix_primary = enrich_detector_artifact(primary, transformed_arm_id=CYCLE8_LETTER_ALT_ARM_ID)
    mix_replica = enrich_detector_artifact(replica, transformed_arm_id=CYCLE8_LETTER_ALT_ARM_ID)
    letter_primary = enrich_detector_artifact(primary, transformed_arm_id=CYCLE8_U034F_LETTER_ARM_ID)
    letter_replica = enrich_detector_artifact(replica, transformed_arm_id=CYCLE8_U034F_LETTER_ARM_ID)
    mix_rows = [mix_primary, mix_replica]
    mix_detected = int(mix_primary["raw_watermarked_detected"]) + int(mix_replica["raw_watermarked_detected"])
    mix_uw = int(mix_primary["raw_unwatermarked_detected"]) + int(mix_replica["raw_unwatermarked_detected"])
    letter_detected = int(letter_primary["raw_watermarked_detected"]) + int(letter_replica["raw_watermarked_detected"])
    mix_max = max(float(mix_primary["raw_watermarked_scores"]["max"]), float(mix_replica["raw_watermarked_scores"]["max"]))
    letter_max = max(
        float(letter_primary["raw_watermarked_scores"]["max"]),
        float(letter_replica["raw_watermarked_scores"]["max"]),
    )
    base_environment = environment_payload()
    environment = {key: value for key, value in base_environment.items() if key != "environment_hash"}
    environment["algorithm_version"] = CYCLE8_MIX_SCORECARD_VERSION
    environment["benchmark_arm_ids"] = list(CYCLE8_MIX_ARM_IDS)
    environment_hash = sha256_json(environment)
    render = _render_status(local)
    payload = {
        "algorithm_version": CYCLE8_MIX_SCORECARD_VERSION,
        "mechanism_id": CYCLE8_LETTER_ALT_ARM_ID,
        "confirmation": False,
        "freeze": False,
        "product_authorized": False,
        "release_registry_empty": release_transform_registry().rules == (),
        "decision": "PROMISING_DEVELOPMENT",
        "evidence_label": "HYPOTHESIS",
        "threshold": CYCLE6_THRESHOLD,
        "environment_hash": environment_hash,
        "effectiveness": {
            "fresh_mix": {
                "label": "HYPOTHESIS",
                "pairs": 128,
                "rate": f"{mix_detected}/128",
                "raw_watermarked_detected": mix_detected,
                "raw_unwatermarked_detected": mix_uw,
                "max_score": mix_max,
                "min_gap_below_threshold": CYCLE6_THRESHOLD - mix_max,
                "1020000": _compact(mix_primary),
                "1030000": _compact(mix_replica),
                "domains": _merge_domains(mix_rows),
            },
            "fresh_letter_x1_same_corpora": {
                "label": "HYPOTHESIS",
                "pairs": 128,
                "rate": f"{letter_detected}/128",
                "raw_watermarked_detected": letter_detected,
                "max_score": letter_max,
                "min_gap_below_threshold": CYCLE6_THRESHOLD - letter_max,
            },
            "letter_space_spent": {
                "label": "HYPOTHESIS",
                "rate": "1/128",
                "detail": "seeds 1000000 and 1010000 remain 1/128 and are not rewritten as zero",
            },
            "letter_x1_system_benchmark": {
                "label": "HYPOTHESIS",
                "rate": "0/128",
                "max_score": 0.5540663040663041,
                "min_gap_below_threshold": 0.003032461365794714,
                "detail": "seeds 980000 and 990000 remain the letter-x1 system benchmark",
            },
        },
        "durability": {
            "frozen_sanitizers_match_raw_on_fresh_mix": _frozen_sanitizers_match_raw(mix_rows),
            "roundtrips": local["roundtrips"],
            "stress": local["stress"],
        },
        "visibility": {
            "label": "VERIFIED" if int(local["visible_pass"]) == int(local["visible_total"]) else "REJECTED",
            "fixture_pass_rate": local["visible_pass_rate"],
            "cli_identity": local["cli_identity"],
            "projected_equals_source": local["projected_equals_source"],
            "rendering": render,
        },
        "reproducibility": {
            "deterministic_output": bool(local["determinism"]["deterministic"]),
            "determinism_unique_hashes": int(local["determinism"]["unique_hashes"]),
            "fresh_independent_corpora": 2,
            "fresh_mix_zero_on_both_corpora": mix_detected == 0,
        },
        "efficiency": {
            "fresh_inserted_count_mean": (
                float(mix_primary["inserted_count_mean"]) + float(mix_replica["inserted_count_mean"])
            )
            / 2,
            "fresh_utf8_overhead_mean": (
                float(mix_primary["utf8_overhead_mean"]) + float(mix_replica["utf8_overhead_mean"])
            )
            / 2,
            "fresh_token_count_delta_mean": (
                float(mix_primary.get("token_count_delta_mean") or 0)
                + float(mix_replica.get("token_count_delta_mean") or 0)
            )
            / 2,
            "fresh_transformed_token_count_max": max(
                int(mix_primary.get("transformed_token_count_max") or 0),
                int(mix_replica.get("transformed_token_count_max") or 0),
            ),
            "fresh_cap_bind_watermarked": int(mix_primary.get("cap_bind_watermarked") or 0)
            + int(mix_replica.get("cap_bind_watermarked") or 0),
            "letter_cap": 192,
        },
        "formal_confirmation_readiness": {
            "ready": False,
            "label": "NOT_READY",
            "reasons": [
                "fresh mix 0/128 is development evidence, not a preregistered confirmation protocol",
                "only two independent n=64 corpora have been scored for this mechanism",
                "letter-alt is not frozen and is not in release_transform_registry()",
                "seed 950000 remains ungenerated",
                "Mn-strip removes U+034F and selected default-ignorable stripping removes the mix carriers",
                "this scorecard is measurement, not confirmation",
            ],
        },
        "local_artifact_hash": local["artifact_hash"],
        "weaknesses": [
            "Mn-strip removes U+034F",
            "default-ignorable-strip removes U+034F and U+FE00",
            "latin-1 cannot roundtrip U+034F or U+FE00",
            "ordinary vim save may append a trailing newline",
            "selected-site cap 192 still binds on long rows",
            "token expansion remains large",
            "Safari/WebKit rendering is UNKNOWN on this Linux host",
            "terminal pixel equality is UNKNOWN",
        ],
    }
    return {**payload, "scorecard_hash": sha256_json(payload)}
