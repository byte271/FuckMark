from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .._validation import require_bool, require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text


_IMMUTABLE_REVISION_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_EMPTY_TEXT_HASH = sha256_text("")


class PaddingSide(str, Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class ModelTokenizerIdentity:
    model_id: str
    model_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    chat_template_present: bool
    chat_template_hash: str
    special_token_map_hash: str
    padding_side: PaddingSide
    bos_token_id: int | None
    eos_token_id: int | None
    pad_token_id: int | None
    add_bos_token: bool
    add_eos_token: bool
    identity_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("model_id", self.model_id),
            ("model_revision", self.model_revision),
            ("tokenizer_id", self.tokenizer_id),
            ("tokenizer_revision", self.tokenizer_revision),
        ):
            require_clean_string(name, value)
        if _IMMUTABLE_REVISION_RE.fullmatch(self.model_revision) is None:
            raise ValueError("model_revision must be an immutable lowercase hexadecimal revision")
        if _IMMUTABLE_REVISION_RE.fullmatch(self.tokenizer_revision) is None:
            raise ValueError("tokenizer_revision must be an immutable lowercase hexadecimal revision")
        require_bool("chat_template_present", self.chat_template_present)
        require_sha256("chat_template_hash", self.chat_template_hash)
        require_sha256("special_token_map_hash", self.special_token_map_hash)
        if not self.chat_template_present and self.chat_template_hash != _EMPTY_TEXT_HASH:
            raise ValueError("absent chat templates must use the SHA-256 of the empty string")
        if not isinstance(self.padding_side, PaddingSide):
            raise TypeError("padding_side must be a PaddingSide")
        for name, value in (
            ("bos_token_id", self.bos_token_id),
            ("eos_token_id", self.eos_token_id),
            ("pad_token_id", self.pad_token_id),
        ):
            if value is None:
                continue
            require_int(name, value)
            if value < 0:
                raise ValueError(f"{name} must be non-negative when present")
        require_bool("add_bos_token", self.add_bos_token)
        require_bool("add_eos_token", self.add_eos_token)
        require_sha256("identity_hash", self.identity_hash)
        if self.identity_hash != sha256_json(self._payload()):
            raise ValueError("identity_hash does not match model/tokenizer identity")

    def _payload(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_revision": self.tokenizer_revision,
            "chat_template_present": self.chat_template_present,
            "chat_template_hash": self.chat_template_hash,
            "special_token_map_hash": self.special_token_map_hash,
            "padding_side": self.padding_side.value,
            "bos_token_id": self.bos_token_id,
            "eos_token_id": self.eos_token_id,
            "pad_token_id": self.pad_token_id,
            "add_bos_token": self.add_bos_token,
            "add_eos_token": self.add_eos_token,
        }

    @classmethod
    def create(
        cls,
        model_id: str,
        model_revision: str,
        tokenizer_id: str,
        tokenizer_revision: str,
        chat_template_present: bool,
        chat_template_hash: str,
        special_token_map_hash: str,
        padding_side: PaddingSide,
        bos_token_id: int | None,
        eos_token_id: int | None,
        pad_token_id: int | None,
        add_bos_token: bool,
        add_eos_token: bool,
    ) -> ModelTokenizerIdentity:
        payload = {
            "model_id": model_id,
            "model_revision": model_revision,
            "tokenizer_id": tokenizer_id,
            "tokenizer_revision": tokenizer_revision,
            "chat_template_present": chat_template_present,
            "chat_template_hash": chat_template_hash,
            "special_token_map_hash": special_token_map_hash,
            "padding_side": padding_side.value if isinstance(padding_side, PaddingSide) else padding_side,
            "bos_token_id": bos_token_id,
            "eos_token_id": eos_token_id,
            "pad_token_id": pad_token_id,
            "add_bos_token": add_bos_token,
            "add_eos_token": add_eos_token,
        }
        return cls(
            model_id=model_id,
            model_revision=model_revision,
            tokenizer_id=tokenizer_id,
            tokenizer_revision=tokenizer_revision,
            chat_template_present=chat_template_present,
            chat_template_hash=chat_template_hash,
            special_token_map_hash=special_token_map_hash,
            padding_side=padding_side,
            bos_token_id=bos_token_id,
            eos_token_id=eos_token_id,
            pad_token_id=pad_token_id,
            add_bos_token=add_bos_token,
            add_eos_token=add_eos_token,
            identity_hash=sha256_json(payload),
        )
