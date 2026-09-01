from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import TextIO

from .product.scan import (
    CATEGORY_DESCRIPTIONS,
    SCAN_CATEGORIES,
    SECURITY_SCAN_CATEGORIES,
    HiddenFinding,
    clean_hidden_characters,
    normalize_scan_categories,
    scan_hidden_characters,
)


LINT_ALGORITHM_VERSION = "fuckmark-lint-v1"
LINT_DEFAULT_CATEGORIES = SECURITY_SCAN_CATEGORIES

LINT_DEFAULT_EXCLUDES = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
)

LINT_DEFAULT_MAX_BYTES = 5_000_000

LINT_EXIT_OK = 0
LINT_EXIT_FINDINGS = 1
LINT_EXIT_USAGE = 2


@dataclass(frozen=True, slots=True)
class FileLintResult:
    path: str
    total: int
    counts: dict[str, int]
    first_locations: tuple[HiddenFinding, ...]
    fixed: bool
    removed: int


def _lint_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fuckmark lint",
        description=(
            "Scan files for hidden or malicious Unicode and fail on findings. "
            "Built for CI, pre-commit, and editors."
        ),
    )
    parser.add_argument("paths", nargs="*", default=["."], metavar="PATH")
    parser.add_argument(
        "--select",
        default=",".join(LINT_DEFAULT_CATEGORIES),
        metavar="CATS",
        help="comma-separated categories to fail on, or 'all' for every category",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="strip the selected hidden characters in place and rewrite the files",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="write a machine-readable JSON report to stdout",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip files matching GLOB (repeatable)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=LINT_DEFAULT_MAX_BYTES,
        metavar="N",
        help=f"skip files larger than N bytes (default {LINT_DEFAULT_MAX_BYTES})",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="only print the summary line",
    )
    return parser


def _resolve_categories(select: str) -> frozenset[str]:
    if select.strip().casefold() == "all":
        return frozenset(SCAN_CATEGORIES)
    names = [item.strip() for item in select.split(",") if item.strip()]
    if not names:
        raise ValueError("no categories selected")
    return normalize_scan_categories(names)


def _is_excluded_dir(name: str, exclude_globs: tuple[str, ...]) -> bool:
    if name in LINT_DEFAULT_EXCLUDES:
        return True
    return any(fnmatch(name, pattern) for pattern in exclude_globs)


def _is_excluded_file(path: Path, exclude_globs: tuple[str, ...]) -> bool:
    posix = path.as_posix()
    return any(fnmatch(path.name, pattern) or fnmatch(posix, pattern) for pattern in exclude_globs)


def _iter_candidate_files(paths: list[str], exclude_globs: tuple[str, ...]) -> list[Path]:
    seen: set[Path] = set()
    ordered: list[Path] = []

    def _add(candidate: Path) -> None:
        resolved = candidate
        if resolved in seen:
            return
        seen.add(resolved)
        ordered.append(resolved)

    for raw in paths:
        base = Path(raw)
        if base.is_symlink():
            continue
        if base.is_file():
            if not _is_excluded_file(base, exclude_globs):
                _add(base)
            continue
        if not base.is_dir():
            continue
        for root, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(name for name in dirs if not _is_excluded_dir(name, exclude_globs))
            for name in sorted(files):
                candidate = Path(root) / name
                if candidate.is_symlink():
                    continue
                if _is_excluded_file(candidate, exclude_globs):
                    continue
                _add(candidate)
    return ordered


def _read_text_file(path: Path, max_bytes: int) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
        return None
    return text


def _write_text_atomic(path: Path, text: str) -> bool:
    parent = path.parent
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return True
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        return False


def _lint_file(path: Path, categories: frozenset[str], text: str, fix: bool) -> FileLintResult:
    scan = scan_hidden_characters(text)
    counts = {name: scan.counts.get(name, 0) for name in scan.active_categories() if name in categories}
    total = sum(counts.values())
    first_locations = tuple(finding for finding in scan.findings if finding.category in categories)[:10]
    fixed = False
    removed = 0
    if fix and total > 0:
        cleaned, removed = clean_hidden_characters(text, categories=categories)
        if cleaned != text and _write_text_atomic(path, cleaned):
            fixed = True
    return FileLintResult(
        path=path.as_posix(),
        total=total,
        counts=counts,
        first_locations=first_locations,
        fixed=fixed,
        removed=removed,
    )


def _emit(output: TextIO, text: str) -> None:
    buffer = getattr(output, "buffer", None)
    if buffer is not None:
        try:
            output.flush()
        except (OSError, ValueError, UnicodeError):
            pass
        buffer.write(text.encode("utf-8"))
        buffer.flush()
        return
    output.write(text)
    output.flush()


def _codepoint_token(codepoint: int) -> str:
    return f"U+{codepoint:04X}"


def _json_report(
    results: list[FileLintResult],
    categories: frozenset[str],
    scanned: int,
    skipped: int,
    fix: bool,
) -> dict[str, object]:
    hits = [result for result in results if result.total > 0]
    return {
        "algorithm_version": LINT_ALGORITHM_VERSION,
        "categories": sorted(categories),
        "fix": fix,
        "files_scanned": scanned,
        "files_skipped": skipped,
        "files_with_findings": len(hits),
        "total_findings": sum(result.total for result in hits),
        "results": [
            {
                "path": result.path,
                "total": result.total,
                "counts": result.counts,
                "fixed": result.fixed,
                "removed": result.removed,
                "locations": [
                    {
                        "index": finding.index,
                        "codepoint": _codepoint_token(finding.codepoint),
                        "category": finding.category,
                        "context": finding.context,
                        "severity": finding.severity,
                        "why": finding.why,
                        "remedy": finding.remedy,
                    }
                    for finding in result.first_locations
                ],
            }
            for result in hits
        ],
    }


def _human_report(
    output: TextIO,
    errors: TextIO,
    results: list[FileLintResult],
    categories: frozenset[str],
    scanned: int,
    skipped: int,
    fix: bool,
    quiet: bool,
) -> None:
    hits = [result for result in results if result.total > 0]
    total_findings = sum(result.total for result in hits)
    if not quiet:
        for result in hits:
            action = " (fixed)" if result.fixed else ""
            counts = ", ".join(f"{name}={result.counts[name]}" for name in result.counts)
            _emit(output, f"{result.path}: {result.total} hidden characters [{counts}]{action}\n")
            for finding in result.first_locations:
                name = CATEGORY_DESCRIPTIONS[finding.category]
                _emit(
                    output,
                    f"    @{finding.index} {_codepoint_token(finding.codepoint)} "
                    f"[{finding.category} {finding.severity}/{finding.context}] {name}\n",
                )
    if hits:
        if fix:
            fixed_files = sum(1 for result in hits if result.fixed)
            summary = (
                f"FuckMark lint: fixed {fixed_files} file(s), "
                f"removed {sum(result.removed for result in hits)} hidden characters "
                f"across {scanned} scanned ({skipped} skipped)."
            )
        else:
            summary = (
                f"FuckMark lint: found {total_findings} hidden characters in "
                f"{len(hits)} of {scanned} file(s) ({skipped} skipped). Run with --fix to strip them."
            )
    else:
        summary = f"FuckMark lint: no hidden characters in {scanned} file(s) ({skipped} skipped)."
    errors.write(summary + "\n")
    errors.flush()


def run_lint_argv(argv: list[str], output: TextIO, errors: TextIO) -> int:
    try:
        arguments = _lint_parser().parse_args(argv)
    except SystemExit as error:
        code = error.code
        if code is None:
            return LINT_EXIT_OK
        return int(code) if isinstance(code, int) else LINT_EXIT_USAGE
    try:
        categories = _resolve_categories(arguments.select)
    except ValueError as error:
        errors.write(f"FuckMark: {error}\n")
        errors.flush()
        return LINT_EXIT_USAGE
    if arguments.max_bytes <= 0:
        errors.write("FuckMark: --max-bytes must be positive\n")
        errors.flush()
        return LINT_EXIT_USAGE

    paths = arguments.paths or ["."]
    exclude_globs = tuple(arguments.exclude)
    candidates = _iter_candidate_files(paths, exclude_globs)

    results: list[FileLintResult] = []
    scanned = 0
    skipped = 0
    for candidate in candidates:
        text = _read_text_file(candidate, arguments.max_bytes)
        if text is None:
            skipped += 1
            continue
        scanned += 1
        results.append(_lint_file(candidate, categories, text, arguments.fix))

    if arguments.json_output:
        report = _json_report(results, categories, scanned, skipped, arguments.fix)
        _emit(output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        _human_report(
            output,
            errors,
            results,
            categories,
            scanned,
            skipped,
            arguments.fix,
            arguments.quiet,
        )

    hits = [result for result in results if result.total > 0]
    if hits:
        return LINT_EXIT_FINDINGS
    return LINT_EXIT_OK
