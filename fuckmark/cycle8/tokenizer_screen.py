from __future__ import annotations

from collections.abc import Callable, Sequence

from ..hashing import sha256_json
from ..product.visible_projection import is_carrier_insertion_v1


TOKENIZER_SCREEN_VERSION = "cycle8-tokenizer-screen-v1"
GPT2_FIXTURE = "The researchers cannot continue until they do not miss the proof of concept."


def load_gpt2_encoder() -> Callable[[str], tuple[int, ...]] | None:
    try:
        import tiktoken
    except ImportError:
        return None
    encoding = tiktoken.get_encoding("gpt2")

    def encode(text: str) -> tuple[int, ...]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        return tuple(encoding.encode(text, disallowed_special=()) )

    return encode


def resynchronization_metrics(original_ids: Sequence[int], transformed_ids: Sequence[int]) -> dict[str, object]:
    original = tuple(original_ids)
    transformed = tuple(transformed_ids)
    first = None
    last = None
    limit = min(len(original), len(transformed))
    for index in range(limit):
        if original[index] != transformed[index]:
            if first is None:
                first = index
            last = index
    if first is None and len(original) != len(transformed):
        first = limit
        last = max(len(original), len(transformed)) - 1
    changed = 0
    if first is not None:
        changed = abs(len(transformed) - len(original))
        changed += sum(
            1 for index in range(limit) if original[index] != transformed[index]
        )
    suffix_align = 0
    original_index = len(original) - 1
    transformed_index = len(transformed) - 1
    while original_index >= 0 and transformed_index >= 0 and original[original_index] == transformed[transformed_index]:
        suffix_align += 1
        original_index -= 1
        transformed_index -= 1
    return {
        "original_token_count": len(original),
        "transformed_token_count": len(transformed),
        "token_count_delta": len(transformed) - len(original),
        "first_changed_token": first,
        "last_changed_token": last,
        "changed_token_estimate": changed,
        "suffix_alignment_tokens": suffix_align,
        "ids_equal": original == transformed,
    }


def insert_after_ascii_spaces(text: str, carrier: str, repeats: int = 1) -> str:
    if not isinstance(text, str) or not isinstance(carrier, str):
        raise TypeError("text and carrier must be strings")
    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats <= 0:
        raise ValueError("repeats must be a positive integer")
    payload = carrier * repeats
    pieces: list[str] = []
    for index, character in enumerate(text):
        pieces.append(character)
        if character == " " and 0 < index < len(text) - 1 and text[index - 1].isascii() and text[index - 1].isalpha() and text[index + 1].isascii() and text[index + 1].isalpha():
            pieces.append(payload)
    return "".join(pieces)


def insert_after_ascii_letters(text: str, carrier: str) -> str:
    if not isinstance(text, str) or not isinstance(carrier, str):
        raise TypeError("text and carrier must be strings")
    return "".join(character + carrier if character.isascii() and character.isalpha() else character for character in text)


def screen_carrier_tokenizer(
    codepoint: int,
    *,
    encoder: Callable[[str], tuple[int, ...]] | None = None,
    fixture: str = GPT2_FIXTURE,
) -> dict[str, object]:
    if encoder is None:
        encoder = load_gpt2_encoder()
    carrier = chr(codepoint)
    space_text = insert_after_ascii_spaces(fixture, carrier)
    space_run_text = insert_after_ascii_spaces(fixture, carrier, repeats=8)
    letter_text = insert_after_ascii_letters(fixture, carrier)
    payload: dict[str, object] = {
        "algorithm_version": TOKENIZER_SCREEN_VERSION,
        "codepoint": codepoint,
        "label": f"U+{codepoint:04X}",
        "fixture": fixture,
        "space_visible_ok": is_carrier_insertion_v1(fixture, space_text, (codepoint,)),
        "space_run_visible_ok": is_carrier_insertion_v1(fixture, space_run_text, (codepoint,)),
        "letter_visible_ok": is_carrier_insertion_v1(fixture, letter_text, (codepoint,)),
        "space_inserted": space_text.count(carrier),
        "space_run_inserted": space_run_text.count(carrier),
        "letter_inserted": letter_text.count(carrier),
        "space_utf8_overhead": len(space_text.encode("utf-8")) - len(fixture.encode("utf-8")),
        "space_run_utf8_overhead": len(space_run_text.encode("utf-8")) - len(fixture.encode("utf-8")),
        "letter_utf8_overhead": len(letter_text.encode("utf-8")) - len(fixture.encode("utf-8")),
        "encoder": "unavailable" if encoder is None else "gpt2",
    }
    if encoder is None:
        payload["space_metrics"] = None
        payload["space_run_metrics"] = None
        payload["letter_metrics"] = None
        payload["status"] = "UNKNOWN"
        return payload
    original_ids = encoder(fixture)
    payload["space_metrics"] = resynchronization_metrics(original_ids, encoder(space_text))
    payload["space_run_metrics"] = resynchronization_metrics(original_ids, encoder(space_run_text))
    payload["letter_metrics"] = resynchronization_metrics(original_ids, encoder(letter_text))
    payload["status"] = "VERIFIED"
    payload["evidence_hash"] = sha256_json(payload)
    return payload
