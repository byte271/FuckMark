from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..hashing import sha256_json, sha256_text
from ..tiny_dev_context_survival_plan_hf import runtime_tokenizer_identity_public
from ..tiny_dev_transform_hf import _attack_samples
from ..transforms import quote_safe_zrd_transform_registry
from .cover_greedy_v4 import (
    COVER_GREEDY_V4_ALGORITHM_VERSION,
    COVER_GREEDY_V4_POLICY_ID,
    schedule_cover_greedy_v4,
)


CYCLE6_CONFIRMATION_CONTRACT_VERSION = "cycle6-confirmation-contract-v1"
CYCLE6_CONFIRMATION_PLAN_VERSION = "cycle6-confirmation-plan-v1"
CYCLE6_CONFIRMATION_AGGREGATE_VERSION = "cycle6-confirmation-aggregate-v1"
CYCLE6_ATTACK_SOURCE_COMMIT = "4a091bde9e8f91cbd9c3feecb4186caa75228c36"
CYCLE6_RULESET_HASH = "f09569fb20f313bc16db7f0e98305c0832ce508ca653546828cfd92c73ef632b"
CYCLE6_TOKENIZER_IDENTITY_HASH = "1be91dc38048d8f69fc45d5fb8175b0edb7c6ec807af1f6b85aa657343dbb95e"
CYCLE6_CONFIRMATION_SEED_BASES = (760_000, 770_000, 780_000)
CYCLE6_BUDGET = 14
CYCLE6_NGRAM_LEN = 5
CYCLE6_THRESHOLD = 0.5570987654320988
CYCLE6_SANITIZER_IDS = ("raw", "nfkc", "cf_strip", "nfkc_cf_strip")
CYCLE6_FROZEN_SOURCE_BLOBS = {
    "fuckmark/transforms/quote_policy.py": "73ac1115e055d978889d6e4a720cd5db39de0dbe",
    "fuckmark/transforms/effectiveness_profile.py": "3bbf15fcbee17c8a8a699821d62d9b521483eb1a",
    "fuckmark/experiments/cover_greedy_v4.py": "d8ea171092e854242cc88f6f0ebfa704e88f9006",
    "fuckmark/sanitizer_robustness.py": "840124b0fad04eefaa2e8e46db5a48d5c077e919",
    "fuckmark/tiny_dev_corpus_hf.py": "8a1c001e90b188fd7b3087519a8d99f76ada6b72",
    "fuckmark/detectors/mean.py": "edd01a2c36ca46c253d29a6382d78b5840e23ff2",
    "fuckmark/native_observations.py": "b6612f14f313bfabda0094f75dd477d342b3e8ed",
}


def _require_mapping(name: str, value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return value


def _git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def validate_cycle6_frozen_source_blobs(
    repository_root: Path,
    contract: Mapping[str, object],
) -> tuple[tuple[str, str], ...]:
    root = Path(repository_root)
    attack = _require_mapping("attack", contract.get("attack"))
    attack_blobs = _require_mapping("attack.source_blobs", attack.get("source_blobs"))
    measurement = _require_mapping("measurement", contract.get("measurement"))
    corpus = _require_mapping("corpus_construction", contract.get("corpus_construction"))
    declared = {
        **{str(path): str(value) for path, value in attack_blobs.items()},
        "fuckmark/sanitizer_robustness.py": str(measurement.get("sanitizer_source_blob")),
        "fuckmark/tiny_dev_corpus_hf.py": str(corpus.get("source_blob")),
        "fuckmark/detectors/mean.py": str(measurement.get("detector_source_blob")),
        "fuckmark/native_observations.py": str(
            measurement.get("native_observations_source_blob")
        ),
    }
    if declared != CYCLE6_FROZEN_SOURCE_BLOBS:
        raise ValueError("Cycle 6 frozen source-blob declarations drifted")
    observed = []
    for relative, expected in sorted(CYCLE6_FROZEN_SOURCE_BLOBS.items()):
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"missing frozen Cycle 6 source file: {relative}")
        actual = _git_blob_sha1(path.read_bytes())
        if actual != expected:
            raise ValueError(f"Cycle 6 frozen source blob drifted: {relative}")
        observed.append((relative, actual))
    return tuple(observed)


def validate_cycle6_confirmation_contract(contract: Mapping[str, object]) -> str:
    if contract.get("algorithm_version") != CYCLE6_CONFIRMATION_CONTRACT_VERSION:
        raise ValueError("unsupported Cycle 6 confirmation contract version")
    attack = _require_mapping("attack", contract.get("attack"))
    if attack.get("implementation_commit") != CYCLE6_ATTACK_SOURCE_COMMIT:
        raise ValueError("Cycle 6 attack implementation commit drifted")
    if attack.get("ruleset_hash") != CYCLE6_RULESET_HASH:
        raise ValueError("Cycle 6 ruleset hash drifted")
    if attack.get("quote_policy_id") != "quote-container-surface-spacing-v1":
        raise ValueError("Cycle 6 quote policy drifted")
    if attack.get("scheduler_algorithm_version") != COVER_GREEDY_V4_ALGORITHM_VERSION:
        raise ValueError("Cycle 6 scheduler algorithm drifted")
    if attack.get("scheduler_policy_id") != COVER_GREEDY_V4_POLICY_ID:
        raise ValueError("Cycle 6 scheduler policy drifted")
    if attack.get("budget") != CYCLE6_BUDGET or attack.get("ngram_len") != CYCLE6_NGRAM_LEN:
        raise ValueError("Cycle 6 budget or n-gram length drifted")
    if attack.get("detector_blind") is not True or attack.get("key_blind") is not True:
        raise ValueError("Cycle 6 access guarantees drifted")

    measurement = _require_mapping("measurement", contract.get("measurement"))
    if measurement.get("model") != "openai-community/gpt2":
        raise ValueError("Cycle 6 confirmation model drifted")
    if measurement.get("model_revision") != "607a30d783dfa663caf39e06633721c8d4cfcd7e":
        raise ValueError("Cycle 6 confirmation model revision drifted")
    if measurement.get("tokenizer_identity_hash") != CYCLE6_TOKENIZER_IDENTITY_HASH:
        raise ValueError("Cycle 6 tokenizer identity drifted")
    if measurement.get("threshold") != CYCLE6_THRESHOLD or measurement.get("comparison") != ">=":
        raise ValueError("Cycle 6 detector threshold identity drifted")
    if measurement.get("target_fpr") != 0.01:
        raise ValueError("Cycle 6 target FPR drifted")
    if tuple(measurement.get("sanitizer_ids", ())) != CYCLE6_SANITIZER_IDS:
        raise ValueError("Cycle 6 sanitizer set drifted")
    if measurement.get("threshold_must_not_be_recalibrated") is not True:
        raise ValueError("Cycle 6 confirmation must preserve the inherited threshold")

    confirmation = _require_mapping("confirmation", contract.get("confirmation"))
    if tuple(confirmation.get("seed_bases", ())) != CYCLE6_CONFIRMATION_SEED_BASES:
        raise ValueError("Cycle 6 confirmation seeds drifted")
    if confirmation.get("attack_rows_per_label_per_corpus") != 64:
        raise ValueError("Cycle 6 confirmation row count drifted")
    if confirmation.get("freeze_before_score") is not True:
        raise ValueError("Cycle 6 plans and corpora must freeze before detector scoring")
    if confirmation.get("cross_corpus_attack_text_hashes_must_be_disjoint") is not True:
        raise ValueError("Cycle 6 confirmation must require disjoint corpora")

    fidelity = _require_mapping("fidelity_gate", contract.get("fidelity_gate"))
    fidelity_status = fidelity.get("status")
    scoring_authorized = confirmation.get("scoring_authorized")
    if fidelity_status == "PENDING_INDEPENDENT_HUMAN_REVIEW":
        if scoring_authorized is not False:
            raise ValueError("Cycle 6 scoring must remain blocked while fidelity is pending")
        if fidelity.get("independent_audit_hash") is not None:
            raise ValueError("pending Cycle 6 fidelity cannot bind a completed audit hash")
    elif fidelity_status == "ACCEPTED_INDEPENDENT_HUMAN_REVIEW":
        if scoring_authorized is not True:
            raise ValueError("accepted Cycle 6 fidelity must explicitly authorize scoring")
        for name in ("full_packet_hash", "independent_audit_hash"):
            value = fidelity.get(name)
            if not isinstance(value, str) or len(value) != 64:
                raise ValueError(f"accepted Cycle 6 fidelity requires {name}")
    else:
        raise ValueError("unsupported Cycle 6 fidelity status")

    claims = _require_mapping("claim_boundary", contract.get("claim_boundary"))
    if claims.get("development_tuning_after_score") is not False:
        raise ValueError("Cycle 6 confirmation forbids post-score tuning")
    if claims.get("universal_watermark_removal_claim") is not False:
        raise ValueError("Cycle 6 confirmation cannot authorize a universal claim")
    return sha256_json(dict(contract))


def _tokenize_source(tokenizer: Any, source: Any) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    if source.text_only_tokens is None:
        raise ValueError(f"sample {source.sample_id} has no text-only token track")
    encoded = tokenizer(source.text, add_special_tokens=False, return_offsets_mapping=True)
    token_ids = tuple(int(value) for value in encoded["input_ids"])
    offsets = tuple((int(start), int(end)) for start, end in encoded["offset_mapping"])
    if token_ids != source.text_only_tokens.token_ids:
        raise ValueError(f"tokenizer replay drifted for {source.sample_id}")
    return token_ids, offsets


def build_cycle6_confirmation_plan(
    corpus: Any,
    tokenizer: Any,
    *,
    source_code_commit: str,
    contract: Mapping[str, object],
) -> dict[str, object]:
    contract_hash = validate_cycle6_confirmation_contract(contract)
    if (
        not isinstance(source_code_commit, str)
        or len(source_code_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_code_commit)
    ):
        raise ValueError("Cycle 6 planning requires a lowercase 40-character commit SHA")
    identity = runtime_tokenizer_identity_public(
        tokenizer,
        str(contract["measurement"]["model"]),
        str(contract["measurement"]["model_revision"]),
    )
    if identity.identity_hash != CYCLE6_TOKENIZER_IDENTITY_HASH:
        raise ValueError("runtime tokenizer identity does not match the frozen contract")
    if corpus.model_identity_hash != identity.identity_hash:
        raise ValueError("corpus tokenizer identity does not match the frozen contract")
    registry = quote_safe_zrd_transform_registry()
    if registry.ruleset_hash != CYCLE6_RULESET_HASH:
        raise ValueError("runtime quote-safe ruleset does not match the frozen contract")
    rows: list[dict[str, object]] = []
    for source in _attack_samples(corpus):
        _tokenize_source(tokenizer, source)
        enumeration = registry.enumerate(source.text)
        plan = schedule_cover_greedy_v4(
            source_sample_id=source.sample_id,
            source_text=source.text,
            registry=registry,
            enumeration=enumeration,
            tokenizer=tokenizer,
            tokenizer_identity_hash=identity.identity_hash,
            ngram_len=CYCLE6_NGRAM_LEN,
            budget=CYCLE6_BUDGET,
        )
        transformed = registry.apply(enumeration, plan.selected_candidate_ids).output_text
        row = {
            "source_sample_id": source.sample_id,
            "source_label": source.label.value,
            "domain": source.domain.value,
            "source_text_hash": source.text_sha256,
            "enumeration_hash": enumeration.enumeration_hash,
            "candidate_count": plan.candidate_count,
            "selected_candidate_ids": plan.selected_candidate_ids,
            "selected_operation_count": plan.selected_candidate_count,
            "repair_selection_count": plan.repair_phase_selections,
            "budget_exhausted": plan.budget_exhausted,
            "root_window_count": plan.root_window_count,
            "intact_window_count": plan.intact_window_count,
            "tuple_leak_window_count": plan.tuple_leak_window_count,
            "closure_free": plan.closure_free,
            "conflict_excluded_candidate_count": len(plan.conflict_excluded_candidate_ids),
            "transformed_text": transformed,
            "transformed_text_hash": sha256_text(transformed),
            "transform_trace_hash": plan.transform_trace_hash,
            "scheduler_result_hash": plan.result_hash,
            "detector_access_observed": plan.detector_access_observed,
            "secret_access_observed": plan.secret_access_observed,
        }
        rows.append({**row, "row_hash": sha256_json(row)})
    if len(rows) != 128:
        raise ValueError("Cycle 6 confirmation plan requires 128 attack rows")
    payload = {
        "algorithm_version": CYCLE6_CONFIRMATION_PLAN_VERSION,
        "contract_hash": contract_hash,
        "source_code_commit": source_code_commit,
        "tiny_dev_artifact_hash": corpus.artifact_hash,
        "corpus_manifest_hash": corpus.manifest.manifest_hash,
        "ruleset_hash": registry.ruleset_hash,
        "quote_policy_id": registry.quote_policy_id,
        "scheduler_algorithm_version": COVER_GREEDY_V4_ALGORITHM_VERSION,
        "scheduler_policy_id": COVER_GREEDY_V4_POLICY_ID,
        "tokenizer_identity_hash": identity.identity_hash,
        "budget": CYCLE6_BUDGET,
        "ngram_len": CYCLE6_NGRAM_LEN,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "rows": tuple(rows),
    }
    return {**payload, "plan_hash": sha256_json(payload)}


def validate_cycle6_confirmation_plan(
    plan: Mapping[str, object],
    corpus: Any,
    *,
    contract: Mapping[str, object],
) -> str:
    contract_hash = validate_cycle6_confirmation_contract(contract)
    if plan.get("algorithm_version") != CYCLE6_CONFIRMATION_PLAN_VERSION:
        raise ValueError("unsupported Cycle 6 confirmation plan version")
    source_code_commit = plan.get("source_code_commit")
    if (
        not isinstance(source_code_commit, str)
        or len(source_code_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_code_commit)
    ):
        raise ValueError("Cycle 6 plan source commit is invalid")
    if plan.get("contract_hash") != contract_hash:
        raise ValueError("Cycle 6 plan contract binding drifted")
    if plan.get("tiny_dev_artifact_hash") != corpus.artifact_hash:
        raise ValueError("Cycle 6 plan corpus binding drifted")
    if plan.get("corpus_manifest_hash") != corpus.manifest.manifest_hash:
        raise ValueError("Cycle 6 plan manifest binding drifted")
    if plan.get("ruleset_hash") != CYCLE6_RULESET_HASH:
        raise ValueError("Cycle 6 plan ruleset drifted")
    if plan.get("tokenizer_identity_hash") != CYCLE6_TOKENIZER_IDENTITY_HASH:
        raise ValueError("Cycle 6 plan tokenizer identity drifted")
    if plan.get("budget") != CYCLE6_BUDGET or plan.get("ngram_len") != CYCLE6_NGRAM_LEN:
        raise ValueError("Cycle 6 plan geometry identity drifted")
    if plan.get("detector_access_observed") is not False or plan.get("secret_access_observed") is not False:
        raise ValueError("Cycle 6 plan access attestation drifted")
    rows = plan.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or len(rows) != 128:
        raise ValueError("Cycle 6 plan must contain exactly 128 rows")
    sources = {source.sample_id: source for source in _attack_samples(corpus)}
    if any(not isinstance(row, Mapping) for row in rows):
        raise TypeError("Cycle 6 plan rows must be mappings")
    if set(sources) != {str(row["source_sample_id"]) for row in rows}:
        raise ValueError("Cycle 6 plan does not cover the full attack split")
    for row in rows:
        source = sources[str(row["source_sample_id"])]
        if row.get("source_text_hash") != source.text_sha256:
            raise ValueError("Cycle 6 plan source binding drifted")
        row_payload = {key: value for key, value in row.items() if key != "row_hash"}
        if row.get("row_hash") != sha256_json(row_payload):
            raise ValueError("Cycle 6 plan row hash drifted")
        if row.get("transformed_text_hash") != sha256_text(str(row["transformed_text"])):
            raise ValueError("Cycle 6 transformed text hash drifted")
        if row.get("detector_access_observed") is not False or row.get("secret_access_observed") is not False:
            raise ValueError("Cycle 6 plan row access attestation drifted")
    payload = {key: value for key, value in plan.items() if key != "plan_hash"}
    expected = sha256_json(payload)
    if plan.get("plan_hash") != expected:
        raise ValueError("Cycle 6 plan hash drifted")
    return expected


def _validate_evidence_artifact(
    item: Mapping[str, object],
    *,
    contract_hash: str,
) -> tuple[set[str], Mapping[str, object], Mapping[str, object]]:
    if item.get("algorithm_version") != "cycle6-confirmation-evidence-v1":
        raise ValueError("unsupported Cycle 6 confirmation evidence version")
    payload = {key: value for key, value in item.items() if key != "artifact_hash"}
    if item.get("artifact_hash") != sha256_json(payload):
        raise ValueError("Cycle 6 evidence artifact hash drifted")
    if item.get("contract_hash") != contract_hash:
        raise ValueError("Cycle 6 evidence contract binding drifted")
    if item.get("selection_detector_access_observed") is not False:
        raise ValueError("Cycle 6 evidence reports detector access during selection")
    if item.get("selection_secret_access_observed") is not False:
        raise ValueError("Cycle 6 evidence reports secret access during selection")
    rows = item.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or len(rows) != 128:
        raise ValueError("Cycle 6 evidence must contain exactly 128 rows")
    sample_ids: set[str] = set()
    source_hashes: set[str] = set()
    label_counts = {"watermarked": 0, "unwatermarked": 0}
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("Cycle 6 evidence rows must be mappings")
        row_payload = {key: value for key, value in row.items() if key != "row_hash"}
        if row.get("row_hash") != sha256_json(row_payload):
            raise ValueError("Cycle 6 evidence row hash drifted")
        sample_id = str(row.get("source_sample_id"))
        if sample_id in sample_ids:
            raise ValueError("Cycle 6 evidence sample IDs must be unique")
        sample_ids.add(sample_id)
        source_hash = str(row.get("source_text_hash"))
        if source_hash in source_hashes:
            raise ValueError("Cycle 6 evidence source text hashes must be unique")
        source_hashes.add(source_hash)
        label = str(row.get("source_label"))
        if label not in label_counts:
            raise ValueError("Cycle 6 evidence contains an unknown source label")
        label_counts[label] += 1
        sanitizers = row.get("sanitizers")
        if not isinstance(sanitizers, Mapping) or tuple(sanitizers) != CYCLE6_SANITIZER_IDS:
            raise ValueError("Cycle 6 evidence row sanitizer order drifted")
    if label_counts != {"watermarked": 64, "unwatermarked": 64}:
        raise ValueError("Cycle 6 evidence must contain 64 rows per label")
    summaries = item.get("summaries")
    if not isinstance(summaries, Sequence) or isinstance(summaries, (str, bytes)):
        raise TypeError("Cycle 6 evidence summaries must be a sequence")
    by_label: dict[str, Mapping[str, object]] = {}
    for summary in summaries:
        if not isinstance(summary, Mapping):
            raise TypeError("Cycle 6 evidence summaries must be mappings")
        summary_payload = {key: value for key, value in summary.items() if key != "summary_hash"}
        if summary.get("summary_hash") != sha256_json(summary_payload):
            raise ValueError("Cycle 6 evidence summary hash drifted")
        by_label[str(summary.get("source_label"))] = summary
    if set(by_label) != set(label_counts):
        raise ValueError("Cycle 6 evidence summaries must cover both source labels")
    for label, summary in by_label.items():
        selected = tuple(row for row in rows if row.get("source_label") == label)
        expected_counts = tuple(
            sum(bool(row["sanitizers"][variant]["detected"]) for row in selected)
            for variant in CYCLE6_SANITIZER_IDS
        )
        if tuple(summary.get("detected_per_sanitizer", ())) != expected_counts:
            raise ValueError("Cycle 6 evidence summary detection counts drifted")
        pristine = sum(bool(row.get("pristine_detected")) for row in selected)
        if summary.get("pristine_detected_count") != pristine:
            raise ValueError("Cycle 6 evidence pristine summary drifted")
    return source_hashes, by_label["watermarked"], by_label["unwatermarked"]


def classify_cycle6_confirmation(per_corpus: Sequence[Mapping[str, object]]) -> str:
    if len(per_corpus) != 3:
        raise ValueError("Cycle 6 confirmation requires three corpora")
    if any(int(row["pristine_watermarked_detected_count"]) < 60 for row in per_corpus):
        return "INVALID_CONTROL"
    if all(
        all(int(value) == 0 for value in row["watermarked_detected_per_sanitizer"])
        for row in per_corpus
    ):
        return "ZERO_RESIDUAL"
    return "NONZERO_RESIDUAL"


def aggregate_cycle6_confirmation(
    evidence: Sequence[Mapping[str, object]],
    *,
    contract: Mapping[str, object],
) -> dict[str, object]:
    contract_hash = validate_cycle6_confirmation_contract(contract)
    if len(evidence) != 3:
        raise ValueError("Cycle 6 confirmation aggregate requires three evidence artifacts")
    seeds = tuple(sorted(int(item["confirmation_seed_base"]) for item in evidence))
    if seeds != CYCLE6_CONFIRMATION_SEED_BASES:
        raise ValueError("Cycle 6 evidence seeds do not match the frozen contract")
    if len({str(item["tiny_dev_artifact_hash"]) for item in evidence}) != 3:
        raise ValueError("Cycle 6 confirmation requires three distinct corpus artifacts")
    stable = (
        "contract_hash",
        "ruleset_hash",
        "tokenizer_identity_hash",
        "measurement_identity",
        "threshold",
        "threshold_comparison",
        "threshold_target_fpr",
        "prior_fixed_threshold_file_sha256",
        "sanitizer_ids",
        "adapter_configuration_fingerprint",
        "adapter_source_commit",
        "sampling_table_hash",
    )
    first = evidence[0]
    for field in stable:
        if any(item.get(field) != first.get(field) for item in evidence[1:]):
            raise ValueError(f"Cycle 6 evidence {field} drifted across corpora")
    measurement = _require_mapping("measurement", contract.get("measurement"))
    expected_stable = {
        "ruleset_hash": CYCLE6_RULESET_HASH,
        "tokenizer_identity_hash": CYCLE6_TOKENIZER_IDENTITY_HASH,
        "measurement_identity": measurement.get("identity"),
        "threshold": CYCLE6_THRESHOLD,
        "threshold_comparison": ">=",
        "threshold_target_fpr": 0.01,
        "prior_fixed_threshold_file_sha256": measurement.get(
            "prior_fixed_threshold_file_sha256"
        ),
        "sanitizer_ids": CYCLE6_SANITIZER_IDS,
        "adapter_source_commit": measurement.get("transformers_source_commit"),
    }
    for field, expected in expected_stable.items():
        if first.get(field) != expected:
            raise ValueError(f"Cycle 6 evidence {field} drifted from the frozen contract")
    source_hash_sets: list[set[str]] = []
    validated_summaries: dict[int, tuple[Mapping[str, object], Mapping[str, object]]] = {}
    for item in evidence:
        source_hashes, watermarked, unwatermarked = _validate_evidence_artifact(
            item,
            contract_hash=contract_hash,
        )
        source_hash_sets.append(source_hashes)
        validated_summaries[int(item["confirmation_seed_base"])] = (
            watermarked,
            unwatermarked,
        )
    for index, left in enumerate(source_hash_sets):
        for right in source_hash_sets[index + 1 :]:
            if left & right:
                raise ValueError("Cycle 6 confirmation attack texts overlap across corpora")
    per_corpus: list[dict[str, object]] = []
    for item in sorted(evidence, key=lambda value: int(value["confirmation_seed_base"])):
        watermarked, unwatermarked = validated_summaries[int(item["confirmation_seed_base"])]
        row = {
            "confirmation_seed_base": item["confirmation_seed_base"],
            "artifact_hash": item["artifact_hash"],
            "corpus_artifact_hash": item["tiny_dev_artifact_hash"],
            "pristine_watermarked_detected_count": watermarked["pristine_detected_count"],
            "watermarked_detected_per_sanitizer": watermarked["detected_per_sanitizer"],
            "unwatermarked_detected_per_sanitizer": unwatermarked["detected_per_sanitizer"],
            "watermarked_mean_score_per_sanitizer": watermarked["mean_score_per_sanitizer"],
            "unwatermarked_mean_score_per_sanitizer": unwatermarked["mean_score_per_sanitizer"],
        }
        per_corpus.append({**row, "row_hash": sha256_json(row)})
    outcome = classify_cycle6_confirmation(per_corpus)
    pooled_watermarked = tuple(
        sum(int(row["watermarked_detected_per_sanitizer"][index]) for row in per_corpus)
        for index in range(len(CYCLE6_SANITIZER_IDS))
    )
    pooled_unwatermarked = tuple(
        sum(int(row["unwatermarked_detected_per_sanitizer"][index]) for row in per_corpus)
        for index in range(len(CYCLE6_SANITIZER_IDS))
    )
    pooled = {
        "watermarked_row_count": 192,
        "unwatermarked_row_count": 192,
        "watermarked_detected_per_sanitizer": pooled_watermarked,
        "unwatermarked_detected_per_sanitizer": pooled_unwatermarked,
        "sanitizer_ids": CYCLE6_SANITIZER_IDS,
    }
    payload = {
        "algorithm_version": CYCLE6_CONFIRMATION_AGGREGATE_VERSION,
        "contract_hash": contract_hash,
        "outcome": outcome,
        "per_corpus": tuple(per_corpus),
        "pooled": {**pooled, "pooled_hash": sha256_json(pooled)},
        "selection_frozen_before_scoring": True,
        "detector_access_used_for_selection": False,
        "secret_access_used_for_selection": False,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}
