from __future__ import annotations

from enum import Enum


class ProtectedSpanKind(str, Enum):
    URL = "url"
    EMAIL = "email"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    NUMBER = "number"
    DATE = "date"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    CODE = "code"
    MARKDOWN_DESTINATION = "markdown_destination"
    QUOTATION = "quotation"
    POSIX_PATH = "posix_path"
    WINDOWS_PATH = "windows_path"
    CLI_FLAG = "cli_flag"
    CITATION = "citation"
    MATH = "math"
    IDENTIFIER = "identifier"
    USER_MARKED_ENTITY = "user_marked_entity"


class TransformTier(str, Enum):
    FORMAT = "tier_0_format"
    SURFACE = "tier_1_surface"
    LEXICAL = "tier_2_lexical"
    SYNTAX = "tier_3_syntax"
    EXPERIMENTAL = "tier_4_experimental"


class TransformFamily(str, Enum):
    CONTRACTION = "contraction"
    ORTHOGRAPHY = "orthography"
    LEXICAL_TEMPLATE = "lexical_template"
    SYNTAX_TEMPLATE = "syntax_template"


class CandidateRejectionReason(str, Enum):
    PROTECTED_OVERLAP = "protected_overlap"
    QUOTE_POLICY_BLOCKED = "quote_policy_blocked"
    ALL_CAPS_BLOCKED = "all_caps_blocked"
    UNSUPPORTED_CASE = "unsupported_case"
    PRECONDITION_FAILED = "precondition_failed"
    USER_VISIBLE_TEXT_CHANGED = "user_visible_text_changed"
    HARD_INVARIANT_FAILED = "hard_invariant_failed"


class InvariantStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class HardInvariantReason(str, Enum):
    PROTECTED_CONTENT_CHANGED = "protected_content_changed"
    NEGATION_CHANGED = "negation_changed"
    MODALITY_CHANGED = "modality_changed"
