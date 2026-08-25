from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from ..hashing import sha256_json, sha256_text
from .protected import ProtectedSpanExtractor
from .protected_artifacts import PROTECTED_INVARIANT_ALGORITHM_VERSION, InvariantDifference, ProtectedInvariantReport, ProtectedSpanManifest, UserProtectedRange
from .schema import InvariantStatus, ProtectedSpanKind


def _invariant_counter(manifest: ProtectedSpanManifest) -> Counter[tuple[str, str]]:
    counter: Counter[tuple[str, str]] = Counter()
    for span in manifest.spans:
        for kind in span.kinds:
            if kind is not ProtectedSpanKind.USER_MARKED_ENTITY:
                counter[(kind.value, span.exact_text)] += 1
    return counter


def validate_protected_invariants(
    original: str,
    transformed: str,
    identifiers: Sequence[str] = (),
    user_ranges: Sequence[UserProtectedRange] = (),
    *,
    include_quotations: bool = True,
) -> ProtectedInvariantReport:
    if not isinstance(original, str) or not isinstance(transformed, str):
        raise TypeError("original and transformed must be strings")
    materialized_ranges = tuple(user_ranges)
    extractor = ProtectedSpanExtractor(identifiers)
    original_manifest = extractor.extract(
        original,
        materialized_ranges,
        include_quotations=include_quotations,
    )
    transformed_manifest = extractor.extract(
        transformed,
        include_quotations=include_quotations,
    )
    original_counter = _invariant_counter(original_manifest)
    transformed_counter = _invariant_counter(transformed_manifest)
    user_texts = tuple(original[value.start:value.end] for value in original_manifest.user_ranges)
    for exact_text in user_texts:
        original_counter[(ProtectedSpanKind.USER_MARKED_ENTITY.value, exact_text)] = original.count(exact_text)
        transformed_counter[(ProtectedSpanKind.USER_MARKED_ENTITY.value, exact_text)] = transformed.count(exact_text)
    keys = sorted(set(original_counter) | set(transformed_counter))
    differences = tuple(InvariantDifference(ProtectedSpanKind(kind), exact_text, original_counter[(kind, exact_text)], transformed_counter[(kind, exact_text)]) for kind, exact_text in keys if original_counter[(kind, exact_text)] != transformed_counter[(kind, exact_text)])
    status = InvariantStatus.PASS if not differences else InvariantStatus.FAIL
    original_hash = sha256_text(original)
    transformed_hash = sha256_text(transformed)
    payload = {"algorithm_version": PROTECTED_INVARIANT_ALGORITHM_VERSION, "status": status.value, "original_hash": original_hash, "transformed_hash": transformed_hash, "original_manifest_hash": original_manifest.manifest_hash, "transformed_manifest_hash": transformed_manifest.manifest_hash, "differences": differences}
    return ProtectedInvariantReport(status, original_hash, transformed_hash, differences, sha256_json(payload), original_manifest.manifest_hash, transformed_manifest.manifest_hash)
