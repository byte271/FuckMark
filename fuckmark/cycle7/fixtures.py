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

FORMAT_RICH = (
    "Careful testing matters before any claim becomes knowledge. "
    "Independent replication remains required after the first success. "
    "Does this protocol still hold? Next measurements decide. "
    "Stop! Further edits stay local."
)

COMPLEMENTIZER_RICH = (
    "I think that the protocol works, and we believe that a replica will fail. "
    "They know that this check is required. I think the second copy is weaker."
)

PRENOMINAL_RICH = (
    "A well known method needs long term logs and high quality checks. "
    "Open source tools help large scale runs."
)

PARENTHETICAL_RICH = (
    "The first replica failed, however, the second replica passed. "
    "The threshold stayed fixed, therefore, the decision remained."
)

COORD_COMMA_RICH = (
    "The first replica failed, and the second replica passed. "
    "The logs were short but the notes were complete or the run stopped."
)

CLAUSE_PUNCT_RICH = (
    "The first replica failed, and the second replica passed; the notes stayed. "
    "Protocol: The threshold stayed fixed, so the decision remained."
)

QUANTIFIER_RICH = (
    "All of the replicas failed and both of these logs were empty. "
    "Half the notes stayed and all my checks passed."
)

WORD_BOUNDARY_RICH = (
    "Measurement protocol remains fixed across independent replications of the "
    "same experimental apparatus. Calibration uses a held-out population."
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


def stage_b_fixture_samples() -> tuple[tuple[str, str], ...]:
    return (
        ("format-rich", FORMAT_RICH),
        ("complementizer-rich", COMPLEMENTIZER_RICH),
        ("prenominal-rich", PRENOMINAL_RICH),
        ("parenthetical-rich", PARENTHETICAL_RICH),
        ("coord-comma-rich", COORD_COMMA_RICH),
        ("contraction-rich", CONTRACTION_RICH),
        ("contraction-sparse", CONTRACTION_SPARSE),
    )


def stage_c_fixture_samples() -> tuple[tuple[str, str], ...]:
    return (
        *stage_b_fixture_samples(),
        ("clause-punct-rich", CLAUSE_PUNCT_RICH),
        ("quantifier-rich", QUANTIFIER_RICH),
    )


def stage_d_fixture_samples() -> tuple[tuple[str, str], ...]:
    return (
        *stage_c_fixture_samples(),
        ("word-boundary-rich", WORD_BOUNDARY_RICH),
    )


def rejection_reason_values() -> tuple[str, ...]:
    return tuple(reason.value for reason in CandidateRejectionReason)
