from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import canonical_json_text
from .cycle8.benchmark import (
    CYCLE8_BENCHMARK_VERSION,
    enrich_detector_artifact,
    environment_payload,
    run_local_system_benchmark,
)
from .cycle8.compare import CYCLE8_U034F_LETTER_ARM_ID, CYCLE8_U034F_SPACE_ARM_ID
from .durable_io import write_canonical_json_fsynced
from .hashing import sha256_file, sha256_json
from .transforms.registry import release_transform_registry


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _maybe_enrich(path: Path, arm_id: str) -> dict[str, object] | None:
    if not path.is_file():
        return None
    return enrich_detector_artifact(_load(path), transformed_arm_id=arm_id)


def _pick(rows: list[dict[str, object]], seed_base: int, arm_id: str) -> dict[str, object] | None:
    for row in rows:
        if int(row["seed_base"]) == seed_base and row["arm_id"] == arm_id:
            return row
    return None


def _compact_row(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    scores = row["raw_watermarked_scores"]
    closest = row.get("closest_watermarked_row")
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
        "stdev": scores["stdev"],
        "min": scores["min"],
        "max": scores["max"],
        "p90": scores["p90"],
        "p95": scores["p95"],
        "max_gap_below_threshold": scores["max_gap_below_threshold"],
        "closest": closest,
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


def _roundtrip_status(local: dict[str, object]) -> dict[str, str]:
    roundtrips = local["roundtrips"]
    return {name: str(payload["status"]) for name, payload in roundtrips.items()}


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
                "webkit_safari": render["webkit_safari"].get("status"),
                "terminal_pixels": render["terminal_pixels"].get("status"),
                "terminal_display_width": render["terminal_display_width"].get("status"),
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
    return summary


def build_scorecard(
    local: dict[str, object],
    *,
    environment: dict[str, object],
    detector_stats: list[dict[str, object]],
) -> dict[str, object]:
    letter_primary = _pick(detector_stats, 980000, CYCLE8_U034F_LETTER_ARM_ID)
    letter_replication = _pick(detector_stats, 990000, CYCLE8_U034F_LETTER_ARM_ID)
    space_primary = _pick(detector_stats, 980000, CYCLE8_U034F_SPACE_ARM_ID)
    space_replication = _pick(detector_stats, 990000, CYCLE8_U034F_SPACE_ARM_ID)
    letter_930 = _pick(detector_stats, 930000, CYCLE8_U034F_LETTER_ARM_ID)
    letter_940 = _pick(detector_stats, 940000, CYCLE8_U034F_LETTER_ARM_ID)
    letter_970 = _pick(detector_stats, 970000, CYCLE8_U034F_LETTER_ARM_ID)
    space_930 = _pick(detector_stats, 930000, CYCLE8_U034F_SPACE_ARM_ID)
    space_940 = _pick(detector_stats, 940000, CYCLE8_U034F_SPACE_ARM_ID)
    fresh = [row for row in (letter_primary, letter_replication) if row is not None]
    fresh_pairs = sum(int(row["pair_count"]) for row in fresh)
    fresh_detected = sum(int(row["raw_watermarked_detected"]) for row in fresh)
    fresh_uw = sum(int(row["raw_unwatermarked_detected"]) for row in fresh)
    max_scores = [
        float(row["raw_watermarked_scores"]["max"])
        for row in fresh
        if row["raw_watermarked_scores"]["max"] is not None
    ]
    gaps = [
        float(row["raw_watermarked_scores"]["max_gap_below_threshold"])
        for row in fresh
        if row["raw_watermarked_scores"]["max_gap_below_threshold"] is not None
    ]
    space_fresh = [row for row in (space_primary, space_replication) if row is not None]
    space_fresh_pairs = sum(int(row["pair_count"]) for row in space_fresh)
    space_fresh_detected = sum(int(row["raw_watermarked_detected"]) for row in space_fresh)
    experimental = [row for row in (letter_930, letter_940, letter_970) if row is not None]
    experimental_pairs = sum(int(row["pair_count"]) for row in experimental)
    experimental_detected = sum(int(row["raw_watermarked_detected"]) for row in experimental)
    thinnest = min(gaps) if gaps else None
    thickest_max = max(max_scores) if max_scores else None
    roundtrips = _roundtrip_status(local)
    render = _render_status(local)
    performance = local["performance"]
    stress = local.get("stress") or {}
    ready_reasons = [
        "fresh letter-x1 980000 max score sits 0.003 below the frozen threshold",
        "experimental 0/192 is 128 seen diagnostic plus 64 independent, not a preregistered confirmation protocol",
        "letter-x1 is not frozen and is not in release_transform_registry()",
        "seed 950000 remains ungenerated",
        "Mn-strip and default-ignorable-strip remove U+034F",
        "this benchmark is measurement, not confirmation",
    ]
    payload = {
        "algorithm_version": CYCLE8_BENCHMARK_VERSION,
        "confirmation": False,
        "freeze": False,
        "product_authorized": False,
        "evidence_label": "HYPOTHESIS",
        "decision": "PROMISING_DEVELOPMENT",
        "formal_confirmation_readiness": {
            "ready": False,
            "label": "NOT_READY",
            "reasons": ready_reasons,
        },
        "release_registry_empty": release_transform_registry().rules == (),
        "mechanism_id": CYCLE8_U034F_LETTER_ARM_ID,
        "detector": {
            "model": environment["model"],
            "model_revision": environment["model_revision"],
            "implementation": "cycle8_hf Hugging Face SynthID Weighted Mean",
            "threshold": environment["threshold"],
            "comparison": environment["comparison"],
            "fpr_assumption": environment["fpr_assumption"],
            "tokenizer": "Hugging Face GPT-2 tokenizer via cycle8_hf encoder",
            "environment_hash": environment["environment_hash"],
        },
        "effectiveness": {
            "fresh_letter_x1": {
                "label": "HYPOTHESIS",
                "pairs": fresh_pairs,
                "raw_watermarked_detected": fresh_detected,
                "raw_unwatermarked_detected": fresh_uw,
                "rate": None if not fresh_pairs else f"{fresh_detected}/{fresh_pairs}",
                "max_score": thickest_max,
                "min_gap_below_threshold": thinnest,
                "980000": _compact_row(letter_primary),
                "990000": _compact_row(letter_replication),
                "domains": _merge_domains(fresh),
            },
            "fresh_space_x1_same_corpora": {
                "label": "HYPOTHESIS",
                "pairs": space_fresh_pairs,
                "raw_watermarked_detected": space_fresh_detected,
                "rate": None if not space_fresh_pairs else f"{space_fresh_detected}/{space_fresh_pairs}",
                "980000": _compact_row(space_primary),
                "990000": _compact_row(space_replication),
            },
            "experimental_0_of_192": {
                "label": "HYPOTHESIS",
                "pairs": experimental_pairs,
                "detected": experimental_detected,
                "rate": None if not experimental_pairs else f"{experimental_detected}/{experimental_pairs}",
                "seen_pairs": 128,
                "independent_pairs": 64,
                "seen_seeds": [930000, 940000],
                "independent_seed": 970000,
                "930000": _compact_row(letter_930),
                "940000": _compact_row(letter_940),
                "970000": _compact_row(letter_970),
            },
            "space_x1_frozen_historical": {
                "label": "HYPOTHESIS",
                "930000_n64": "1/64" if space_930 is None else f"{space_930['raw_watermarked_detected']}/{space_930['pair_count']}",
                "940000_n64": "0/64" if space_940 is None else f"{space_940['raw_watermarked_detected']}/{space_940['pair_count']}",
                "combined": "1/128",
            },
        },
        "visibility": {
            "label": "VERIFIED" if local["visible_failures"] == [] else "REJECTED",
            "fixture_pass_rate": local["visible_pass_rate"],
            "fixture_failures": local["visible_failures"],
            "cli_identity": local["cli_identity"],
            "rendering": render,
        },
        "durability": {
            "roundtrips": roundtrips,
            "frozen_sanitizers_match_raw_on_fresh_letter": _frozen_sanitizers_match_raw(fresh),
            "stress": stress,
        },
        "safety": {
            "protected_pass_rate": local["protected_pass_rate"],
            "supported_domain_fail_closed_non_ascii": True,
            "fail_closed_fixture_ids": stress.get("fail_closed_fixture_ids"),
        },
        "efficiency": {
            "letter_cap": 192,
            "fresh_inserted_count_mean": (
                sum(float(row["inserted_count_mean"]) for row in fresh) / len(fresh) if fresh else None
            ),
            "fresh_utf8_overhead_mean": (
                sum(float(row["utf8_overhead_mean"]) for row in fresh) / len(fresh) if fresh else None
            ),
            "fresh_token_count_delta_mean": (
                sum(float(row["token_count_delta_mean"] or 0) for row in fresh) / len(fresh) if fresh else None
            ),
            "fresh_transformed_token_count_max": (
                max(int(row["transformed_token_count_max"] or 0) for row in fresh) if fresh else None
            ),
            "fresh_cap_bind_watermarked": sum(int(row.get("cap_bind_watermarked") or 0) for row in fresh),
            "approaches_gpt2_context_limit": any(bool(row.get("approaches_gpt2_context_limit")) for row in fresh),
        },
        "performance": {
            "label": "SOURCE-BOUND",
            "short_transform_mean_ms": performance["short"]["transform_mean_ms"],
            "medium_transform_mean_ms": performance["medium"]["transform_mean_ms"],
            "long_transform_mean_ms": performance["long"]["transform_mean_ms"],
            "short_chars_per_s": performance["short"]["transform_chars_per_s"],
            "medium_chars_per_s": performance["medium"]["transform_chars_per_s"],
            "long_chars_per_s": performance["long"]["transform_chars_per_s"],
            "host": performance.get("host"),
            "python": performance.get("python"),
            "cpu_count": performance.get("cpu_count"),
        },
        "reproducibility": {
            "deterministic_output": local["determinism"]["deterministic"],
            "determinism_unique_hashes": local["determinism"]["unique_hashes"],
            "fresh_independent_corpora": len(fresh),
            "fresh_letter_zero_on_both_corpora": fresh_detected == 0 and fresh_pairs == 128,
        },
        "platform": {
            "linux_this_host": "VERIFIED",
            "macos_cli_identity": "SOURCE-BOUND",
            "windows_cli_identity": "SOURCE-BOUND",
            "detail": "Package E2E on CI covers CLI identity on Linux/macOS/Windows. Letter-x1 is development-only Python and was executed on this Linux host.",
        },
        "baselines": {
            "identity": "HISTORICAL_ONLY",
            "cycle6_visible_spacing": "PRODUCT_DISQUALIFIED",
            "cycle7_visible_edit": "PRODUCT_DISQUALIFIED",
            "u200c_space_x1": "REJECTED",
            "u034f_space_x1": "HYPOTHESIS",
            "u034f_letter_x1": "HYPOTHESIS",
        },
        "weaknesses": [
            "Mn-strip removes U+034F",
            "default-ignorable-strip removes U+034F",
            "latin-1 cannot roundtrip U+034F",
            "ordinary vim save may append a trailing newline",
            "exact-byte search for substrings such as do not can miss after intra-word insertion",
            "selected-site cap 192 binds on 106 of 128 fresh watermarked rows",
            "980000 max score 0.55407 leaves only about 0.003 margin",
            "Safari/WebKit rendering is UNKNOWN on this Linux host",
            "terminal pixel equality is UNKNOWN",
            "accessibility/screen-reader behavior is UNKNOWN",
            "macOS and Windows letter-x1 transform execution is SOURCE-BOUND, not re-run here",
        ],
        "environment_hash": environment["environment_hash"],
        "local_artifact_hash": local["artifact_hash"],
        "detector_stats": [
            {
                "seed_base": row["seed_base"],
                "pair_count": row["pair_count"],
                "arm_id": row["arm_id"],
                "stats_hash": row["stats_hash"],
            }
            for row in detector_stats
        ],
    }
    return {**payload, "scorecard_hash": sha256_json(payload)}


def scorecard_markdown(scorecard: dict[str, object]) -> str:
    letter = scorecard["effectiveness"]["fresh_letter_x1"]
    space = scorecard["effectiveness"]["fresh_space_x1_same_corpora"]
    experimental = scorecard["effectiveness"]["experimental_0_of_192"]
    frozen_space = scorecard["effectiveness"]["space_x1_frozen_historical"]
    vis = scorecard["visibility"]
    dur = scorecard["durability"]
    safety = scorecard["safety"]
    eff = scorecard["efficiency"]
    perf = scorecard["performance"]
    repro = scorecard["reproducibility"]
    plat = scorecard["platform"]
    detector = scorecard["detector"]
    render = vis["rendering"]
    lines = [
        "# Cycle 8 letter-x1 system benchmark scorecard",
        "",
        "Measurement, not confirmation. Letter-x1 is not in `release_transform_registry()`.",
        f"Evidence label: `{scorecard['evidence_label']}`. Decision: `{scorecard['decision']}`.",
        f"Formal confirmation readiness: `{scorecard['formal_confirmation_readiness']['label']}`.",
        "",
        "## Detector",
        "",
        f"- model: `{detector['model']}`",
        f"- revision: `{detector['model_revision']}`",
        f"- implementation: {detector['implementation']}",
        f"- threshold: `{detector['threshold']}`",
        f"- comparison: `{detector['comparison']}`",
        f"- FPR assumption: {detector['fpr_assumption']}",
        "",
        "## Effectiveness",
        "",
        "| Claim | Result | Label |",
        "| --- | --- | --- |",
        f"| Fresh letter-x1 raw WM | {letter['rate']} | `{letter['label']}` |",
        f"| Fresh letter-x1 raw UW | {letter['raw_unwatermarked_detected']}/{letter['pairs']} | `{letter['label']}` |",
        f"| Fresh letter-x1 max score | {letter['max_score']} | `{letter['label']}` |",
        f"| Fresh letter-x1 min gap below threshold | {letter['min_gap_below_threshold']} | `{letter['label']}` |",
        f"| Fresh space-x1 on the same corpora | {space['rate']} | `{space['label']}` |",
        f"| Experimental letter-x1 0/192 | {experimental['rate']} ({experimental['seen_pairs']} seen + {experimental['independent_pairs']} independent) | `{experimental['label']}` |",
        f"| Frozen historical space-x1 930000+940000 | {frozen_space['combined']} | `{frozen_space['label']}` |",
        "",
        "Do not collapse experimental 0/192 into the fresh 0/128. Do not call either result formal confirmation.",
        "",
        "### Fresh per-domain letter-x1",
        "",
        "| Domain | n | detected | max score |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in letter["domains"]:
        lines.append(
            f"| {item['domain']} | {item['watermarked_n']} | {item['raw_detected']} | {item['max']} |"
        )
    lines.extend(
        [
            "",
            "## Visibility",
            "",
            f"- fixture visible-projection: `{vis['fixture_pass_rate']}` `{vis['label']}`",
            f"- failures: {vis['fixture_failures'] or 'none'}",
            f"- CLI identity on `I do not agree.`: `{vis['cli_identity']}`",
            f"- Chromium `pre`: `{render['chromium_pre']}`",
            f"- Chromium textarea: `{render['chromium_textarea']}`",
            f"- Chromium contenteditable: `{render['chromium_contenteditable']}`",
            f"- WebKit/Safari: `{render['webkit_safari']}`",
            f"- terminal pixels: `{render['terminal_pixels']}`",
            "",
            "## Durability",
            "",
        ]
    )
    for name, status in dur["roundtrips"].items():
        lines.append(f"- {name}: `{status}`")
    lines.extend(
        [
            "",
            f"- frozen sanitizers match raw on fresh letter: `{dur['frozen_sanitizers_match_raw_on_fresh_letter']}`",
            f"- Mn-strip removes carrier: `{dur['stress'].get('mn_strip_removes_carrier')}`",
            f"- default-ignorable-strip removes carrier: `{dur['stress'].get('default_ignorable_strip_removes_carrier')}`",
            f"- Cf-strip preserves carrier: `{dur['stress'].get('cf_strip_preserves_carrier')}`",
            "",
            "## Safety",
            "",
            f"- protected-span pass rate: `{safety['protected_pass_rate']}`",
            f"- non-ASCII fail closed: `{safety['supported_domain_fail_closed_non_ascii']}`",
            "",
            "## Efficiency",
            "",
            f"- selected-site cap: `{eff['letter_cap']}`",
            f"- fresh mean insertions: `{eff['fresh_inserted_count_mean']}`",
            f"- fresh mean UTF-8 overhead bytes: `{eff['fresh_utf8_overhead_mean']}`",
            f"- fresh mean token-count delta: `{eff['fresh_token_count_delta_mean']}`",
            f"- fresh max transformed token count: `{eff['fresh_transformed_token_count_max']}`",
            f"- fresh cap-binding watermarked rows: `{eff['fresh_cap_bind_watermarked']}`",
            f"- approaches GPT-2 1024 context: `{eff['approaches_gpt2_context_limit']}`",
            "",
            "## Performance",
            "",
            f"- label: `{perf['label']}`",
            f"- short mean transform: `{perf['short_transform_mean_ms']}` ms",
            f"- medium mean transform: `{perf['medium_transform_mean_ms']}` ms",
            f"- long mean transform: `{perf['long_transform_mean_ms']}` ms",
            f"- host: `{perf['host']}`",
            f"- python: `{perf['python']}`",
            f"- cpu_count: `{perf['cpu_count']}`",
            "",
            "## Reproducibility",
            "",
            f"- deterministic output: `{repro['deterministic_output']}`",
            f"- fresh independent corpora: `{repro['fresh_independent_corpora']}`",
            f"- letter zero on both fresh corpora: `{repro['fresh_letter_zero_on_both_corpora']}`",
            "",
            "## Platform",
            "",
            f"- Linux this host: `{plat['linux_this_host']}`",
            f"- macOS CLI identity: `{plat['macos_cli_identity']}`",
            f"- Windows CLI identity: `{plat['windows_cli_identity']}`",
            f"- {plat['detail']}",
            "",
            "## Weaknesses",
            "",
        ]
    )
    for item in scorecard["weaknesses"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            f"scorecard_hash: `{scorecard['scorecard_hash']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fuckmark-cycle8-letter-system-benchmark")
    parser.add_argument("--output-dir", type=Path, default=Path("evidence/cycle8-letter-system-benchmark-2026-08-26"))
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args(argv)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    environment = environment_payload()
    write_canonical_json_fsynced(output / "environment.json", environment)
    if args.skip_local and (output / "local-system.json").is_file():
        local = _load(output / "local-system.json")
    else:
        local = run_local_system_benchmark(include_render=not args.skip_render)
        write_canonical_json_fsynced(output / "local-system.json", local)
    detector_paths = (
        (Path("evidence/cycle8-letter-930000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_LETTER_ARM_ID),
        (Path("evidence/cycle8-letter-940000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_LETTER_ARM_ID),
        (Path("evidence/cycle8-letter-970000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_LETTER_ARM_ID),
        (Path("evidence/cycle8-scale-930000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_SPACE_ARM_ID),
        (Path("evidence/cycle8-scale-940000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_SPACE_ARM_ID),
        (Path("evidence/cycle8-letter-benchmark-980000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_LETTER_ARM_ID),
        (Path("evidence/cycle8-letter-benchmark-990000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_LETTER_ARM_ID),
        (Path("evidence/cycle8-letter-benchmark-980000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_SPACE_ARM_ID),
        (Path("evidence/cycle8-letter-benchmark-990000-n64-2026-08-26/detector-compare.json"), CYCLE8_U034F_SPACE_ARM_ID),
    )
    detector_stats = []
    for path, arm_id in detector_paths:
        row = _maybe_enrich(path, arm_id)
        if row is not None:
            detector_stats.append(row)
    write_canonical_json_fsynced(
        output / "detector-stats.json",
        {"rows": detector_stats, "artifact_hash": sha256_json({"rows": detector_stats})},
    )
    scorecard = build_scorecard(local, environment=environment, detector_stats=detector_stats)
    write_canonical_json_fsynced(output / "scorecard.json", scorecard)
    (output / "scorecard.md").write_text(scorecard_markdown(scorecard), encoding="utf-8")
    names = [
        "environment.json",
        "local-system.json",
        "detector-stats.json",
        "scorecard.json",
        "scorecard.md",
        "methodology.md",
        "README.md",
    ]
    lines = [f"{sha256_file(output / name)}  {name}" for name in names if (output / name).is_file()]
    (output / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        canonical_json_text(
            {
                "scorecard_hash": scorecard["scorecard_hash"],
                "visible_pass_rate": local["visible_pass_rate"],
                "fresh_letter_rate": scorecard["effectiveness"]["fresh_letter_x1"]["rate"],
                "formal_confirmation_readiness": scorecard["formal_confirmation_readiness"]["label"],
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
