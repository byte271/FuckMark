__project_name__ = "FuckMark"
__version__ = "0.1.0"

from .alignment import (
    AlignmentOp,
    AlignmentResult,
    AlignmentStep,
    align_tokens,
    conserved_runs,
    validate_alignment,
)
from .config import canonical_json_bytes, canonical_json_text, canonicalize
from .coverage import Interval, merge_intervals, substitution_observation_interval, union_size
from .hashing import derive_seed, sha256_bytes, sha256_file, sha256_json, sha256_text
from .observations import (
    StructuralObservationDiff,
    StructuralObservationState,
    StructuralObservationSummary,
    TokenNgram,
    build_token_ngrams,
    structural_observation_diff,
    summarize_structural_observations,
)
from .types import RunIdentity, SourcePin

__all__ = [
    "__project_name__",
    "__version__",
    "AlignmentOp",
    "AlignmentResult",
    "AlignmentStep",
    "Interval",
    "RunIdentity",
    "SourcePin",
    "StructuralObservationDiff",
    "StructuralObservationState",
    "StructuralObservationSummary",
    "TokenNgram",
    "align_tokens",
    "build_token_ngrams",
    "canonical_json_bytes",
    "canonical_json_text",
    "canonicalize",
    "conserved_runs",
    "derive_seed",
    "merge_intervals",
    "sha256_bytes",
    "sha256_file",
    "sha256_json",
    "sha256_text",
    "structural_observation_diff",
    "substitution_observation_interval",
    "summarize_structural_observations",
    "union_size",
    "validate_alignment",
]
