from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from fuckmark.config import canonical_json_bytes, canonical_json_text
from fuckmark.experiments.cycle6_confirmation import (
    CYCLE6_CONFIRMATION_SEED_BASES,
    CYCLE6_FROZEN_SOURCE_BLOBS,
    validate_cycle6_confirmation_contract,
)
from fuckmark.hashing import sha256_json, sha256_text
from fuckmark.tiny_dev_cycle6_freeze_cross_check import (
    CYCLE6_FREEZE_CROSS_CHECK_VERSION,
    build_cycle6_freeze_cross_check,
    cross_check_cycle6_frozen_artifacts,
    main as cross_check_main,
)


ROOT = Path(__file__).resolve().parents[1]
FROZEN_COMMIT = "b" * 40
ORCHESTRATION_COMMIT = "c" * 40
FROZEN_SCIENTIFIC_COMMIT = "bfd9a4d81f0561a17f5ac4daa3858e97ebd811f1"
RUN16_CONTRACT_HASH = "8bff80151c1be33a9f4bedf0b00abab1fffd9b04c0572aef1381be58530e1cef"
RUN16_CORPUS_HASHES = {
    760000: "d507802fec23d8f4b9ad0a4250131800d2baa3e4f85fa070c8678f50d598bb32",
    770000: "2a24b04cead31427cd175e957f441b80b6e7c3febb9e6e08d2f4b78daab5f567",
    780000: "5ee089d76fd61c31081a3085c85f2cef93c64b5f9e8452bce92ad630672c2c79",
}
RUN16_PLAN_HASHES = {
    760000: "706483a4229af16ba07fd6d18c9ee3da00ff9ee1b321dd1d0dbefb54416c28a4",
    770000: "b534c4c96df7688967573c41a55e222d023790672c99c6e09f3c9f221581c871",
    780000: "8915dfc129fe3b8d144f9e48dbf20da6bd8190179ec8cc009576afb017546415",
}
RUN16_CROSS_CHECK_HASH_ORCHESTRATION_FROZEN = (
    "b2c1a5b81a6af67bacaa798a89bce02d18efd948760f54e5b5c4a4ac992f4dcc"
)
RUN16_CROSS_CHECK_FILE_SHA256 = (
    "00f63cc48552ef37608150c26a50aefe507d806b2bee4813d622731f8f349f3c"
)
RUN16_ROOT = ROOT / ".tmp" / "cycle6-run16"


def _hashes(prefix: str) -> dict[int, str]:
    return {
        seed: sha256_json({"kind": prefix, "confirmation_seed_base": seed})
        for seed in CYCLE6_CONFIRMATION_SEED_BASES
    }


def _build() -> dict[str, object]:
    return build_cycle6_freeze_cross_check(
        contract_hash=sha256_json({"contract": "cycle6-v2"}),
        corpus_artifact_hashes=_hashes("corpus"),
        plan_hashes=_hashes("plan"),
        frozen_source_code_commit=FROZEN_COMMIT,
        orchestration_code_commit=ORCHESTRATION_COMMIT,
    )


def test_cycle6_cross_check_builder_uses_canonical_string_seed_keys() -> None:
    artifact = _build()

    assert artifact["algorithm_version"] == CYCLE6_FREEZE_CROSS_CHECK_VERSION
    assert tuple(artifact["seed_bases"]) == CYCLE6_CONFIRMATION_SEED_BASES
    assert tuple(artifact["corpus_artifact_hashes"]) == ("760000", "770000", "780000")
    assert tuple(artifact["plan_hashes"]) == ("760000", "770000", "780000")
    payload = {key: value for key, value in artifact.items() if key != "artifact_hash"}
    assert artifact["artifact_hash"] == sha256_json(payload)


def test_cycle6_cross_check_construction_is_byte_stable() -> None:
    first = _build()
    second = _build()

    assert first == second
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_cycle6_cross_check_rejects_missing_seed_binding() -> None:
    corpus_hashes = _hashes("corpus")
    del corpus_hashes[780_000]

    with pytest.raises(ValueError, match="three frozen Cycle 6 seed bases"):
        build_cycle6_freeze_cross_check(
            contract_hash=sha256_json({"contract": "cycle6-v2"}),
            corpus_artifact_hashes=corpus_hashes,
            plan_hashes=_hashes("plan"),
            frozen_source_code_commit=FROZEN_COMMIT,
            orchestration_code_commit=ORCHESTRATION_COMMIT,
        )


def test_cycle6_workflow_runs_tested_cross_check_before_scoring() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cycle6-confirmation.yml").read_text(
        encoding="utf-8"
    )

    assert "python -m fuckmark.tiny_dev_cycle6_freeze_cross_check" in workflow
    assert "corpus_hashes[seed]" not in workflow
    assert "plan_hashes[seed]" not in workflow
    assert "needs: freeze-cross-check" in workflow
    assert "needs: score" in workflow


def test_run16_integer_seed_mappings_cannot_be_canonically_hashed() -> None:
    payload = {
        "algorithm_version": "cycle6-freeze-cross-check-v1",
        "contract_hash": RUN16_CONTRACT_HASH,
        "seed_bases": CYCLE6_CONFIRMATION_SEED_BASES,
        "corpus_artifact_hashes": dict(RUN16_CORPUS_HASHES),
        "plan_hashes": dict(RUN16_PLAN_HASHES),
        "attack_rows_per_corpus": 128,
        "pairwise_attack_text_overlap": 0,
        "all_plans_frozen_before_scoring": True,
        "detector_access_used_for_selection": False,
        "secret_access_used_for_selection": False,
    }

    with pytest.raises(TypeError, match="Canonical JSON object keys must be strings"):
        sha256_json(payload)


def test_run16_bindings_produce_the_recovered_cross_check_hash() -> None:
    contract = json.loads(
        (ROOT / "specs" / "fuckmark-cycle6-confirmation-v2.contract.json").read_text(
            encoding="utf-8"
        )
    )
    contract_hash = validate_cycle6_confirmation_contract(contract)
    artifact = build_cycle6_freeze_cross_check(
        contract_hash=contract_hash,
        corpus_artifact_hashes=RUN16_CORPUS_HASHES,
        plan_hashes=RUN16_PLAN_HASHES,
        frozen_source_code_commit=FROZEN_SCIENTIFIC_COMMIT,
        orchestration_code_commit=FROZEN_SCIENTIFIC_COMMIT,
    )
    encoded = canonical_json_bytes(artifact) + b"\n"

    assert contract_hash == RUN16_CONTRACT_HASH
    assert artifact["artifact_hash"] == RUN16_CROSS_CHECK_HASH_ORCHESTRATION_FROZEN
    assert hashlib.sha256(encoded).hexdigest() == RUN16_CROSS_CHECK_FILE_SHA256
    assert canonical_json_bytes(artifact) == canonical_json_bytes(
        json.loads(encoded.decode("utf-8"))
    )


def _write_frozen_tree(
    root: Path,
    *,
    detector_scoring_performed: bool = False,
    overlap_across_corpora: bool = False,
) -> dict[int, str]:
    corpus_hashes: dict[int, str] = {}
    for seed in CYCLE6_CONFIRMATION_SEED_BASES:
        freeze_root = root / f"cycle6-freeze-{seed}"
        freeze_root.mkdir(parents=True)
        corpus_hash = sha256_json({"corpus": seed})
        plan_hash = sha256_json({"plan": seed})
        corpus_hashes[seed] = corpus_hash
        rows = []
        for label in ("watermarked", "unwatermarked"):
            for index in range(64):
                namespace = "shared" if overlap_across_corpora else str(seed)
                rows.append(
                    {
                        "source_label": label,
                        "source_text_hash": sha256_text(f"{namespace}-{label}-{index}"),
                    }
                )
        corpus_path = freeze_root / f"cycle6-corpus-{seed}.json"
        plan_path = freeze_root / f"cycle6-plan-{seed}.json"
        corpus_path.write_text("{}\n", encoding="utf-8", newline="\n")
        plan_path.write_text(
            json.dumps(
                {
                    "source_code_commit": FROZEN_COMMIT,
                    "rows": rows,
                    "plan_hash": plan_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        files = {
            corpus_path.name: {
                "file_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
                "artifact_hash": corpus_hash,
                "plan_hash": None,
            },
            plan_path.name: {
                "file_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                "artifact_hash": None,
                "plan_hash": plan_hash,
            },
        }
        manifest_payload = {
            "algorithm_version": "cycle6-freeze-manifest-v1",
            "confirmation_seed_base": seed,
            "source_code_commit": FROZEN_COMMIT,
            "files": files,
            "detector_scoring_performed": detector_scoring_performed,
            "secret_access_performed": False,
        }
        manifest = {**manifest_payload, "manifest_hash": sha256_json(manifest_payload)}
        (freeze_root / f"cycle6-freeze-manifest-{seed}.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return corpus_hashes


def _patch_scientific_validators(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fuckmark.tiny_dev_cycle6_freeze_cross_check.validate_cycle6_confirmation_contract",
        lambda contract: sha256_json({"contract": "cycle6-v2"}),
    )
    monkeypatch.setattr(
        "fuckmark.tiny_dev_cycle6_freeze_cross_check.validate_cycle6_frozen_source_blobs",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "fuckmark.tiny_dev_cycle6_freeze_cross_check.load_tiny_dev_corpus_by_version_json",
        lambda path: SimpleNamespace(
            artifact_hash=sha256_json({"corpus": int(path.stem.rsplit("-", 1)[1])})
        ),
    )
    monkeypatch.setattr(
        "fuckmark.tiny_dev_cycle6_freeze_cross_check.validate_cycle6_confirmation_plan",
        lambda plan, corpus, contract=None: str(plan["plan_hash"]),
    )


def test_cross_check_payload_construction_canonicalizes_integer_seed_maps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_root = tmp_path / "frozen"
    _write_frozen_tree(frozen_root)
    _patch_scientific_validators(monkeypatch)

    first = cross_check_cycle6_frozen_artifacts(
        frozen_root,
        tmp_path / "repo",
        {"contract": "cycle6-v2"},
        frozen_source_code_commit=FROZEN_COMMIT,
        orchestration_code_commit=ORCHESTRATION_COMMIT,
    )
    second = cross_check_cycle6_frozen_artifacts(
        frozen_root,
        tmp_path / "repo",
        {"contract": "cycle6-v2"},
        frozen_source_code_commit=FROZEN_COMMIT,
        orchestration_code_commit=ORCHESTRATION_COMMIT,
    )
    output = tmp_path / "cycle6-freeze-cross-check.json"
    expected = tmp_path / "expected.json"
    assert (
        cross_check_main(
            [
                "--frozen-root",
                str(frozen_root),
                "--repository-root",
                str(tmp_path / "repo"),
                "--contract-json",
                str(_write_contract(tmp_path)),
                "--frozen-source-code-commit",
                FROZEN_COMMIT,
                "--orchestration-code-commit",
                ORCHESTRATION_COMMIT,
                "--json",
                str(output),
            ]
        )
        == 0
    )

    assert tuple(first["corpus_artifact_hashes"]) == ("760000", "770000", "780000")
    assert tuple(first["plan_hashes"]) == ("760000", "770000", "780000")
    assert first == second
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert output.read_bytes() == canonical_json_bytes(first) + b"\n"
    expected.write_bytes(output.read_bytes())
    assert (
        cross_check_main(
            [
                "--frozen-root",
                str(frozen_root),
                "--repository-root",
                str(tmp_path / "repo"),
                "--contract-json",
                str(tmp_path / "contract.json"),
                "--frozen-source-code-commit",
                FROZEN_COMMIT,
                "--orchestration-code-commit",
                ORCHESTRATION_COMMIT,
                "--expected-cross-check-json",
                str(expected),
            ]
        )
        == 0
    )


def _write_contract(root: Path) -> Path:
    path = root / "contract.json"
    path.write_text("{}\n", encoding="utf-8", newline="\n")
    return path


def test_cross_check_rejects_detector_access_before_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_root = tmp_path / "frozen"
    _write_frozen_tree(frozen_root, detector_scoring_performed=True)
    _patch_scientific_validators(monkeypatch)

    with pytest.raises(ValueError, match="detector accessed before freeze"):
        cross_check_cycle6_frozen_artifacts(
            frozen_root,
            tmp_path / "repo",
            {"contract": "cycle6-v2"},
            frozen_source_code_commit=FROZEN_COMMIT,
            orchestration_code_commit=ORCHESTRATION_COMMIT,
        )


def test_cross_check_rejects_cross_corpus_attack_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen_root = tmp_path / "frozen"
    _write_frozen_tree(frozen_root, overlap_across_corpora=True)
    _patch_scientific_validators(monkeypatch)

    with pytest.raises(ValueError, match="attack text overlap"):
        cross_check_cycle6_frozen_artifacts(
            frozen_root,
            tmp_path / "repo",
            {"contract": "cycle6-v2"},
            frozen_source_code_commit=FROZEN_COMMIT,
            orchestration_code_commit=ORCHESTRATION_COMMIT,
        )


def _git_blob_root(tmp_path: Path) -> Path:
    repo = tmp_path / "scientific"
    for relative in CYCLE6_FROZEN_SOURCE_BLOBS:
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
        )
    return repo


@pytest.mark.skipif(
    not (RUN16_ROOT / "cycle6-freeze-760000" / "cycle6-corpus-760000.json").is_file(),
    reason="run 32873260399 freeze artifacts are not present locally",
)
def test_run16_frozen_artifacts_cross_check_is_byte_stable(tmp_path: Path) -> None:
    contract = json.loads(
        (ROOT / "specs" / "fuckmark-cycle6-confirmation-v2.contract.json").read_text(
            encoding="utf-8"
        )
    )
    repository_root = _git_blob_root(tmp_path)
    first = cross_check_cycle6_frozen_artifacts(
        RUN16_ROOT,
        repository_root,
        contract,
        frozen_source_code_commit=FROZEN_SCIENTIFIC_COMMIT,
        orchestration_code_commit=FROZEN_SCIENTIFIC_COMMIT,
    )
    second = cross_check_cycle6_frozen_artifacts(
        RUN16_ROOT,
        repository_root,
        contract,
        frozen_source_code_commit=FROZEN_SCIENTIFIC_COMMIT,
        orchestration_code_commit=FROZEN_SCIENTIFIC_COMMIT,
    )

    assert first == second
    assert first["artifact_hash"] == RUN16_CROSS_CHECK_HASH_ORCHESTRATION_FROZEN
    assert first["corpus_artifact_hashes"] == {
        str(seed): digest for seed, digest in RUN16_CORPUS_HASHES.items()
    }
    assert first["plan_hashes"] == {
        str(seed): digest for seed, digest in RUN16_PLAN_HASHES.items()
    }
    assert canonical_json_text(first) + "\n" == (
        RUN16_ROOT / "cycle6-freeze-cross-check.json"
    ).read_text(encoding="utf-8")
