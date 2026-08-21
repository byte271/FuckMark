from __future__ import annotations

import json
import re
from pathlib import Path

from .._validation import require_bool, require_int, require_sha256
from ..hashing import sha256_json
from ..transforms.contractions import context_survival_contraction_rules
from ..transforms.durable_rules import development_durable_surface_rules
from ..transforms.registry import TransformRegistry, durable_portfolio_transform_registry
from ..transforms.surface_rules import development_surface_rules
from .normalization_survival import (
    N4_COPY_PASTE_WHITESPACE,
    NORMALIZATION_SURVIVAL_BUDGETS,
    load_normalization_survival_benchmark,
    normalization_profiles,
)


DURABLE_PORTFOLIO_COMPARISON_VERSION = "durable-portfolio-comparison-v1"
DURABLE_PORTFOLIO_MINIMUM_INDEPENDENT_N4_RELATIVE_GAIN = 0.1
DURABLE_PORTFOLIO_RELEASE_STATUS = "DEVELOPMENT_ONLY_FIDELITY_EVIDENCE_REQUIRED"
DURABLE_PORTFOLIO_SUCCESS = "MATERIAL_DURABLE_OPPORTUNITY_INCREASE"
DURABLE_PORTFOLIO_REJECT = "NO_MATERIAL_DURABLE_OPPORTUNITY_INCREASE"
_DURABLE_PORTFOLIO_SCOPE = (
    "Detector-blind development opportunity comparison; no detector effect or "
    "release authorization"
)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _context_baseline_registry() -> TransformRegistry:
    return TransformRegistry(
        (*context_survival_contraction_rules(), *development_surface_rules())
    )


def _sample_profile(sample: dict[str, object], profile_id: str) -> dict[str, object]:
    profiles = sample["profiles"]
    if not isinstance(profiles, list):
        raise TypeError("normalization sample profiles must be a list")
    matching = tuple(value for value in profiles if value["profile_id"] == profile_id)
    if len(matching) != 1:
        raise ValueError("normalization sample profile identity is incomplete")
    return matching[0]


def _sample_witnesses(
    benchmark: dict[str, object],
    profile_id: str,
) -> dict[tuple[str, int], bool]:
    output = {}
    for sample in benchmark["sample_summaries"]:
        profile = _sample_profile(sample, profile_id)
        for witness in profile["witnesses"]:
            key = (sample["sample_id"], witness["budget"])
            if key in output:
                raise ValueError("normalization witness identity is duplicated")
            output[key] = witness["reachable"]
    return output


def _n4_totals(benchmark: dict[str, object]) -> tuple[int, int]:
    surviving = 0
    independent = 0
    for sample in benchmark["sample_summaries"]:
        profile = _sample_profile(sample, N4_COPY_PASTE_WHITESPACE)
        surviving += profile["invariant_safe_surviving_count"]
        independent += profile["independent_invariant_safe_surviving_count"]
    return surviving, independent


def _raw_totals(benchmark: dict[str, object]) -> tuple[int, int, int]:
    raw = sum(value["raw_candidate_count"] for value in benchmark["sample_summaries"])
    safe = sum(value["invariant_safe_count"] for value in benchmark["sample_summaries"])
    independent_safe = sum(
        value["independent_invariant_safe_count"]
        for value in benchmark["sample_summaries"]
    )
    return raw, safe, independent_safe


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _new_rule_rows(
    portfolio: dict[str, object],
    new_rule_ids: set[str],
) -> tuple[dict[str, object], ...]:
    return tuple(
        value
        for value in portfolio["rule_summaries"]
        if value["profile_id"] == N4_COPY_PASTE_WHITESPACE
        and value["rule_id"] in new_rule_ids
    )


def _new_rule_declarations() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "rule_id": value.rule_id,
            "rule_hash": value.rule_hash,
            "construction": value.construction.value,
            "family": value.family.value,
            "tier": value.tier.value,
        }
        for value in sorted(
            development_durable_surface_rules(), key=lambda item: item.rule_id
        )
    )


def _normalization_status(row: dict[str, object] | None) -> str:
    if row is None:
        return "NOT_OBSERVED"
    if row["invariant_safe_count"] == 0:
        return "NO_INVARIANT_SAFE_OBSERVATION"
    if row["invariant_safe_count"] == row["invariant_safe_surviving_count"]:
        return "PASS"
    return "FAIL"


def compare_durable_portfolio_benchmarks(
    baseline_path: Path,
    portfolio_path: Path,
) -> dict[str, object]:
    baseline = load_normalization_survival_benchmark(baseline_path)
    portfolio = load_normalization_survival_benchmark(portfolio_path)
    shared_names = (
        "benchmark_source_code_commit",
        "source_corpus_commit",
        "source_corpus_hash",
        "source_workflow_run_id",
        "source_sample_count",
        "source_samples_per_target_length",
        "normalization_profiles",
        "budgets",
    )
    if any(baseline[name] != portfolio[name] for name in shared_names):
        raise ValueError("durable portfolio inputs do not share one frozen benchmark source")
    baseline_registry = _context_baseline_registry()
    portfolio_registry = durable_portfolio_transform_registry()
    if baseline["ruleset_hash"] != baseline_registry.ruleset_hash:
        raise ValueError("durable portfolio baseline ruleset drifted")
    if portfolio["ruleset_hash"] != portfolio_registry.ruleset_hash:
        raise ValueError("durable portfolio candidate ruleset drifted")
    durable_rules = development_durable_surface_rules()
    new_rule_ids = {value.rule_id for value in durable_rules}
    baseline_row_hashes = {value["row_hash"] for value in baseline["candidate_rows"]}
    portfolio_row_hashes = {value["row_hash"] for value in portfolio["candidate_rows"]}
    missing_baseline_rows = baseline_row_hashes - portfolio_row_hashes
    if missing_baseline_rows:
        raise ValueError("durable portfolio removed or mutated a baseline candidate row")
    added_rows = tuple(
        value
        for value in portfolio["candidate_rows"]
        if value["row_hash"] not in baseline_row_hashes
    )
    if any(value["rule_id"] not in new_rule_ids for value in added_rows):
        raise ValueError("durable portfolio contains an unattributed added candidate row")
    if len(portfolio_row_hashes) - len(baseline_row_hashes) != len(added_rows):
        raise ValueError("durable portfolio candidate row identities are duplicated")
    baseline_raw, baseline_safe, baseline_independent_safe = _raw_totals(baseline)
    portfolio_raw, portfolio_safe, portfolio_independent_safe = _raw_totals(portfolio)
    baseline_n4, baseline_independent_n4 = _n4_totals(baseline)
    portfolio_n4, portfolio_independent_n4 = _n4_totals(portfolio)
    baseline_witnesses = _sample_witnesses(baseline, N4_COPY_PASTE_WHITESPACE)
    portfolio_witnesses = _sample_witnesses(portfolio, N4_COPY_PASTE_WHITESPACE)
    if set(baseline_witnesses) != set(portfolio_witnesses):
        raise ValueError("durable portfolio matched witness cells are incomplete")
    budget_rows = []
    total_gains = 0
    total_losses = 0
    for budget in NORMALIZATION_SURVIVAL_BUDGETS:
        keys = tuple(key for key in sorted(baseline_witnesses) if key[1] == budget)
        baseline_count = sum(baseline_witnesses[key] for key in keys)
        portfolio_count = sum(portfolio_witnesses[key] for key in keys)
        gains = sum(
            not baseline_witnesses[key] and portfolio_witnesses[key] for key in keys
        )
        losses = sum(
            baseline_witnesses[key] and not portfolio_witnesses[key] for key in keys
        )
        total_gains += gains
        total_losses += losses
        budget_rows.append(
            {
                "budget": budget,
                "sample_count": len(keys),
                "baseline_reachable_sample_count": baseline_count,
                "portfolio_reachable_sample_count": portfolio_count,
                "matched_gain_count": gains,
                "matched_loss_count": losses,
            }
        )
    new_n4_rows = _new_rule_rows(portfolio, new_rule_ids)
    by_rule = {value["rule_id"]: value for value in new_n4_rows}
    if set(by_rule) - new_rule_ids:
        raise ValueError("durable portfolio rule summary attribution drifted")
    new_invariant_rejections = sum(
        not value["invariant_safe"]
        for value in added_rows
        if value["profile_id"] == "N0_IDENTITY"
    )
    qualification_rows = tuple(
        {
            "rule_id": rule.rule_id,
            "rule_hash": rule.rule_hash,
            "observed_candidate_count": (
                0 if rule.rule_id not in by_rule else by_rule[rule.rule_id]["candidate_count"]
            ),
            "observed_invariant_safe_count": (
                0
                if rule.rule_id not in by_rule
                else by_rule[rule.rule_id]["invariant_safe_count"]
            ),
            "observed_n4_surviving_count": (
                0
                if rule.rule_id not in by_rule
                else by_rule[rule.rule_id]["invariant_safe_surviving_count"]
            ),
            "normalization_status": _normalization_status(by_rule.get(rule.rule_id)),
            "source_grounded_fidelity_status": "NOT_PROVIDED",
            "release_eligible": False,
            "release_status": DURABLE_PORTFOLIO_RELEASE_STATUS,
        }
        for rule in sorted(durable_rules, key=lambda value: value.rule_id)
    )
    independent_n4_gain = portfolio_independent_n4 - baseline_independent_n4
    independent_n4_relative_gain = _rate(independent_n4_gain, baseline_independent_n4)
    material_gain = (
        independent_n4_relative_gain is not None
        and independent_n4_relative_gain
        >= DURABLE_PORTFOLIO_MINIMUM_INDEPENDENT_N4_RELATIVE_GAIN
    )
    portfolio_success = (
        material_gain
        and total_gains > 0
        and total_losses == 0
        and new_invariant_rejections == 0
        and all(
            value["normalization_status"] in ("PASS", "NOT_OBSERVED")
            for value in qualification_rows
        )
    )
    payload = {
        "algorithm_version": DURABLE_PORTFOLIO_COMPARISON_VERSION,
        "benchmark_source_code_commit": baseline["benchmark_source_code_commit"],
        "source_corpus_commit": baseline["source_corpus_commit"],
        "source_corpus_hash": baseline["source_corpus_hash"],
        "source_workflow_run_id": baseline["source_workflow_run_id"],
        "sample_count": baseline["source_sample_count"],
        "baseline_artifact_hash": baseline["artifact_hash"],
        "portfolio_artifact_hash": portfolio["artifact_hash"],
        "baseline_ruleset_hash": baseline["ruleset_hash"],
        "portfolio_ruleset_hash": portfolio["ruleset_hash"],
        "new_rules": _new_rule_declarations(),
        "baseline_raw_candidate_count": baseline_raw,
        "portfolio_raw_candidate_count": portfolio_raw,
        "raw_candidate_gain": portfolio_raw - baseline_raw,
        "baseline_invariant_safe_count": baseline_safe,
        "portfolio_invariant_safe_count": portfolio_safe,
        "invariant_safe_gain": portfolio_safe - baseline_safe,
        "baseline_independent_invariant_safe_count": baseline_independent_safe,
        "portfolio_independent_invariant_safe_count": portfolio_independent_safe,
        "independent_invariant_safe_gain": (
            portfolio_independent_safe - baseline_independent_safe
        ),
        "baseline_n4_surviving_count": baseline_n4,
        "portfolio_n4_surviving_count": portfolio_n4,
        "n4_surviving_gain": portfolio_n4 - baseline_n4,
        "baseline_independent_n4_surviving_count": baseline_independent_n4,
        "portfolio_independent_n4_surviving_count": portfolio_independent_n4,
        "independent_n4_surviving_gain": independent_n4_gain,
        "independent_n4_relative_gain": independent_n4_relative_gain,
        "minimum_independent_n4_relative_gain": (
            DURABLE_PORTFOLIO_MINIMUM_INDEPENDENT_N4_RELATIVE_GAIN
        ),
        "new_invariant_rejection_count": new_invariant_rejections,
        "baseline_candidate_row_preservation_count": len(baseline_row_hashes),
        "added_candidate_profile_row_count": len(added_rows),
        "n4_exact_budget_comparison": tuple(budget_rows),
        "total_matched_exact_budget_gain_count": total_gains,
        "total_matched_exact_budget_loss_count": total_losses,
        "rule_qualification": qualification_rows,
        "portfolio_success": portfolio_success,
        "portfolio_decision": (
            DURABLE_PORTFOLIO_SUCCESS if portfolio_success else DURABLE_PORTFOLIO_REJECT
        ),
        "release_eligible_rule_count": 0,
        "release_decision": DURABLE_PORTFOLIO_RELEASE_STATUS,
        "detector_access_observed": False,
        "secret_access_observed": False,
        "scientific_scope": _DURABLE_PORTFOLIO_SCOPE,
    }
    return {**payload, "artifact_hash": sha256_json(payload)}


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _require_nonnegative_count(name: str, value: object) -> None:
    require_int(name, value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _require_exact_keys(
    name: str,
    value: object,
    expected: set[str],
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a JSON object")
    if set(value) != expected:
        raise ValueError(f"{name} keys do not match the frozen schema")
    return value


def load_durable_portfolio_comparison(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs)
    if not isinstance(value, dict):
        raise TypeError("durable portfolio comparison must be a JSON object")
    expected = {
        "algorithm_version",
        "benchmark_source_code_commit",
        "source_corpus_commit",
        "source_corpus_hash",
        "source_workflow_run_id",
        "sample_count",
        "baseline_artifact_hash",
        "portfolio_artifact_hash",
        "baseline_ruleset_hash",
        "portfolio_ruleset_hash",
        "new_rules",
        "baseline_raw_candidate_count",
        "portfolio_raw_candidate_count",
        "raw_candidate_gain",
        "baseline_invariant_safe_count",
        "portfolio_invariant_safe_count",
        "invariant_safe_gain",
        "baseline_independent_invariant_safe_count",
        "portfolio_independent_invariant_safe_count",
        "independent_invariant_safe_gain",
        "baseline_n4_surviving_count",
        "portfolio_n4_surviving_count",
        "n4_surviving_gain",
        "baseline_independent_n4_surviving_count",
        "portfolio_independent_n4_surviving_count",
        "independent_n4_surviving_gain",
        "independent_n4_relative_gain",
        "minimum_independent_n4_relative_gain",
        "new_invariant_rejection_count",
        "baseline_candidate_row_preservation_count",
        "added_candidate_profile_row_count",
        "n4_exact_budget_comparison",
        "total_matched_exact_budget_gain_count",
        "total_matched_exact_budget_loss_count",
        "rule_qualification",
        "portfolio_success",
        "portfolio_decision",
        "release_eligible_rule_count",
        "release_decision",
        "detector_access_observed",
        "secret_access_observed",
        "scientific_scope",
        "artifact_hash",
    }
    if set(value) != expected:
        raise ValueError("durable portfolio comparison keys do not match the frozen schema")
    if value["algorithm_version"] != DURABLE_PORTFOLIO_COMPARISON_VERSION:
        raise ValueError("unsupported durable portfolio comparison version")
    for name in ("benchmark_source_code_commit", "source_corpus_commit"):
        if not isinstance(value[name], str) or _GIT_SHA_RE.fullmatch(value[name]) is None:
            raise ValueError(f"{name} must be a lowercase Git SHA")
    for name in (
        "source_corpus_hash",
        "baseline_artifact_hash",
        "portfolio_artifact_hash",
        "baseline_ruleset_hash",
        "portfolio_ruleset_hash",
        "artifact_hash",
    ):
        require_sha256(name, value[name])
    for name in (
        "source_workflow_run_id",
        "sample_count",
        "baseline_raw_candidate_count",
        "portfolio_raw_candidate_count",
        "baseline_invariant_safe_count",
        "portfolio_invariant_safe_count",
        "baseline_independent_invariant_safe_count",
        "portfolio_independent_invariant_safe_count",
        "baseline_n4_surviving_count",
        "portfolio_n4_surviving_count",
        "baseline_independent_n4_surviving_count",
        "portfolio_independent_n4_surviving_count",
        "new_invariant_rejection_count",
        "baseline_candidate_row_preservation_count",
        "added_candidate_profile_row_count",
        "total_matched_exact_budget_gain_count",
        "total_matched_exact_budget_loss_count",
        "release_eligible_rule_count",
    ):
        _require_nonnegative_count(name, value[name])
    for name in (
        "raw_candidate_gain",
        "invariant_safe_gain",
        "independent_invariant_safe_gain",
        "n4_surviving_gain",
        "independent_n4_surviving_gain",
    ):
        require_int(name, value[name])
    if value["source_workflow_run_id"] <= 0 or value["sample_count"] <= 0:
        raise ValueError("durable portfolio source counts must be positive")
    for name in (
        "new_rules",
        "n4_exact_budget_comparison",
        "rule_qualification",
    ):
        if not isinstance(value[name], list):
            raise TypeError(f"{name} must be a list")
    for name in (
        "portfolio_success",
        "detector_access_observed",
        "secret_access_observed",
    ):
        require_bool(name, value[name])
    baseline_registry = _context_baseline_registry()
    portfolio_registry = durable_portfolio_transform_registry()
    if value["baseline_ruleset_hash"] != baseline_registry.ruleset_hash:
        raise ValueError("durable portfolio comparison baseline ruleset drifted")
    if value["portfolio_ruleset_hash"] != portfolio_registry.ruleset_hash:
        raise ValueError("durable portfolio comparison candidate ruleset drifted")
    if value["new_rules"] != list(_new_rule_declarations()):
        raise ValueError("durable portfolio comparison rule declarations drifted")
    arithmetic = (
        (
            "raw_candidate_gain",
            "baseline_raw_candidate_count",
            "portfolio_raw_candidate_count",
        ),
        (
            "invariant_safe_gain",
            "baseline_invariant_safe_count",
            "portfolio_invariant_safe_count",
        ),
        (
            "independent_invariant_safe_gain",
            "baseline_independent_invariant_safe_count",
            "portfolio_independent_invariant_safe_count",
        ),
        (
            "n4_surviving_gain",
            "baseline_n4_surviving_count",
            "portfolio_n4_surviving_count",
        ),
        (
            "independent_n4_surviving_gain",
            "baseline_independent_n4_surviving_count",
            "portfolio_independent_n4_surviving_count",
        ),
    )
    if any(value[gain] != value[after] - value[before] for gain, before, after in arithmetic):
        raise ValueError("durable portfolio comparison arithmetic does not replay")
    if any(value[gain] < 0 for gain, _, _ in arithmetic):
        raise ValueError("durable portfolio comparison cannot lose aggregate opportunity")
    for prefix in ("baseline", "portfolio"):
        raw = value[f"{prefix}_raw_candidate_count"]
        safe = value[f"{prefix}_invariant_safe_count"]
        independent_safe = value[f"{prefix}_independent_invariant_safe_count"]
        n4 = value[f"{prefix}_n4_surviving_count"]
        independent_n4 = value[f"{prefix}_independent_n4_surviving_count"]
        if safe > raw or independent_safe > safe or n4 > safe or independent_n4 > n4:
            raise ValueError("durable portfolio opportunity bounds drifted")
    profile_count = len(normalization_profiles())
    if value["baseline_candidate_row_preservation_count"] != (
        value["baseline_raw_candidate_count"] * profile_count
    ):
        raise ValueError("durable portfolio baseline row preservation count drifted")
    if value["added_candidate_profile_row_count"] != (
        value["raw_candidate_gain"] * profile_count
    ):
        raise ValueError("durable portfolio added row count drifted")
    if value["new_invariant_rejection_count"] != (
        value["raw_candidate_gain"] - value["invariant_safe_gain"]
    ):
        raise ValueError("durable portfolio invariant rejection accounting drifted")
    if (
        value["minimum_independent_n4_relative_gain"]
        != DURABLE_PORTFOLIO_MINIMUM_INDEPENDENT_N4_RELATIVE_GAIN
    ):
        raise ValueError("durable portfolio minimum relative gain drifted")
    expected_relative_gain = _rate(
        value["independent_n4_surviving_gain"],
        value["baseline_independent_n4_surviving_count"],
    )
    if isinstance(value["independent_n4_relative_gain"], bool) or value[
        "independent_n4_relative_gain"
    ] != expected_relative_gain:
        raise ValueError("durable portfolio relative gain does not replay")
    budget_keys = {
        "budget",
        "sample_count",
        "baseline_reachable_sample_count",
        "portfolio_reachable_sample_count",
        "matched_gain_count",
        "matched_loss_count",
    }
    budget_rows = []
    for expected_budget, item in zip(
        NORMALIZATION_SURVIVAL_BUDGETS,
        value["n4_exact_budget_comparison"],
        strict=True,
    ):
        row = _require_exact_keys("N4 exact-budget comparison", item, budget_keys)
        for name in budget_keys:
            _require_nonnegative_count(name, row[name])
        if row["budget"] != expected_budget or row["sample_count"] != value["sample_count"]:
            raise ValueError("durable portfolio exact-budget identity drifted")
        if any(
            row[name] > row["sample_count"]
            for name in (
                "baseline_reachable_sample_count",
                "portfolio_reachable_sample_count",
                "matched_gain_count",
                "matched_loss_count",
            )
        ):
            raise ValueError("durable portfolio exact-budget count exceeds samples")
        if row["matched_gain_count"] + row["matched_loss_count"] > row["sample_count"]:
            raise ValueError("durable portfolio matched changes exceed samples")
        if row["portfolio_reachable_sample_count"] - row[
            "baseline_reachable_sample_count"
        ] != row["matched_gain_count"] - row["matched_loss_count"]:
            raise ValueError("durable portfolio exact-budget accounting drifted")
        budget_rows.append(row)
    if len(budget_rows) != len(NORMALIZATION_SURVIVAL_BUDGETS):
        raise ValueError("durable portfolio exact-budget rows are incomplete")
    if value["total_matched_exact_budget_gain_count"] != sum(
        row["matched_gain_count"] for row in budget_rows
    ) or value["total_matched_exact_budget_loss_count"] != sum(
        row["matched_loss_count"] for row in budget_rows
    ):
        raise ValueError("durable portfolio exact-budget totals do not replay")
    qualification_keys = {
        "rule_id",
        "rule_hash",
        "observed_candidate_count",
        "observed_invariant_safe_count",
        "observed_n4_surviving_count",
        "normalization_status",
        "source_grounded_fidelity_status",
        "release_eligible",
        "release_status",
    }
    qualifications = []
    declarations = list(_new_rule_declarations())
    if len(value["rule_qualification"]) != len(declarations):
        raise ValueError("durable portfolio rule qualification is incomplete")
    for declaration, item in zip(declarations, value["rule_qualification"], strict=True):
        row = _require_exact_keys("durable rule qualification", item, qualification_keys)
        if row["rule_id"] != declaration["rule_id"] or row["rule_hash"] != declaration[
            "rule_hash"
        ]:
            raise ValueError("durable portfolio qualification identity drifted")
        for name in (
            "observed_candidate_count",
            "observed_invariant_safe_count",
            "observed_n4_surviving_count",
        ):
            _require_nonnegative_count(name, row[name])
        if row["observed_invariant_safe_count"] > row["observed_candidate_count"]:
            raise ValueError("durable portfolio qualification safe count drifted")
        if row["observed_n4_surviving_count"] > row["observed_invariant_safe_count"]:
            raise ValueError("durable portfolio qualification survivor count drifted")
        expected_status = (
            "NOT_OBSERVED"
            if row["observed_candidate_count"] == 0
            else "NO_INVARIANT_SAFE_OBSERVATION"
            if row["observed_invariant_safe_count"] == 0
            else "PASS"
            if row["observed_invariant_safe_count"] == row["observed_n4_surviving_count"]
            else "FAIL"
        )
        if row["normalization_status"] != expected_status:
            raise ValueError("durable portfolio normalization qualification drifted")
        require_bool("release_eligible", row["release_eligible"])
        if (
            row["source_grounded_fidelity_status"] != "NOT_PROVIDED"
            or row["release_eligible"]
            or row["release_status"] != DURABLE_PORTFOLIO_RELEASE_STATUS
        ):
            raise ValueError("durable portfolio release qualification drifted")
        qualifications.append(row)
    if value["raw_candidate_gain"] != sum(
        row["observed_candidate_count"] for row in qualifications
    ) or value["invariant_safe_gain"] != sum(
        row["observed_invariant_safe_count"] for row in qualifications
    ) or value["n4_surviving_gain"] != sum(
        row["observed_n4_surviving_count"] for row in qualifications
    ):
        raise ValueError("durable portfolio rule qualification totals do not replay")
    material_gain = (
        expected_relative_gain is not None
        and expected_relative_gain >= DURABLE_PORTFOLIO_MINIMUM_INDEPENDENT_N4_RELATIVE_GAIN
    )
    expected_success = (
        material_gain
        and value["total_matched_exact_budget_gain_count"] > 0
        and value["total_matched_exact_budget_loss_count"] == 0
        and value["new_invariant_rejection_count"] == 0
        and all(
            row["normalization_status"] in ("PASS", "NOT_OBSERVED")
            for row in qualifications
        )
    )
    if value["portfolio_success"] != expected_success:
        raise ValueError("durable portfolio success decision does not replay")
    expected_decision = DURABLE_PORTFOLIO_SUCCESS if expected_success else DURABLE_PORTFOLIO_REJECT
    if value["portfolio_decision"] != expected_decision:
        raise ValueError("durable portfolio decision drifted")
    if value["detector_access_observed"] or value["secret_access_observed"]:
        raise ValueError("durable portfolio comparison observed prohibited access")
    if (
        value["release_eligible_rule_count"] != 0
        or value["release_decision"] != DURABLE_PORTFOLIO_RELEASE_STATUS
    ):
        raise ValueError("durable portfolio comparison cannot authorize release rules")
    if value["scientific_scope"] != _DURABLE_PORTFOLIO_SCOPE:
        raise ValueError("durable portfolio comparison scientific scope drifted")
    payload = {key: item for key, item in value.items() if key != "artifact_hash"}
    if value["artifact_hash"] != sha256_json(payload):
        raise ValueError("durable portfolio comparison artifact hash mismatch")
    return value
