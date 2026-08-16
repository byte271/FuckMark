from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from .._validation import require_sha256
from ..adapters import DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN
from ..corpus import ModelTokenizerIdentity
from ..detectors import UncalibratedDetectorEvidence, verify_calibration_bundle
from ..transforms.fidelity_readiness import verify_task29_fidelity_readiness
from ..transforms.fidelity_verification import LexicalPromotionEvidence
from ..transforms.syntax_fidelity_verification import SyntaxDevelopmentEvidence
from .confirmatory import ConfirmatoryPreregistration


class ConfirmatoryPreflightVerificationError(ValueError):
    pass


def _canonical_source_pins():
    return tuple(
        sorted(
            (DEEPMIND_REFERENCE_SOURCE_PIN, HUGGINGFACE_SYNTHID_SOURCE_PIN),
            key=lambda value: (value.source_id, value.repository, value.commit),
        )
    )


def verify_confirmatory_preregistration(
    preregistration: ConfirmatoryPreregistration,
    *,
    code_commit: str,
    spec_revision_hash: str,
    power_analysis_hash: str,
    budget_config_hash: str,
    verification_test_hashes: Sequence[str],
    model_tokenizers: Sequence[ModelTokenizerIdentity],
    calibration_negative_evidence: Mapping[str, Sequence[UncalibratedDetectorEvidence]],
    sealed_test_key_hash: str,
    sealed_test_corpus_hash: str,
    task29_lexical_evidence: Sequence[LexicalPromotionEvidence] = (),
    task29_syntax_evidence: Sequence[SyntaxDevelopmentEvidence] = (),
    task29_tokenizers: Mapping[str, Callable[[str], Sequence[int]]] | None = None,
) -> None:
    if not isinstance(preregistration, ConfirmatoryPreregistration):
        raise TypeError("preregistration must be a ConfirmatoryPreregistration")
    if preregistration.source_pins != _canonical_source_pins():
        raise ConfirmatoryPreflightVerificationError(
            "confirmatory source pins do not match the currently pinned open-source revisions"
        )
    if code_commit != preregistration.code_commit:
        raise ConfirmatoryPreflightVerificationError("code commit does not match preregistration")
    for name, actual, expected in (
        ("spec revision hash", spec_revision_hash, preregistration.spec_revision_hash),
        ("power analysis hash", power_analysis_hash, preregistration.power_analysis_hash),
        ("budget config hash", budget_config_hash, preregistration.budget_config_hash),
        ("sealed test-key hash", sealed_test_key_hash, preregistration.sealed_test_key_hash),
        ("sealed test-corpus hash", sealed_test_corpus_hash, preregistration.sealed_test_corpus_hash),
    ):
        require_sha256(name, actual)
        if actual != expected:
            raise ConfirmatoryPreflightVerificationError(f"{name} does not match preregistration")
    runtime_models = tuple(sorted(tuple(model_tokenizers), key=lambda value: value.identity_hash if isinstance(value, ModelTokenizerIdentity) else ""))
    if any(not isinstance(value, ModelTokenizerIdentity) for value in runtime_models):
        raise TypeError("model_tokenizers must contain ModelTokenizerIdentity values")
    if runtime_models != preregistration.model_tokenizers:
        raise ConfirmatoryPreflightVerificationError(
            "runtime model/tokenizer identities do not match preregistration"
        )
    test_hashes = tuple(verification_test_hashes)
    for value in test_hashes:
        require_sha256("verification test hash", value)
    if test_hashes != preregistration.verification_test_hashes:
        raise ConfirmatoryPreflightVerificationError(
            "verification test hashes do not match preregistration"
        )
    evidence_map = dict(calibration_negative_evidence)
    expected_bundle_hashes = {value.bundle_hash for value in preregistration.calibration_bundles}
    if set(evidence_map) != expected_bundle_hashes:
        raise ConfirmatoryPreflightVerificationError(
            "calibration replay evidence must exactly cover preregistered bundles"
        )
    for bundle in preregistration.calibration_bundles:
        rows = evidence_map[bundle.bundle_hash]
        try:
            verify_calibration_bundle(rows, bundle)
        except Exception as error:
            raise ConfirmatoryPreflightVerificationError(
                f"calibration bundle {bundle.bundle_hash} does not replay from supplied negative evidence"
            ) from error
    selected_rule_hashes = tuple(value.rule_hash for value in preregistration.task29_readiness.selected_rows)
    try:
        verify_task29_fidelity_readiness(
            preregistration.task29_readiness,
            lexical_evidence=task29_lexical_evidence,
            syntax_evidence=task29_syntax_evidence,
            tokenizers=task29_tokenizers,
            confirmatory_rule_hashes=selected_rule_hashes,
        )
    except Exception as error:
        raise ConfirmatoryPreflightVerificationError(
            "Task 29 fidelity readiness does not replay from supplied source-grounded evidence"
        ) from error
