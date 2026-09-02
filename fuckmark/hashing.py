from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .config import canonical_json_bytes


def sha256_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return sha256_bytes(text.encode("utf-8", "surrogatepass"))


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise TypeError("chunk_size must be an integer")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_lf_file(path: str | Path) -> str:
    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or Path")
    data = Path(path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256_bytes(data)


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def derive_seed(master_seed: int | str, *parts: str, bits: int = 64) -> int:
    if isinstance(master_seed, bool) or not isinstance(master_seed, (int, str)):
        raise TypeError("master_seed must be an integer or string")
    if any(not isinstance(part, str) for part in parts):
        raise TypeError("seed derivation parts must be strings")
    if isinstance(bits, bool) or not isinstance(bits, int):
        raise TypeError("bits must be an integer")
    if bits <= 0 or bits > 256:
        raise ValueError("bits must be between 1 and 256")
    payload = canonical_json_bytes({"master_seed": master_seed, "parts": list(parts)})
    value = int.from_bytes(hashlib.sha256(payload).digest(), "big")
    return value & ((1 << bits) - 1)
