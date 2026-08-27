import pytest

from fuckmark.cli import process_text
from fuckmark.cycle8.letter_mix import LETTER_MIX_APPROVED_CARRIERS, apply_letter_alternating_mix
from fuckmark.product.encodings import (
    PRODUCT_TEXT_ENCODING,
    UNSUPPORTED_PRODUCT_ENCODINGS,
    canonical_product_encoding_name,
    encoding_roundtrip_survives,
    is_supported_product_encoding,
    require_supported_product_encoding,
)


def test_product_text_encoding_is_utf8_only() -> None:
    assert PRODUCT_TEXT_ENCODING == "utf-8"
    assert is_supported_product_encoding("utf-8") is True
    assert is_supported_product_encoding("UTF8") is True
    assert is_supported_product_encoding("utf_8") is True
    for name in ("latin-1", "latin1", "iso-8859-1", "ascii", "us-ascii", "cp1252", "windows-1252"):
        assert is_supported_product_encoding(name) is False
        with pytest.raises(ValueError, match="unsupported product encoding"):
            require_supported_product_encoding(name)
    assert UNSUPPORTED_PRODUCT_ENCODINGS == frozenset({"latin-1", "ascii", "cp1252"})
    assert canonical_product_encoding_name("ISO8859-1") == "latin-1"
    assert require_supported_product_encoding("utf-8") == "utf-8"


def test_mix_payload_roundtrips_utf8_and_is_unsupported_on_latin1() -> None:
    source = "I do not agree."
    transformed = apply_letter_alternating_mix(source)
    assert encoding_roundtrip_survives(transformed, "utf-8") is True
    assert encoding_roundtrip_survives(transformed, "latin-1") is False
    assert encoding_roundtrip_survives(transformed, "ascii") is False
    assert encoding_roundtrip_survives(transformed, "cp1252") is False
    assert encoding_roundtrip_survives(source, "latin-1") is True
    assert process_text(source) == apply_letter_alternating_mix(source)
    assert transformed != source
    assert all(chr(codepoint) in transformed for codepoint in LETTER_MIX_APPROVED_CARRIERS)
