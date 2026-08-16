from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json, sha256_text
from .schema import CorpusDomain, CorpusSplit, require_exact_text


@dataclass(frozen=True, slots=True)
class PromptRecord:
    prompt_id: str
    prompt_family_id: str
    domain: CorpusDomain
    split: CorpusSplit
    language: str
    source_id: str
    source_hash: str
    license_id: str
    provenance: str
    text: str
    text_sha256: str
    record_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("prompt_id", self.prompt_id),
            ("prompt_family_id", self.prompt_family_id),
            ("language", self.language),
            ("source_id", self.source_id),
            ("license_id", self.license_id),
            ("provenance", self.provenance),
        ):
            require_clean_string(name, value)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        if not isinstance(self.split, CorpusSplit):
            raise TypeError("split must be a CorpusSplit")
        if self.language != "en":
            raise ValueError("FuckMark v0.1.0 corpus language must be en")
        require_sha256("source_hash", self.source_hash)
        require_exact_text("text", self.text)
        require_sha256("text_sha256", self.text_sha256)
        require_sha256("record_hash", self.record_hash)
        if self.text_sha256 != sha256_text(self.text):
            raise ValueError("text_sha256 does not match exact prompt text")
        if self.record_hash != sha256_json(self._payload()):
            raise ValueError("record_hash does not match prompt record")

    def _payload(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_family_id": self.prompt_family_id,
            "domain": self.domain.value,
            "split": self.split.value,
            "language": self.language,
            "source_id": self.source_id,
            "source_hash": self.source_hash,
            "license_id": self.license_id,
            "provenance": self.provenance,
            "text": self.text,
            "text_sha256": self.text_sha256,
        }

    @classmethod
    def create(
        cls,
        prompt_id: str,
        prompt_family_id: str,
        domain: CorpusDomain,
        split: CorpusSplit,
        source_id: str,
        source_hash: str,
        license_id: str,
        provenance: str,
        text: str,
        language: str = "en",
    ) -> PromptRecord:
        require_exact_text("text", text)
        text_hash = sha256_text(text)
        payload = {
            "prompt_id": prompt_id,
            "prompt_family_id": prompt_family_id,
            "domain": domain.value if isinstance(domain, CorpusDomain) else domain,
            "split": split.value if isinstance(split, CorpusSplit) else split,
            "language": language,
            "source_id": source_id,
            "source_hash": source_hash,
            "license_id": license_id,
            "provenance": provenance,
            "text": text,
            "text_sha256": text_hash,
        }
        return cls(
            prompt_id=prompt_id,
            prompt_family_id=prompt_family_id,
            domain=domain,
            split=split,
            language=language,
            source_id=source_id,
            source_hash=source_hash,
            license_id=license_id,
            provenance=provenance,
            text=text,
            text_sha256=text_hash,
            record_hash=sha256_json(payload),
        )
