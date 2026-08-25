from __future__ import annotations

from ..transforms.schema import CandidateRejectionReason


CYCLE7_FIXTURE_SET_ID = "cycle7-stage-a-fixtures-v1"

CONTRACTION_RICH = (
    "They are not ready, and we do not stop when the system is in use. "
    "You cannot wait, and I am sure they have time. The path towards the lab "
    "is amongst the remaining options. She said, \"Do not quote this change.\" "
    "See https://example.com/path and 12.5% on 2024-08-25. Run `code_sample` "
    "and pass --verbose. Contact lab@example.com. Cite [1] and (Smith, 2024). "
    "Hash deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef. "
    "Path /usr/bin/true and C:\\Windows\\System32\\drivers. Identifier CamelCaseThing."
)

CONTRACTION_SPARSE = (
    "Measurement protocol remains fixed across independent replications of the "
    "same experimental apparatus. Calibration uses a held-out population."
)

COMPOUND_RICH = (
    "A proof of concept and a point of view need step-by-step checks. "
    "State of the art methods stay face to face with case-by-case review."
)

QUOTE_INTERIOR = 'He answered, "They are not finished and we do not agree."'

AMBIGUOUS_NEGATIVES = (
    "He'd already left before the meeting started.",
    "It's time for the measurement to begin.",
    "Let us know when the run completes.",
)

PROTECTED_CASES = (
    ("url", "Visit https://example.com/do-not-touch and continue."),
    ("number", "The value 12 is exact and we do not round it."),
    ("date", "On 2024-08-25 we do not change the timestamp."),
    ("code", "Run `do not` as a literal command token."),
    ("identifier", "Keep CamelCaseThing intact while they are waiting."),
    ("posix_path", "The binary /usr/bin/true cannot be rewritten."),
    ("windows_path", "File C:\\Windows\\System32\\drivers cannot be rewritten."),
    ("hash", "Digest deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef is fixed."),
    ("citation", "Prior work [1] cannot be silently altered."),
    ("email", "Write lab@example.com if they are delayed."),
)


def fixture_samples() -> tuple[tuple[str, str], ...]:
    return (
        ("contraction-rich", CONTRACTION_RICH),
        ("contraction-sparse", CONTRACTION_SPARSE),
        ("compound-rich", COMPOUND_RICH),
        ("quote-interior", QUOTE_INTERIOR),
    )


def rejection_reason_values() -> tuple[str, ...]:
    return tuple(reason.value for reason in CandidateRejectionReason)
