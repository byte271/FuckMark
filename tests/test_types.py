import pytest

from fuckmark.types import RunIdentity, SourcePin


def test_source_pin_accepts_valid_identity() -> None:
    pin = SourcePin(
        source_id="deepmind",
        repository="google-deepmind/synthid-text",
        commit="addb4a158143c7c6851a1308f78b89fceed59683",
        license_id="Apache-2.0",
        critical_files=("src/a.py",),
    )
    assert pin.repository == "google-deepmind/synthid-text"


def test_source_pin_rejects_floating_or_empty_identity() -> None:
    with pytest.raises(ValueError):
        SourcePin("x", "invalid", "main", "Apache-2.0", ("a",))


def test_run_identity_rejects_empty_fields() -> None:
    values = ["x"] * 14
    values[5] = ""
    with pytest.raises(ValueError):
        RunIdentity(*values)


def test_source_pin_requires_full_git_sha() -> None:
    with pytest.raises(ValueError):
        SourcePin(
            source_id="deepmind",
            repository="google-deepmind/synthid-text",
            commit="addb4a1",
            license_id="Apache-2.0",
            critical_files=("src/a.py",),
        )


def test_source_pin_rejects_escaping_critical_path() -> None:
    with pytest.raises(ValueError):
        SourcePin(
            source_id="deepmind",
            repository="google-deepmind/synthid-text",
            commit="addb4a158143c7c6851a1308f78b89fceed59683",
            license_id="Apache-2.0",
            critical_files=("../secret",),
        )


def test_source_pin_accepts_json_list_for_critical_files_and_freezes_it() -> None:
    pin = SourcePin(
        source_id="deepmind",
        repository="google-deepmind/synthid-text",
        commit="addb4a158143c7c6851a1308f78b89fceed59683",
        license_id="Apache-2.0",
        critical_files=["src/a.py", "src/b.py"],
    )
    assert pin.critical_files == ("src/a.py", "src/b.py")


def test_source_pin_rejects_noncanonical_repository_paths() -> None:
    with pytest.raises(ValueError):
        SourcePin(
            source_id="deepmind",
            repository="google-deepmind/synthid-text",
            commit="addb4a158143c7c6851a1308f78b89fceed59683",
            license_id="Apache-2.0",
            critical_files=("src//a.py",),
        )


def test_run_identity_accepts_fully_immutable_identity() -> None:
    commit = "a" * 40
    digest = "b" * 64
    identity = RunIdentity(
        run_id="run-1",
        experiment_id="E00",
        git_commit=commit,
        adapter_id="deepmind-reference",
        adapter_source_commit=commit,
        model_id="model/id",
        model_revision=commit,
        tokenizer_id="tokenizer/id",
        tokenizer_revision=commit,
        watermark_config_hash=digest,
        detector_config_hash=digest,
        corpus_manifest_hash=digest,
        transform_config_hash=digest,
        experiment_config_hash=digest,
    )
    assert identity.git_commit == commit


def test_run_identity_rejects_floating_revisions_and_short_hashes() -> None:
    commit = "a" * 40
    digest = "b" * 64
    with pytest.raises(ValueError):
        RunIdentity(
            run_id="run-1",
            experiment_id="E00",
            git_commit=commit,
            adapter_id="deepmind-reference",
            adapter_source_commit=commit,
            model_id="model/id",
            model_revision="main",
            tokenizer_id="tokenizer/id",
            tokenizer_revision=commit,
            watermark_config_hash=digest,
            detector_config_hash=digest,
            corpus_manifest_hash=digest,
            transform_config_hash=digest,
            experiment_config_hash=digest,
        )


def test_identity_strings_reject_control_and_formatting_characters() -> None:
    commit = "a" * 40
    digest = "b" * 64
    with pytest.raises(ValueError):
        SourcePin("deep\nmin", "owner/repo", commit, "Apache-2.0", ("src/a.py",))
    with pytest.raises(ValueError):
        RunIdentity(
            "run\u200b1",
            "E00",
            commit,
            "adapter",
            commit,
            "model/id",
            commit,
            "tokenizer/id",
            commit,
            digest,
            digest,
            digest,
            digest,
            digest,
        )
