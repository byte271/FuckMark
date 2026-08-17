from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .adapters.huggingface_synthid import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig
from .config import canonical_json_text
from .detectors.mean import WEIGHTED_MEAN_ALGORITHM_VERSION, weighted_mean_score
from .experiments.synthid_smoke import SynthIDSmokePrompt, run_synthid_smoke
from .hashing import sha256_json


DEFAULT_KEYS = (654, 400, 836, 123, 340, 443, 597, 160, 57)
DEFAULT_NGRAM_LEN = 5
DEFAULT_PROMPTS = (
    "Write a formal paragraph with no contractions explaining why careful testing matters before making a scientific claim.",
    "Write a formal paragraph with no contractions explaining why a map can be useful but cannot replace direct observation.",
    "Write a formal paragraph with no contractions about why software should not silently ignore invalid data.",
    "Write a formal paragraph with no contractions describing what a student should do when an experiment does not match a prediction.",
    "Write a formal paragraph with no contractions explaining why a measurement may fail even when an idea is reasonable.",
    "Write a formal paragraph with no contractions about why repeated results are more convincing than one surprising result.",
    "Write a formal paragraph with no contractions explaining why a detector should not be judged from only one example.",
    "Write a formal paragraph with no contractions about why preserving numbers and quotations matters when editing text.",
    "Write a formal paragraph with no contractions explaining why a control group is necessary in an experiment.",
    "Write a formal paragraph with no contractions about why researchers cannot assume that one model represents every model.",
    "Write a formal paragraph with no contractions explaining why a low false positive rate matters for a detector.",
    "Write a formal paragraph with no contractions about why an experiment should not change its rules after seeing the result.",
    "Write a formal paragraph with no contractions explaining why random baselines are useful when evaluating an optimization method.",
    "Write a formal paragraph with no contractions about why text quality should remain acceptable after a transformation.",
    "Write a formal paragraph with no contractions explaining why a secret key should not be used by a key blind transformation policy.",
    "Write a formal paragraph with no contractions about why longer texts may behave differently from shorter texts.",
    "Write a formal paragraph with no contractions explaining why tokenization can change after punctuation or spacing edits.",
    "Write a formal paragraph with no contractions about why independent replication can reveal accidental findings.",
    "Write a formal paragraph with no contractions explaining why failed transformations should remain visible in aggregate results.",
    "Write a formal paragraph with no contractions about why evidence should not be stronger than the experiment that produced it.",
)


class HuggingFaceSynthIDSmokeBackend:
    def __init__(
        self,
        model_id: str,
        *,
        device: str,
        max_new_tokens: int,
        temperature: float,
        top_k: int,
        top_p: float,
        ngram_len: int,
        keys: tuple[int, ...],
    ) -> None:
        try:
            import torch
            import transformers
            from transformers import AutoModelForCausalLM, AutoTokenizer, SynthIDTextWatermarkingConfig
        except ImportError as error:
            raise RuntimeError("Install the smoke extra before running the Hugging Face SynthID smoke experiment") from error
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device not in {"cpu", "cuda"}:
            raise ValueError("device must be auto, cpu, or cuda")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")
        self._torch = torch
        self._transformers = transformers
        self._model_id = model_id
        self._device = device
        self._max_new_tokens = max_new_tokens
        self._temperature = temperature
        self._top_k = top_k
        self._top_p = top_p
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        if self._tokenizer.eos_token_id is None:
            raise RuntimeError("the selected tokenizer must define eos_token_id")
        if self._tokenizer.pad_token_id is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._model = AutoModelForCausalLM.from_pretrained(model_id)
        self._model.to(device)
        self._model.eval()
        self._watermark_config = SynthIDTextWatermarkingConfig(
            ngram_len=ngram_len,
            keys=list(keys),
        )
        adapter_config = HuggingFaceSynthIDConfig(
            ngram_len=ngram_len,
            keys=keys,
        )
        self._adapter = HuggingFaceSynthIDAdapter.from_torch(adapter_config, device=device)
        self._detector_config_hash = sha256_json(
            {
                "detector_algorithm_version": WEIGHTED_MEAN_ALGORITHM_VERSION,
                "adapter_config_hash": self._adapter.configuration_fingerprint(),
                "prompt_boundary_mode": "decoded-completion-only",
                "weights": None,
            }
        )

    @property
    def backend_id(self) -> str:
        return "huggingface-transformers-synthid-generation"

    @property
    def backend_version(self) -> str:
        return f"transformers={self._transformers.__version__};torch={self._torch.__version__};device={self._device}"

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
        if watermarked:
            kwargs["watermarking_config"] = self._watermark_config
        with torch.inference_mode():
            output = self._model.generate(**encoded, **kwargs)
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
    parser = argparse.ArgumentParser(prog="fuckmark-synthid-smoke")
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
    parser.add_argument("--json", type=Path, default=Path("artifacts/synthid-smoke.json"))
    parser.add_argument("--csv", type=Path, default=Path("artifacts/synthid-smoke.csv"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    prompts = _load_prompts(args.prompts, args.prompt_limit, args.seed_base)
    backend = HuggingFaceSynthIDSmokeBackend(
        args.model,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
        top_p=args.top_p,
        ngram_len=DEFAULT_NGRAM_LEN,
        keys=DEFAULT_KEYS,
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
