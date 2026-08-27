import json
from pathlib import Path

from fuckmark.cycle8.mix_freeze import CYCLE8_MIX_FREEZE_LETTER_MIX_SHA256
from fuckmark.hashing import sha256_file, sha256_json


ROOT = Path(__file__).resolve().parents[1]
OLD_DIRS = (
    ROOT / "evidence/cycle8-letter-system-benchmark-2026-08-26",
    ROOT / "evidence/cycle8-mix-margin-2026-08-26",
)
NEW_DIR = ROOT / "evidence/audit-fixes-2026-08-27"


def test_historical_render_evidence_hashes_are_unchanged() -> None:
    for folder in OLD_DIRS:
        sums = (folder / "SHA256SUMS.txt").read_text(encoding="utf-8")
        for line in sums.splitlines():
            digest, name = line.split()
            assert sha256_file(folder / name) == digest


def test_f01_replacement_measurement_rejects_blank_div_false_positive() -> None:
    payload = json.loads((NEW_DIR / "render-v2.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in payload.items() if key != "artifact_hash"}
    assert payload["artifact_hash"] == sha256_json(body)
    assert payload["algorithm_version"] == "cycle8-benchmark-render-v2"
    assert payload["historical_files_not_rewritten"] is True
    assert "contenteditable divs" in payload["historical_evidence_invalid_because"]
    by_key = {(row["surface"], row["pair"]): row["result"]["status"] for row in payload["rows"]}
    assert by_key[("contenteditable", "negative")] == "REJECTED"
    assert by_key[("contenteditable", "positive")] == "VERIFIED"
    assert by_key[("contenteditable", "nonempty_vs_empty")] == "REJECTED"
    assert by_key[("textarea", "negative")] == "REJECTED"
    assert by_key[("textarea", "positive")] == "VERIFIED"
    assert by_key[("textarea", "nonempty_vs_empty")] == "REJECTED"
    assert payload["webkit_safari"] == "UNKNOWN"
    assert payload["terminal_pixels"] == "UNKNOWN"
    assert "DejaVu Sans Mono" in payload["font"]
    readme = (NEW_DIR / "README.md").read_text(encoding="utf-8")
    assert "not proof of text rendering equivalence" in readme
    assert "be6ae7645fda8b39d1d308722ac249f519e68de5" in readme
    scan = json.loads((NEW_DIR / "letter-mix-scan.json").read_text(encoding="utf-8"))
    scan_body = {key: value for key, value in scan.items() if key != "artifact_hash"}
    assert scan["artifact_hash"] == sha256_json(scan_body)
    assert scan["note"].startswith("Host observations only")


def test_mix_freeze_letter_mix_hash_stays_historical() -> None:
    live = sha256_file(ROOT / "fuckmark/cycle8/letter_mix.py")
    assert CYCLE8_MIX_FREEZE_LETTER_MIX_SHA256 == "b1ceec24e584c0e9e7135ef0c89a3bd249b0bda4a45e07aa7190b1b010ba56d4"
    assert live != CYCLE8_MIX_FREEZE_LETTER_MIX_SHA256
