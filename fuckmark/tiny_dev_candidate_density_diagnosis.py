from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import canonical_json_text
from .corpus import CorpusSplit, load_tiny_dev_corpus_json
from .experiments.candidate_density_diagnosis import build_strict_scarcity_diagnosis


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fuckmark-tiny-dev-candidate-density-diagnosis")
    parser.add_argument("--corpus-json", type=Path, required=True)
    parser.add_argument("--candidate-density-json", type=Path, required=True)
    parser.add_argument(
        "--artifact-json",
        type=Path,
        default=Path("artifacts/tiny-dev-strict-scarcity-diagnosis.json"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    corpus = load_tiny_dev_corpus_json(args.corpus_json)
    raw = json.loads(args.candidate_density_json.read_text(encoding="utf-8"))
    if raw.get("source_corpus_hash") != corpus.artifact_hash:
        raise RuntimeError("candidate-density artifact does not bind frozen TinyDev corpus")
    attack = tuple(
        sample
        for sample in corpus.manifest.samples
        if sample.split is CorpusSplit.ATTACK_DEVELOPMENT
    )
    counts = {sample.sample_id: len(sample.text) for sample in attack}
    artifact = build_strict_scarcity_diagnosis(
        source_corpus_hash=corpus.artifact_hash,
        candidate_density_artifact=raw,
        source_character_counts=counts,
    )
    args.artifact_json.parent.mkdir(parents=True, exist_ok=True)
    args.artifact_json.write_text(canonical_json_text(artifact) + "\n", encoding="utf-8")
    summary = {
        "source_count": len(artifact.rows),
        "b4_cost_ceiling_count": sum(row.b4_cost_ceiling_limited for row in artifact.rows),
        "b4_candidate_limited_count": sum(row.b4_candidate_limited for row in artifact.rows),
        "b6_cost_ceiling_count": sum(row.b6_cost_ceiling_limited for row in artifact.rows),
        "b6_candidate_limited_count": sum(row.b6_candidate_limited for row in artifact.rows),
        "character_budgets": [row.maximum_minimum_cost_operations for row in artifact.rows],
    }
    sys.stdout.write(f"artifact_hash={artifact.artifact_hash}\n")
    sys.stdout.write(f"decision={artifact.decision}\n")
    sys.stdout.write(f"family_expansion_permitted={str(artifact.family_expansion_permitted).lower()}\n")
    sys.stdout.write(f"summary={json.dumps(summary, sort_keys=True)}\n")
    sys.stdout.write(f"artifact_json={args.artifact_json.as_posix()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
