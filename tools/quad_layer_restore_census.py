from __future__ import annotations

import argparse
import json
from pathlib import Path

from fuckmark.cycle8.benchmark import (
    strip_default_ignorable,
    strip_enclosing_marks,
    strip_nonspacing_marks,
    strip_other_controls,
)
from fuckmark.cycle8.control_carrier import apply_required_sanitizer_bundle
from fuckmark.cycle8.gate_v2 import GATE_V2_CONFIRMATION_SEED_BASES, gate_v2_confirmation_artifact_path
from fuckmark.cycle8.letter_mix import (
    LETTER_MIX_MECHANISM_ID,
    apply_historical_triple_layer_letter_mix,
    apply_letter_alternating_mix,
)
from fuckmark.cycle8.threat_model_audit import lm_watermarking_unicode_sanitizer
from fuckmark.config import canonical_json_text
from fuckmark.hashing import sha256_json
from fuckmark.product.visible_projection import project_visible_v1
from fuckmark.sanitizer_robustness import strip_unicode_format_characters


ARMS = (
    "quad_raw",
    "quad_mn_us",
    "quad_mn_me_us",
    "quad_di_me_us",
    "quad_mn_me_cc",
    "quad_bundle_us",
    "quad_mn_me_us_cf",
    "historical_triple_mn_me_us",
)
CF_RANGE = range(0x13430, 0x13440)


def _has_cf(text: str) -> bool:
    return any(ord(character) in CF_RANGE for character in text)


def _payloads(live: str, historical: str) -> dict[str, str]:
    mn_me = strip_enclosing_marks(strip_nonspacing_marks(live))
    return {
        "quad_raw": live,
        "quad_mn_us": lm_watermarking_unicode_sanitizer(strip_nonspacing_marks(live)),
        "quad_mn_me_us": lm_watermarking_unicode_sanitizer(mn_me),
        "quad_di_me_us": lm_watermarking_unicode_sanitizer(strip_enclosing_marks(strip_default_ignorable(live))),
        "quad_mn_me_cc": strip_other_controls(mn_me),
        "quad_bundle_us": lm_watermarking_unicode_sanitizer(apply_required_sanitizer_bundle(live)),
        "quad_mn_me_us_cf": strip_unicode_format_characters(lm_watermarking_unicode_sanitizer(mn_me)),
        "historical_triple_mn_me_us": lm_watermarking_unicode_sanitizer(
            strip_enclosing_marks(strip_nonspacing_marks(historical))
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("evidence/cycle8-quad-layer-restore-exploratory-2026-08-29/scorecard.json"),
    )
    arguments = parser.parse_args()
    totals = {
        arm: {"restores_source": 0, "matches_us_source": 0, "n": 0} for arm in ARMS
    }
    corpora = []
    visible_ok = 0
    us_stable = 0
    cf_after_mn_me_us = 0
    watermarked_rows = 0
    for seed_base in GATE_V2_CONFIRMATION_SEED_BASES:
        artifact = json.loads(Path(gate_v2_confirmation_artifact_path(seed_base)).read_text(encoding="utf-8"))
        rows = [sample for sample in artifact["samples"] if sample["label"] == "watermarked"]
        local_restore = {arm: 0 for arm in ARMS}
        local_us = {arm: 0 for arm in ARMS}
        local_visible = 0
        local_stable = 0
        local_cf = 0
        for sample in rows:
            source = str(sample["text"])
            live = apply_letter_alternating_mix(source)
            historical = apply_historical_triple_layer_letter_mix(source)
            us_source = lm_watermarking_unicode_sanitizer(source)
            if us_source == source:
                local_stable += 1
                us_stable += 1
            if project_visible_v1(live) == source:
                local_visible += 1
                visible_ok += 1
            payloads = _payloads(live, historical)
            if _has_cf(payloads["quad_mn_me_us"]):
                local_cf += 1
                cf_after_mn_me_us += 1
            for arm, text in payloads.items():
                restored = text == source
                matched = text == us_source
                local_restore[arm] += int(restored)
                local_us[arm] += int(matched)
                totals[arm]["restores_source"] += int(restored)
                totals[arm]["matches_us_source"] += int(matched)
                totals[arm]["n"] += 1
        watermarked_rows += len(rows)
        corpora.append(
            {
                "seed_base": seed_base,
                "watermarked_rows": len(rows),
                "visible_ok": local_visible,
                "us_stable_sources": local_stable,
                "cf_residual_after_mn_me_us": local_cf,
                "restores_source": local_restore,
                "matches_us_source": local_us,
            }
        )
    payload = {
        "algorithm_version": "cycle8-quad-layer-restore-exploratory-v1",
        "role": "exploratory_restore_census_of_frozen_sources",
        "confirmation_rewritten": False,
        "spent_confirmation_corpora_not_reused_for_generation": True,
        "detector_not_run": True,
        "mechanism_id": LETTER_MIX_MECHANISM_ID,
        "watermarked_rows": watermarked_rows,
        "visible_ok": visible_ok,
        "us_stable_sources": us_stable,
        "cf_residual_after_mn_me_us": cf_after_mn_me_us,
        "evidence_label": "HYPOTHESIS",
        "scope": (
            "Restore-only census of frozen Gate v2 confirmation watermarked sources from seeds "
            "1200000, 1210000, and 1220000 after live four-layer mix. Detector scores were not "
            "computed. Confirmation artifacts were not rewritten. matches_us_source compares the "
            "attacked mix to UnicodeSanitizer(source) because that sanitizer mutates some frozen "
            "sources even without mix."
        ),
        "effectiveness": {
            arm: {
                "restores_source": totals[arm]["restores_source"],
                "matches_us_source": totals[arm]["matches_us_source"],
                "n": totals[arm]["n"],
                "restore_rate": f"{totals[arm]['restores_source']}/{totals[arm]['n']}",
                "us_source_rate": f"{totals[arm]['matches_us_source']}/{totals[arm]['n']}",
            }
            for arm in ARMS
        },
        "corpora": corpora,
        "do_not_generate_950000": True,
        "do_not_rerun_looking_for_zero": True,
    }
    report = {**payload, "scorecard_hash": sha256_json(payload)}
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    print(json.dumps(report["effectiveness"], ensure_ascii=False, indent=2, sort_keys=True))
    print("visible_ok", visible_ok, "/", watermarked_rows)
    print("us_stable_sources", us_stable)
    print("cf_residual_after_mn_me_us", cf_after_mn_me_us)
    print("scorecard_hash", report["scorecard_hash"])
    print("wrote", arguments.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
