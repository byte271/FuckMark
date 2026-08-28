from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from fuckmark.hashing import sha256_text
from fuckmark.product.visible_projection import is_carrier_insertion_v1, project_visible_v1


def live_mix_hash(source: str) -> str:
    live = apply_letter_alternating_mix(source)
    assert project_visible_v1(live, LETTER_MIX_APPROVED_CARRIERS) == source
    if live != source:
        assert is_carrier_insertion_v1(source, live, LETTER_MIX_APPROVED_CARRIERS)
    return sha256_text(live)
