from __future__ import annotations

import argparse
from pathlib import Path

from fuckmark.config import canonical_json_text
from fuckmark.cycle8.compare import arm_registry, cycle8_fixture_samples, run_fixture_compare
from fuckmark.cycle8.decision import classify_fixture_compare
from fuckmark.cycle8.registry import apply_all_candidates
from fuckmark.cycle8.tokenizer_screen import GPT2_FIXTURE, load_gpt2_encoder
from fuckmark.durable_io import write_canonical_json_fsynced
from fuckmark.hashing import sha256_json
from fuckmark.product.rendering import compare_chrome_pre_screenshots
from fuckmark.product.visible_projection import is_carrier_insertion_v1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args(argv)
    encoder = load_gpt2_encoder()
    fixture = run_fixture_compare(encoder=encoder)
    destination = Path("specs/cycle8/fixture-compare-v1.json")
    write_canonical_json_fsynced(destination, fixture)
    decision = classify_fixture_compare(fixture)
    write_canonical_json_fsynced(Path("specs/cycle8/fixture-decision-v1.json"), decision)
    rendering = []
    if args.render:
        for sample_id, text in cycle8_fixture_samples():
            if sample_id != "gpt2-screen":
                continue
            for arm_id, codepoint in (
                ("u034f-space-x1", 0x034F),
                ("u034f-space-x8", 0x034F),
                ("u200c-space-x1", 0x200C),
                ("ufe00-space-x1", 0xFE00),
            ):
                registry = arm_registry(arm_id)
                transformed = apply_all_candidates(registry, text)
                comparison = compare_chrome_pre_screenshots(text, transformed)
                rendering.append(
                    {
                        "sample_id": sample_id,
                        "arm_id": arm_id,
                        "visible_ok": is_carrier_insertion_v1(text, transformed, (codepoint,)),
                        "environment": comparison.environment,
                        "status": comparison.status,
                        "equal": comparison.equal,
                        "detail": comparison.detail,
                    }
                )
        render_payload = {
            "algorithm_version": "cycle8-chrome-render-v1",
            "fixture": GPT2_FIXTURE,
            "rows": rendering,
        }
        render_payload["artifact_hash"] = sha256_json(
            {key: value for key, value in render_payload.items() if key != "artifact_hash"}
        )
        write_canonical_json_fsynced(Path("specs/cycle8/chrome-render-v1.json"), render_payload)
        print("chrome_render", canonical_json_text({"rows": rendering}))
    print(destination)
    print("visible_pass_rate", fixture["visible_pass_rate"])
    print("decision", decision["decision"], decision["product_gate"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
