from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .adapters import DEEPMIND_REFERENCE_SOURCE_PIN, DeepMindReferenceAdapter, DeepMindReferenceConfig
from .config import canonical_json_text
from .detectors.mean import WEIGHTED_MEAN_ALGORITHM_VERSION, weighted_mean_score
from .experiments.e26_open_adapter_transfer import DEEPMIND_BACKEND_ID
from .experiments.synthid_smoke import SynthIDSmokePrompt, run_synthid_smoke
from .hashing import sha256_json
from .synthid_smoke_hf import DEFAULT_PROMPTS


class DeepMindSynthIDSmokeBackend:
    def __init__(
        self,
        model_id: str,
        *,
        device: str,
        max_new_tokens: int,
        temperature: float,
        top_k: int,
        top_p: float,
    ) -> None:
        try:
            import torch
            import transformers
            from synthid_text import synthid_mixin
        except ImportError as error:
            raise RuntimeError("Install the pinned DeepMind smoke dependencies before running this backend") from error
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be auto, cpu, or cuda")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")
        if not 0.0 < temperature <= 1.0:
            raise ValueError("DeepMind reference temperature must lie in (0, 1]")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not 0.0 < top_p <= 1.0:
            raise ValueError("top_p must lie in (0, 1]")
        if max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be positive")
        config = synthid_mixin.DEFAULT_WATERMARKING_CONFIG
        ngram_len = int(config["ngram_len"])
        keys = tuple(int(value) for value in config["keys"])
        context_history_size = int(config["context_history_size"])
        self._torch = torch
        self._transformers = transformers
        self._model_id = model_id
        self._device = device
        self._max_new_tokens = max_new_tokens
        self._temperature = temperature
        self._top_k = top_k
        self._top_p = top_p
        self._tokenizer = transformers.AutoTokenizer.from_pretrained(model_id, padding_side="left")
        if self._tokenizer.eos_token_id is None:
            raise RuntimeError("the selected tokenizer must define eos_token_id")
        if self._tokenizer.pad_token_id is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._control_model = transformers.GPT2LMHeadModel.from_pretrained(model_id).to(device)
        self._watermarked_model = synthid_mixin.SynthIDGPT2LMHeadModel.from_pretrained(model_id).to(device)
        self._control_model.eval()
        self._watermarked_model.eval()
        self._adapter = DeepMindReferenceAdapter(
            DeepMindReferenceConfig(
                ngram_len=ngram_len,
                keys=keys,
                context_history_size=context_history_size,
            )
        )
        self._detector_config_hash = sha256_json(
            {
                "detector_algorithm_version": WEIGHTED_MEAN_ALGORITHM_VERSION,
                "adapter_config_hash": self._adapter.configuration_fingerprint(),
                "adapter_source_commit": DEEPMIND_REFERENCE_SOURCE_PIN.commit,
                "prompt_boundary_mode": "decoded-completion-only",
                "weights": None,
            }
        )

    @property
    def backend_id(self) -> str:
        return DEEPMIND_BACKEND_ID

    @property
    def backend_version(self) -> str:
        return (
            f"synthid-text={DEEPMIND_REFERENCE_SOURCE_PIN.commit};"
            f"transformers={self._transformers.__version__};"
            f"torch={self._torch.__version__};device={self._device}"
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def detector_id(self) -> str:
        return f"fuckmark-weighted-mean:{WEIGHTED_MEAN_ALGORITHM_VERSION}"

    @property
    def detector_config_hash(self) -> str:
        return self._detector_config_hash

    def generate(self, prompt: str, seed: int, *, watermarked: bool) -> str:
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
            "max_new_tokens": self._max_new_tokens,
            "pad_token_id": self._tokenizer.pad_token_id,
        }
        model = self._watermarked_model if watermarked else self._control_model
        with torch.inference_mode():
            output = model.generate(**encoded, **kwargs)
        prompt_length = int(encoded["input_ids"].shape[1])
        continuation = output[0, prompt_length:].detach().cpu().tolist()
        text = self._tokenizer.decode(continuation, skip_special_tokens=True)
        if not text:
            raise RuntimeError("generation produced an empty decoded continuation")
        return text

    def score(self, text: str) -> float:
        token_ids = self._tokenizer.encode(text, add_special_tokens=False)
        if len(token_ids) < self._adapter.ngram_len:
            raise RuntimeError("decoded continuation is too short for SynthID scoring")
        signals = self._adapter.signals(token_ids, self._tokenizer.eos_token_id)
        return weighted_mean_score(signals.g_values, signals.valid_mask)


def _load_prompts(path: Path | None, limit: int, seed_base: int) -> tuple[SynthIDSmokePrompt, ...]:
    if path is None:
        values = DEFAULT_PROMPTS
    else:
        values = tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if limit <= 0:
        raise ValueError("prompt limit must be positive")
    values = values[:limit]
    if not values:
        raise ValueError("prompt source contains no usable prompts")
    return tuple(
        SynthIDSmokePrompt(f"smoke-{index + 1:03d}", text, seed_base + index)
        for index, text in enumerate(values)
    )


def _write_csv(path: Path, report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "prompt_id",
        "seed",
        "control_pristine_score",
        "control_transformed_score",
        "watermark_pristine_score",
        "watermark_transformed_score",
        "control_score_shift",
        "watermark_score_drop",
        "control_changed",
        "watermark_changed",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for value in report.results:
            writer.writerow({field: getattr(value, field) for field in fields})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-smoke-deepmind")
    parser.add_argument("--model", default="openai-community/gpt2")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--prompt-limit", type=int, default=20)
    parser.add_argument("--seed-base", type=int, default=271000)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--target-fpr", type=float, default=0.05)
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-smoke-deepmind.json"))
    parser.add_argument("--csv", type=Path, default=Path("artifacts/synthid-smoke-deepmind.csv"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    prompts = _load_prompts(args.prompts, args.prompt_limit, args.seed_base)
    backend = DeepMindSynthIDSmokeBackend(
        args.model,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
    )
    report = run_synthid_smoke(prompts, backend, target_fpr=args.target_fpr)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(canonical_json_text(report) + "\n", encoding="utf-8")
    _write_csv(args.csv, report)
    summary = report.summary
    sys.stdout.write(f"report_hash={report.report_hash}\n")
    sys.stdout.write(f"prompt_count={summary.prompt_count}\n")
    sys.stdout.write(f"threshold={summary.threshold:.6f}\n")
    sys.stdout.write(f"control_fpr_before={summary.pristine_control_detection_rate:.3f}\n")
    sys.stdout.write(f"control_fpr_after={summary.transformed_control_detection_rate:.3f}\n")
    sys.stdout.write(f"watermark_detection_before={summary.pristine_watermark_detection_rate:.3f}\n")
    sys.stdout.write(f"watermark_detection_after={summary.transformed_watermark_detection_rate:.3f}\n")
    sys.stdout.write(f"mean_watermark_score_drop={summary.mean_watermark_score_drop:.6f}\n")
    sys.stdout.write(f"median_watermark_score_drop={summary.median_watermark_score_drop:.6f}\n")
    sys.stdout.write(f"json={args.json.as_posix()}\n")
    sys.stdout.write(f"csv={args.csv.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
