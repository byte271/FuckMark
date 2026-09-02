from __future__ import annotations

import json
import os
import sys
from ctypes import (
    CDLL,
    POINTER,
    c_char,
    c_char_p,
    c_int32,
    c_uint32,
    create_string_buffer,
    string_at,
)
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_LIB: CDLL | None = None


def _library_candidates() -> list[Path]:
    env = os.environ.get("FUCKMARK_SCAN_LIB", "").strip()
    names = (
        "libfuckmark_scan.so",
        "libfuckmark_scan.dylib",
        "fuckmark_scan.dll",
        "fuckmark_scan.so",
    )
    paths: list[Path] = []
    if env:
        paths.append(Path(env))
    release = _ROOT / "crates" / "fuckmark-scan" / "target" / "release"
    debug = _ROOT / "crates" / "fuckmark-scan" / "target" / "debug"
    for folder in (release, debug):
        for name in names:
            paths.append(folder / name)
    return paths


def library_path() -> Path | None:
    for path in _library_candidates():
        if path.is_file():
            return path
    return None


def load_library() -> CDLL | None:
    global _LIB
    if _LIB is not None:
        return _LIB
    path = library_path()
    if path is None:
        return None
    lib = CDLL(str(path))
    lib.fm_alloc.argtypes = [c_uint32]
    lib.fm_alloc.restype = POINTER(c_char)
    lib.fm_dealloc.argtypes = [POINTER(c_char), c_uint32]
    lib.fm_dealloc.restype = None
    lib.fm_classify.argtypes = [c_uint32]
    lib.fm_classify.restype = c_int32
    lib.fm_scan.argtypes = [
        c_char_p,
        c_uint32,
        c_char_p,
        c_uint32,
        c_char_p,
        c_uint32,
        c_int32,
    ]
    lib.fm_scan.restype = POINTER(c_char)
    lib.fm_clean.argtypes = [c_char_p, c_uint32, c_char_p, c_uint32]
    lib.fm_clean.restype = POINTER(c_char)
    _LIB = lib
    return _LIB


def available() -> bool:
    return load_library() is not None


def _read_packed_json(lib: CDLL, ptr) -> dict:
    if not ptr:
        raise RuntimeError("native scan returned a null pointer")
    header = string_at(ptr, 4)
    length = int.from_bytes(header, "little", signed=False)
    payload = string_at(ptr, 4 + length)[4:]
    lib.fm_dealloc(ptr, c_uint32(4 + length))
    return json.loads(payload.decode("utf-8"))


def _contains_surrogate(text: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in text)


def _scan_via_python(
    text: str,
    *,
    language: str,
    categories: list[str] | None,
    max_findings: int,
) -> dict:
    from .product.scan import SCAN_ALGORITHM_VERSION, scan_hidden_characters

    cap = max(len(text), 1) if max_findings < 0 else max_findings
    full = scan_hidden_characters(text, max_findings=cap, language=language or "auto")
    if categories is None:
        selected = None
    else:
        from .product.scan import normalize_scan_categories

        selected = normalize_scan_categories(categories)
    findings: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    peak = ""
    rank = {"info": 0, "medium": 1, "high": 2, "critical": 3}
    for finding in full.findings:
        if selected is not None and finding.category not in selected:
            continue
        findings.append(
            {
                "index": finding.index,
                "codepoint": finding.codepoint,
                "category": finding.category,
                "context": finding.context,
                "severity": finding.severity,
                "why": finding.why,
                "remedy": finding.remedy,
            }
        )
        counts[finding.category] = counts.get(finding.category, 0) + 1
        if rank.get(finding.severity, -1) > rank.get(peak, -1):
            peak = finding.severity
    return {
        "algorithm_version": SCAN_ALGORITHM_VERSION,
        "source_length": full.source_length,
        "total": len(findings),
        "truncated": full.truncated,
        "highest_severity": peak,
        "counts": counts,
        "findings": findings,
    }


def _clean_via_python(text: str, *, categories: list[str] | None) -> tuple[str, int]:
    from .product.scan import clean_hidden_characters

    return clean_hidden_characters(text, categories=categories)


def classify(codepoint: int) -> str | None:
    lib = load_library()
    if lib is None:
        raise RuntimeError("native fuckmark-scan library is not available")
    if not isinstance(codepoint, int):
        raise TypeError("codepoint must be an int")
    index = int(lib.fm_classify(c_uint32(codepoint & 0xFFFFFFFF)))
    if index < 0:
        return None
    from .product.scan import SCAN_CATEGORIES

    return SCAN_CATEGORIES[index]


def scan_text(
    text: str,
    *,
    language: str = "auto",
    categories: list[str] | None = None,
    max_findings: int = -1,
) -> dict:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if _contains_surrogate(text):
        return _scan_via_python(
            text,
            language=language,
            categories=categories,
            max_findings=max_findings,
        )
    lib = load_library()
    if lib is None:
        raise RuntimeError("native fuckmark-scan library is not available")
    text_bytes = text.encode("utf-8")
    lang_bytes = str(language or "auto").encode("utf-8")
    if categories is None:
        cat_bytes = b"*"
    else:
        cat_bytes = ",".join(categories).encode("utf-8")
    text_buf = create_string_buffer(text_bytes)
    lang_buf = create_string_buffer(lang_bytes)
    cat_buf = create_string_buffer(cat_bytes) if cat_bytes else create_string_buffer(1)
    ptr = lib.fm_scan(
        text_buf,
        c_uint32(len(text_bytes)),
        lang_buf,
        c_uint32(len(lang_bytes)),
        cat_buf,
        c_uint32(len(cat_bytes)),
        c_int32(max_findings),
    )
    return _read_packed_json(lib, ptr)


def clean_text(text: str, *, categories: list[str] | None = None) -> tuple[str, int]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if _contains_surrogate(text):
        return _clean_via_python(text, categories=categories)
    lib = load_library()
    if lib is None:
        raise RuntimeError("native fuckmark-scan library is not available")
    text_bytes = text.encode("utf-8")
    if categories is None:
        cat_bytes = b"*"
    else:
        cat_bytes = ",".join(categories).encode("utf-8")
    text_buf = create_string_buffer(text_bytes)
    cat_buf = create_string_buffer(cat_bytes) if cat_bytes else create_string_buffer(1)
    ptr = lib.fm_clean(
        text_buf,
        c_uint32(len(text_bytes)),
        cat_buf,
        c_uint32(len(cat_bytes)),
    )
    payload = _read_packed_json(lib, ptr)
    return str(payload.get("cleaned", "")), int(payload.get("removed", 0))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not available():
        sys.stderr.write(
            "fuckmark native-scan: library not found; run crates/fuckmark-scan/build-native.sh\n"
        )
        return 1
    text = args[0] if args else "a\u202eb"
    language = args[1] if len(args) > 1 else "auto"
    payload = scan_text(text, language=language)
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
