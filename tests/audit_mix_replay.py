from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from fuckmark.hashing import sha256_text
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1

PERMITTED_LIVE_MIX_DRIFT = {
    "cycle8-1080000-51-structured_instructional-unwatermarked": {
        "family": "deepmind-transfer",
        "label": "unwatermarked",
        "scope": "live path protection of sys/types.h after freeze; stored detector scores do not transfer",
        "stored_mix_sha256": "3da2b2707ff2307585661008922d3f25ddd91ccfa60040321a5277b08f64193d",
        "live_mix_sha256": "f6d4464ebbbf3adeae5b118e80151d38ad8e7511f47dc55aa309fd938a6fb860",
    },
    "cycle8-1080000-55-structured_instructional-unwatermarked": {
        "family": "deepmind-transfer",
        "label": "unwatermarked",
        "scope": "live HTML include and sys/types.h protection after freeze; stored detector scores do not transfer",
        "stored_mix_sha256": "14ed554609655ce2aaf22ca7d36d0d946babdc368d7276c15c443894dbc27c72",
        "live_mix_sha256": "e5c6da6a45f00a3b614752bef46c852e2a9ae2384d06fa83d4d679cddd1ab660",
    },
    "cycle8-840000-13-technical_explanation-watermarked": {
        "family": "mix-confirmation-mean-transfer",
        "label": "watermarked",
        "scope": "tests/test_validation is a live extensionless path; Gate v2 confirmation hashes are unchanged; stored mean-transfer scores do not transfer",
        "stored_mix_sha256": "096dadebdf8d309decaa841fb58d7bc0573d7c4d95eab306becfcfe3d21486b2",
        "live_mix_sha256": "845ec79d12040a9a77505d7da8b78b6de3e5c8ab94f9dc3cfc5ae8f6222642b9",
    },
}


def live_mix_hash(source: str) -> str:
    live = apply_letter_alternating_mix(source)
    assert project_visible_v1(live, LETTER_MIX_APPROVED_CARRIERS) == source
    if live != source:
        assert is_carrier_insertion_v1(source, live, LETTER_MIX_APPROVED_CARRIERS)
    return sha256_text(live)


def assert_live_mix_matches_stored(sample_id: str, source: str, stored_hash: str, *, label: str) -> str:
    live = live_mix_hash(source)
    if live == stored_hash:
        return live
    allowed = PERMITTED_LIVE_MIX_DRIFT.get(sample_id)
    if allowed is None:
        raise AssertionError(f"unexplained live mix drift for {sample_id}")
    if str(label) == "watermarked" and allowed.get("label") != "watermarked":
        raise AssertionError(f"watermarked sample drifted: {sample_id}")
    recorded_stored = allowed.get("stored_mix_sha256")
    if recorded_stored is not None and stored_hash != recorded_stored:
        raise AssertionError(f"permitted stored mix hash changed for {sample_id}")
    expected = allowed.get("live_mix_sha256")
    if expected is not None and live != expected:
        raise AssertionError(f"permitted drift hash changed for {sample_id}")
    return live
