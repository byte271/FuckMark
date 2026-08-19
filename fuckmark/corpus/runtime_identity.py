from __future__ import annotations

from ..hashing import sha256_json, sha256_text
from .identity import ModelTokenizerIdentity, PaddingSide


def runtime_tokenizer_identity_public(
    tokenizer,
    model_id: str,
    model_revision: str,
) -> ModelTokenizerIdentity:
    if tokenizer.eos_token_id is None:
        raise RuntimeError("runtime tokenizer must define eos_token_id")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    chat_template = getattr(tokenizer, "chat_template", None)
    if chat_template is not None and not isinstance(chat_template, str):
        raise RuntimeError("runtime tokenizer chat_template must be a string when present")
    padding_side = getattr(tokenizer, "padding_side", None)
    if padding_side != "left":
        raise RuntimeError("runtime tokenizer must use left padding")
    return ModelTokenizerIdentity.create(
        model_id=model_id,
        model_revision=model_revision,
        tokenizer_id=model_id,
        tokenizer_revision=model_revision,
        chat_template_present=bool(chat_template),
        chat_template_hash=sha256_text(chat_template or ""),
        special_token_map_hash=sha256_json(tokenizer.special_tokens_map),
        padding_side=PaddingSide.LEFT,
        bos_token_id=tokenizer.bos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
        add_bos_token=bool(getattr(tokenizer, "add_bos_token", False)),
        add_eos_token=bool(getattr(tokenizer, "add_eos_token", False)),
    )
