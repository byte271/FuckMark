from __future__ import annotations

from dataclasses import dataclass

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json, sha256_text
from .generation import GenerationParameters, WatermarkCondition
from .identity import ModelTokenizerIdentity, PaddingSide
from .schema import CorpusDomain, CorpusSplit, KeySplit, PromptBoundaryMode, TARGET_LENGTHS, WatermarkLabel, require_exact_text
from .tokenization import GenerationTokenRecord, TextOnlyTokenRecord, TokenTrack


@dataclass(frozen=True, slots=True)
class CorpusSample:
    sample_id: str
    match_id: str
    prompt_id: str
    prompt_family_id: str
    domain: CorpusDomain
    split: CorpusSplit
    language: str
    label: WatermarkLabel
    text: str
    text_sha256: str
    model: ModelTokenizerIdentity
    generation: GenerationParameters
    watermark: WatermarkCondition
    target_length: int
    prompt_boundary_mode: PromptBoundaryMode
    generation_tokens: GenerationTokenRecord
    text_only_tokens: TextOnlyTokenRecord | None
    generation_realized_length: int
    record_hash: str

    def __post_init__(self) -> None:
        for name, value in (
            ("sample_id", self.sample_id),
            ("match_id", self.match_id),
            ("prompt_id", self.prompt_id),
            ("prompt_family_id", self.prompt_family_id),
            ("language", self.language),
        ):
            require_clean_string(name, value)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        if not isinstance(self.split, CorpusSplit):
            raise TypeError("split must be a CorpusSplit")
        if self.language != "en":
            raise ValueError("FuckMark v0.1.0 corpus language must be en")
        if not isinstance(self.label, WatermarkLabel):
            raise TypeError("label must be a WatermarkLabel")
        require_exact_text("text", self.text)
        require_sha256("text_sha256", self.text_sha256)
        if self.text_sha256 != sha256_text(self.text):
            raise ValueError("text_sha256 does not match exact sample text")
        if not isinstance(self.model, ModelTokenizerIdentity):
            raise TypeError("model must be a ModelTokenizerIdentity")
        if not isinstance(self.generation, GenerationParameters):
            raise TypeError("generation must be GenerationParameters")
        if not isinstance(self.watermark, WatermarkCondition):
            raise TypeError("watermark must be WatermarkCondition")
        require_int("target_length", self.target_length)
        if self.target_length not in TARGET_LENGTHS:
            raise ValueError("target_length must be one of 64, 128, 256, 512, 1024")
        if self.generation.max_new_tokens < self.target_length:
            raise ValueError("generation max_new_tokens must be at least target_length")
        if not isinstance(self.prompt_boundary_mode, PromptBoundaryMode):
            raise TypeError("prompt_boundary_mode must be a PromptBoundaryMode")
        if self.prompt_boundary_mode is not PromptBoundaryMode.CONTINUATION_ONLY:
            raise ValueError("corpus source samples must use continuation-only prompt boundaries")
        if not isinstance(self.generation_tokens, GenerationTokenRecord):
            raise TypeError("generation_tokens must be a GenerationTokenRecord")
        if self.generation_tokens.model_tokenizer_identity_hash != self.model.identity_hash:
            raise ValueError("generation token record does not match the sample model/tokenizer identity")
        if self.text_only_tokens is not None and not isinstance(self.text_only_tokens, TextOnlyTokenRecord):
            raise TypeError("text_only_tokens must be a TextOnlyTokenRecord or None")
        mask = self.generation_tokens.attention_mask
        if self.model.padding_side is PaddingSide.LEFT and mask != tuple(sorted(mask)):
            raise ValueError("left-padding attention masks must contain zeros only before ones")
        if self.model.padding_side is PaddingSide.RIGHT and mask != tuple(sorted(mask, reverse=True)):
            raise ValueError("right-padding attention masks must contain ones only before zeros")
        if self.model.pad_token_id is not None:
            for token_id, valid in zip(self.generation_tokens.input_token_ids, mask):
                if valid == 0 and token_id != self.model.pad_token_id:
                    raise ValueError("masked generation input positions must equal the pinned pad_token_id")
        if self.text_only_tokens is not None:
            if self.text_only_tokens.model_tokenizer_identity_hash != self.model.identity_hash:
                raise ValueError("text-only token record does not match the sample model/tokenizer identity")
            if self.text_only_tokens.source_text_sha256 != self.text_sha256:
                raise ValueError("text-only token record must bind to the exact sample text")
        require_int("generation_realized_length", self.generation_realized_length)
        expected_length = len(self.generation_tokens.continuation_token_ids)
        if self.generation_realized_length <= 0 or self.generation_realized_length != expected_length:
            raise ValueError("generation_realized_length must equal the positive generated continuation token count")
        if self.generation_realized_length > self.generation.max_new_tokens:
            raise ValueError("generation_realized_length must not exceed generation max_new_tokens")
        if self.split is CorpusSplit.FINAL_TEST and self.watermark.key_split is not KeySplit.TEST:
            raise ValueError("final-test corpus samples must use TEST_KEYS")
        if self.split is not CorpusSplit.FINAL_TEST and self.watermark.key_split is KeySplit.TEST:
            raise ValueError("TEST_KEYS must not appear outside the final-test corpus split")
        require_sha256("record_hash", self.record_hash)
        if self.record_hash != sha256_json(self._payload()):
            raise ValueError("record_hash does not match corpus sample")

    def _payload(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "match_id": self.match_id,
            "prompt_id": self.prompt_id,
            "prompt_family_id": self.prompt_family_id,
            "domain": self.domain.value,
            "split": self.split.value,
            "language": self.language,
            "label": self.label.value,
            "text": self.text,
            "text_sha256": self.text_sha256,
            "model": self.model,
            "generation": self.generation,
            "watermark": self.watermark,
            "target_length": self.target_length,
            "prompt_boundary_mode": self.prompt_boundary_mode.value,
            "generation_tokens": self.generation_tokens,
            "text_only_tokens": self.text_only_tokens,
            "generation_realized_length": self.generation_realized_length,
        }

    def token_ids_for(self, track: TokenTrack) -> tuple[int, ...]:
        if not isinstance(track, TokenTrack):
            raise TypeError("track must be a TokenTrack")
        if track is TokenTrack.GENERATION:
            return self.generation_tokens.continuation_token_ids
        if self.text_only_tokens is None:
            raise KeyError("text-only token track is not available for this sample")
        return self.text_only_tokens.token_ids

    def token_hash_for(self, track: TokenTrack) -> str:
        if not isinstance(track, TokenTrack):
            raise TypeError("track must be a TokenTrack")
        if track is TokenTrack.GENERATION:
            return self.generation_tokens.continuation_token_hash
        if self.text_only_tokens is None:
            raise KeyError("text-only token track is not available for this sample")
        return self.text_only_tokens.token_hash

    def realized_length_for(self, track: TokenTrack) -> int:
        return len(self.token_ids_for(track))

    @classmethod
    def create(
        cls,
        sample_id: str,
        match_id: str,
        prompt_id: str,
        prompt_family_id: str,
        domain: CorpusDomain,
        split: CorpusSplit,
        label: WatermarkLabel,
        text: str,
        model: ModelTokenizerIdentity,
        generation: GenerationParameters,
        watermark: WatermarkCondition,
        target_length: int,
        generation_tokens: GenerationTokenRecord,
        text_only_tokens: TextOnlyTokenRecord | None = None,
        prompt_boundary_mode: PromptBoundaryMode = PromptBoundaryMode.CONTINUATION_ONLY,
        language: str = "en",
    ) -> CorpusSample:
        require_exact_text("text", text)
        text_hash = sha256_text(text)
        generation_realized_length = (
            len(generation_tokens.continuation_token_ids)
            if isinstance(generation_tokens, GenerationTokenRecord)
            else 0
        )
        payload = {
            "sample_id": sample_id,
            "match_id": match_id,
            "prompt_id": prompt_id,
            "prompt_family_id": prompt_family_id,
            "domain": domain.value if isinstance(domain, CorpusDomain) else domain,
            "split": split.value if isinstance(split, CorpusSplit) else split,
            "language": language,
            "label": label.value if isinstance(label, WatermarkLabel) else label,
            "text": text,
            "text_sha256": text_hash,
            "model": model,
            "generation": generation,
            "watermark": watermark,
            "target_length": target_length,
            "prompt_boundary_mode": prompt_boundary_mode.value if isinstance(prompt_boundary_mode, PromptBoundaryMode) else prompt_boundary_mode,
            "generation_tokens": generation_tokens,
            "text_only_tokens": text_only_tokens,
            "generation_realized_length": generation_realized_length,
        }
        return cls(
            sample_id=sample_id,
            match_id=match_id,
            prompt_id=prompt_id,
            prompt_family_id=prompt_family_id,
            domain=domain,
            split=split,
            language=language,
            label=label,
            text=text,
            text_sha256=text_hash,
            model=model,
            generation=generation,
            watermark=watermark,
            target_length=target_length,
            prompt_boundary_mode=prompt_boundary_mode,
            generation_tokens=generation_tokens,
            text_only_tokens=text_only_tokens,
            generation_realized_length=generation_realized_length,
            record_hash=sha256_json(payload),
        )
