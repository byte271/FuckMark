from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus import (
    GenerationParameters,
    KeySplit,
    ModelTokenizerIdentity,
    PaddingSide,
    WatermarkCondition,
)
from .corpus.mid_dev import MID_DEV_SOURCE_COUNT
from .corpus.mid_dev_generation import (
    MID_DEV_SEED_POLICY_ID,
    MidDevGeneratedContinuation,
    build_real_mid_dev_corpus,
)
from .hashing import sha256_json, sha256_text


DEFAULT_MODEL_ID = "openai-community/gpt2"
DEFAULT_MODEL_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
DEFAULT_KEYS = (654, 400, 836, 123, 340, 443, 597, 160, 57)
DEFAULT_NGRAM_LEN = 5


class HuggingFaceMidDevBackend:
    def __init__(
        self,
        model_id: str,
        model_revision: str,
        *,
        device: str,
        temperature: float,
        top_k: int,
        top_p: float,
        ngram_len: int = DEFAULT_NGRAM_LEN,
        keys: tuple[int, ...] = DEFAULT_KEYS,
    ) -> None:
        try:
            import torch
            import transformers
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                SynthIDTextWatermarkingConfig,
            )
        except ImportError as error:
            raise RuntimeError(
                "Install the pinned Transformers/Torch dependencies before running MidDev generation"
            ) from error
        if len(model_revision) not in (40, 64) or any(
            character not in "0123456789abcdef" for character in model_revision
        ):
            raise ValueError("model_revision must be an immutable lowercase hexadecimal revision")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be auto, cpu, or cuda")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")

        self._torch = torch
        self._transformers = transformers
        self._model_id = model_id
        self._model_revision = model_revision
        self._device = device
        self._temperature = temperature
        self._top_k = top_k
        self._top_p = top_p

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            revision=model_revision,
            padding_side="left",
        )
        if self._tokenizer.eos_token_id is None:
            raise RuntimeError("the selected tokenizer must define eos_token_id")
        if self._tokenizer.pad_token_id is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id,
            revision=model_revision,
        )
        self._model.to(device)
        self._model.eval()

        self._watermark_config = SynthIDTextWatermarkingConfig(
            ngram_len=ngram_len,
            keys=list(keys),
        )
        watermark_payload = {
            "ngram_len": ngram_len,
            "keys": keys,
            "context_history_size": 1024,
            "sampling_table_seed": 0,
            "sampling_table_size": 65536,
            "skip_first_ngram_calls": False,
            "debug_mode": False,
        }
        self._watermark_condition = WatermarkCondition.create(
            sha256_json(watermark_payload),
            KeySplit.DEV,
            "dev-huggingface-synthid-default-v1",
        )

        chat_template = getattr(self._tokenizer, "chat_template", None)
        if chat_template is not None and not isinstance(chat_template, str):
            raise RuntimeError("tokenizer chat_template must be a string when present")
        self._model_identity = ModelTokenizerIdentity.create(
            model_id=model_id,
            model_revision=model_revision,
            tokenizer_id=model_id,
            tokenizer_revision=model_revision,
            chat_template_present=bool(chat_template),
            chat_template_hash=sha256_text(chat_template or ""),
            special_token_map_hash=sha256_json(self._tokenizer.special_tokens_map),
            padding_side=PaddingSide.LEFT,
            bos_token_id=self._tokenizer.bos_token_id,
            eos_token_id=self._tokenizer.eos_token_id,
            pad_token_id=self._tokenizer.pad_token_id,
            add_bos_token=bool(getattr(self._tokenizer, "add_bos_token", False)),
            add_eos_token=bool(getattr(self._tokenizer, "add_eos_token", False)),
        )
        first_parameter = next(self._model.parameters())
        self._dtype = str(first_parameter.dtype).removeprefix("torch.")
        self._backend_version = (
            f"transformers={transformers.__version__};"
            f"torch={torch.__version__};device={device};revision={model_revision};"
            "length_policy=min_new_tokens_equals_max_new_tokens"
        )

    @property
    def model_identity(self) -> ModelTokenizerIdentity:
        return self._model_identity

    @property
    def watermark_condition(self) -> WatermarkCondition:
        return self._watermark_condition

    def generation_parameters(self, seed: int, target_length: int) -> GenerationParameters:
        return GenerationParameters.create(
            seed=seed,
            seed_policy_id=MID_DEV_SEED_POLICY_ID,
            temperature=self._temperature,
            top_k=self._top_k,
            top_p=self._top_p,
            max_new_tokens=target_length,
            do_sample=True,
            dtype=self._dtype,
            device=self._device,
            backend_id="huggingface-transformers-synthid-mid-dev-exact-length",
            backend_version=self._backend_version,
        )

    def generate(
        self,
        prompt: str,
        seed: int,
        target_length: int,
        *,
        watermarked: bool,
    ) -> MidDevGeneratedContinuation:
        torch = self._torch
        torch.manual_seed(seed)
        if self._device == "cuda":
            torch.cuda.manual_seed_all(seed)

        encoded = self._tokenizer(prompt, return_tensors="pt")
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        kwargs = {
            "do_sample": True,
            "temperature": self._temperature,
            "top_k": self._top_k,
            "top_p": self._top_p,
            "min_new_tokens": target_length,
            "max_new_tokens": target_length,
            "pad_token_id": self._tokenizer.pad_token_id,
        }
        if watermarked:
            kwargs["watermarking_config"] = self._watermark_config

        with torch.inference_mode():
            output = self._model.generate(**encoded, **kwargs)
        input_ids = tuple(
            int(value) for value in encoded["input_ids"][0].detach().cpu().tolist()
        )
        attention_mask = tuple(
            int(value) for value in encoded["attention_mask"][0].detach().cpu().tolist()
        )
        continuation = tuple(
            int(value)
            for value in output[0, len(input_ids) :].detach().cpu().tolist()
        )
        if len(continuation) != target_length:
            raise RuntimeError(
                f"exact-length MidDev generation returned {len(continuation)} tokens; "
                f"expected {target_length}"
            )
        text = self._tokenizer.decode(continuation, skip_special_tokens=True)
        if not text:
            raise RuntimeError("generation produced an empty decoded continuation")
        text_only = tuple(
            int(value) for value in self._tokenizer.encode(text, add_special_tokens=False)
        )
        if not text_only:
            raise RuntimeError("text-only re-encoding produced no tokens")
        return MidDevGeneratedContinuation(
            text=text,
            input_token_ids=input_ids,
            attention_mask=attention_mask,
            continuation_token_ids=continuation,
            text_only_token_ids=text_only,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-mid-dev-corpus-hf")
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    parser.add_argument("--model-revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/mid-dev-corpus.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    backend = HuggingFaceMidDevBackend(
        args.model,
        args.model_revision,
        device=args.device,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    artifact = build_real_mid_dev_corpus(backend)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    model_hashes = {sample.model.identity_hash for sample in artifact.manifest.samples}
    watermark_hashes = {
        sample.watermark.condition_hash for sample in artifact.manifest.samples
    }
    if len(model_hashes) != 1 or len(watermark_hashes) != 1:
        raise RuntimeError("MidDev corpus mixed model or watermark identities")
    sys.stdout.write(f"artifact_hash={artifact.artifact_hash}\n")
    sys.stdout.write(f"manifest_hash={artifact.manifest.manifest_hash}\n")
    sys.stdout.write(f"source_profile_hash={artifact.source_profile_hash}\n")
    sys.stdout.write(f"analysis_split_hash={artifact.analysis_split_hash}\n")
    sys.stdout.write(f"source_count={artifact.source_count}\n")
    sys.stdout.write(f"sample_count={len(artifact.manifest.samples)}\n")
    sys.stdout.write(f"model_identity_hash={next(iter(model_hashes))}\n")
    sys.stdout.write(f"watermark_condition_hash={next(iter(watermark_hashes))}\n")
    sys.stdout.write(f"expected_source_count={MID_DEV_SOURCE_COUNT}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
