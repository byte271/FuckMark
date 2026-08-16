from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from ._validation import require_clean_string, require_sha256


_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_IMMUTABLE_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")



@dataclass(frozen=True, slots=True)
class SourcePin:
    source_id: str
    repository: str
    commit: str
    license_id: str
    critical_files: tuple[str, ...]

    def __post_init__(self) -> None:
        require_clean_string("source_id", self.source_id)
        require_clean_string("repository", self.repository)
        require_clean_string("commit", self.commit)
        require_clean_string("license_id", self.license_id)
        if _REPOSITORY_RE.fullmatch(self.repository) is None:
            raise ValueError("repository must use owner/name form")
        owner, name = self.repository.split("/", 1)
        if owner in {".", ".."} or name in {".", ".."}:
            raise ValueError("repository owner and name must be concrete identifiers")
        if _GIT_SHA_RE.fullmatch(self.commit) is None:
            raise ValueError("commit must be a full 40-character hexadecimal Git revision")
        if not isinstance(self.critical_files, (tuple, list)):
            raise TypeError("critical_files must be a tuple or list")
        normalized_files = tuple(self.critical_files)
        if not normalized_files:
            raise ValueError("critical_files must not be empty")
        for path in normalized_files:
            require_clean_string("critical file path", path)
            if "\\" in path:
                raise ValueError("critical file paths must use forward slashes")
            parsed = PurePosixPath(path)
            if parsed.is_absolute() or ".." in parsed.parts or parsed == PurePosixPath("."):
                raise ValueError("critical file paths must be relative repository file paths")
            if parsed.as_posix() != path:
                raise ValueError("critical file paths must use canonical repository path form")
        if len(set(normalized_files)) != len(normalized_files):
            raise ValueError("critical_files must not contain duplicates")
        object.__setattr__(self, "critical_files", normalized_files)


@dataclass(frozen=True, slots=True)
class RunIdentity:
    run_id: str
    experiment_id: str
    git_commit: str
    adapter_id: str
    adapter_source_commit: str
    model_id: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    watermark_config_hash: str
    detector_config_hash: str
    corpus_manifest_hash: str
    transform_config_hash: str
    experiment_config_hash: str

    def __post_init__(self) -> None:
        names = (
            "run_id",
            "experiment_id",
            "git_commit",
            "adapter_id",
            "adapter_source_commit",
            "model_id",
            "model_revision",
            "tokenizer_id",
            "tokenizer_revision",
            "watermark_config_hash",
            "detector_config_hash",
            "corpus_manifest_hash",
            "transform_config_hash",
            "experiment_config_hash",
        )
        values = (
            self.run_id,
            self.experiment_id,
            self.git_commit,
            self.adapter_id,
            self.adapter_source_commit,
            self.model_id,
            self.model_revision,
            self.tokenizer_id,
            self.tokenizer_revision,
            self.watermark_config_hash,
            self.detector_config_hash,
            self.corpus_manifest_hash,
            self.transform_config_hash,
            self.experiment_config_hash,
        )
        for name, value in zip(names, values):
            require_clean_string(name, value)
        if _GIT_SHA_RE.fullmatch(self.git_commit) is None:
            raise ValueError("git_commit must be a full lowercase 40-character Git revision")
        if _GIT_SHA_RE.fullmatch(self.adapter_source_commit) is None:
            raise ValueError("adapter_source_commit must be a full lowercase 40-character Git revision")
        if _IMMUTABLE_REVISION_RE.fullmatch(self.model_revision) is None:
            raise ValueError("model_revision must be an immutable lowercase hexadecimal revision")
        if _IMMUTABLE_REVISION_RE.fullmatch(self.tokenizer_revision) is None:
            raise ValueError("tokenizer_revision must be an immutable lowercase hexadecimal revision")
        hash_fields = (
            ("watermark_config_hash", self.watermark_config_hash),
            ("detector_config_hash", self.detector_config_hash),
            ("corpus_manifest_hash", self.corpus_manifest_hash),
            ("transform_config_hash", self.transform_config_hash),
            ("experiment_config_hash", self.experiment_config_hash),
        )
        for name, value in hash_fields:
            require_sha256(name, value)
