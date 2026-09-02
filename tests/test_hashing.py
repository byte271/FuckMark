import json
from pathlib import Path

from fuckmark.hashing import sha256_bytes, sha256_file, sha256_lf_file, sha256_text


def test_byte_and_text_hash_match_for_utf8() -> None:
    text = "FuckMark"
    assert sha256_text(text) == sha256_bytes(text.encode("utf-8"))


def test_lf_file_hash_folds_crlf(tmp_path: Path) -> None:
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"a\nb\n")
    crlf.write_bytes(b"a\r\nb\r\n")
    assert sha256_lf_file(lf) == sha256_lf_file(crlf) == sha256_file(lf)
    assert sha256_file(crlf) != sha256_file(lf)


def test_text_hash_accepts_lone_surrogates() -> None:
    lone = "\ud800"
    assert sha256_text(lone) == sha256_bytes(lone.encode("utf-8", "surrogatepass"))
    assert sha256_text(lone) != sha256_text("")


def test_json_utf8_escapes_lone_surrogates() -> None:
    from fuckmark.config import canonical_json_bytes, json_utf8_bytes, json_utf8_text

    lone = "\ud800"
    dumped = json_utf8_text({"text": lone})
    encoded = json_utf8_bytes({"text": lone})
    assert "\\ud800" in dumped
    assert encoded == dumped.encode("utf-8")
    encoded.decode("utf-8")
    assert b"\xed\xa0\x80" not in encoded
    assert json.loads(encoded) == {"text": lone}
    canonical = canonical_json_bytes({"text": lone})
    canonical.decode("utf-8")
    assert b"\xed\xa0\x80" not in canonical


def test_file_hash_matches_content_hash(tmp_path: Path) -> None:
    path = tmp_path / "fixture.bin"
    payload = b"abc\x00def"
    path.write_bytes(payload)
    assert sha256_file(path) == sha256_bytes(payload)


def test_file_hash_rejects_non_positive_chunk_size(tmp_path: Path) -> None:
    import pytest

    path = tmp_path / "fixture.bin"
    path.write_bytes(b"real content")
    with pytest.raises(ValueError):
        sha256_file(path, chunk_size=0)
    with pytest.raises(ValueError):
        sha256_file(path, chunk_size=-1)


def test_seed_rejects_non_string_scope_parts() -> None:
    import pytest
    from fuckmark.hashing import derive_seed

    with pytest.raises(TypeError):
        derive_seed(42, 123)


def test_integer_and_string_master_seeds_are_distinct() -> None:
    from fuckmark.hashing import derive_seed

    assert derive_seed(42, "scope") != derive_seed("42", "scope")


def test_hashing_rejects_wrong_input_types() -> None:
    import pytest

    with pytest.raises(TypeError):
        sha256_bytes("abc")
    with pytest.raises(TypeError):
        sha256_text(b"abc")
    with pytest.raises(TypeError):
        sha256_lf_file(123)


def test_file_hash_rejects_non_integer_chunk_size(tmp_path: Path) -> None:
    import pytest

    path = tmp_path / "fixture.bin"
    path.write_bytes(b"content")
    with pytest.raises(TypeError):
        sha256_file(path, chunk_size=1.5)
