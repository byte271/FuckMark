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
