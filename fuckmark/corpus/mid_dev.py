from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from .._validation import require_clean_string, require_int, require_sha256
from ..hashing import sha256_json
from .manifest import CorpusManifest, build_corpus_manifest
from .prompt import PromptRecord
from .sample import CorpusSample
from .schema import CorpusDomain, CorpusSplit, KeySplit, WatermarkLabel


MID_DEV_CORPUS_ALGORITHM_VERSION = "mid-dev-context-survival-corpus-v1"
MID_DEV_TARGET_LENGTHS = (128, 256)
MID_DEV_SOURCE_COUNT = 36
MID_DEV_SOURCES_PER_LENGTH = 18
MID_DEV_SOURCES_PER_FAMILY_LENGTH = 3
MID_DEV_PROMPT_SOURCE_ID = "fuckmark-mid-dev-context-survival-prompts-v1"
MID_DEV_PROMPT_LICENSE_ID = "LicenseRef-FuckMark-Unspecified"
MID_DEV_PROMPT_PROVENANCE = "fuckmark/corpus/mid_dev.py"


@dataclass(frozen=True, slots=True)
class MidDevPromptFamily:
    family_id: str
    domain: CorpusDomain
    template: str

    def __post_init__(self) -> None:
        require_clean_string("family_id", self.family_id)
        if not isinstance(self.domain, CorpusDomain):
            raise TypeError("domain must be a CorpusDomain")
        require_clean_string("template", self.template)
        if "{topic}" not in self.template or "{target_length}" not in self.template:
            raise ValueError("MidDev prompt template must bind topic and target_length")


MID_DEV_PROMPT_FAMILIES = (
    MidDevPromptFamily(
        "middev-general-expository",
        CorpusDomain.GENERAL_EXPLANATORY,
        "Explain {topic} in a coherent expository paragraph of enough detail to support about {target_length} continuation tokens. Avoid lists.",
    ),
    MidDevPromptFamily(
        "middev-technical-causal",
        CorpusDomain.TECHNICAL_EXPLANATION,
        "Give a multi-sentence technical explanation of how {topic} causes downstream effects in software experiments. Include mechanism, failure mode, and validation check. Aim for about {target_length} continuation tokens.",
    ),
    MidDevPromptFamily(
        "middev-structured-procedural",
        CorpusDomain.STRUCTURED_INSTRUCTIONAL,
        "Describe a practical procedure for handling {topic}. Use complete sentences with concrete sequencing and enough detail for about {target_length} continuation tokens.",
    ),
    MidDevPromptFamily(
        "middev-contrast-comparison",
        CorpusDomain.GENERAL_EXPLANATORY,
        "Compare two reasonable approaches to {topic}, explaining tradeoffs, when each is preferable, and one shared failure mode. Write about {target_length} continuation tokens.",
    ),
    MidDevPromptFamily(
        "middev-casual-assistant",
        CorpusDomain.CONVERSATIONAL_PROSE,
        "A colleague casually asks about {topic}. Answer naturally but precisely, with enough connected detail for about {target_length} continuation tokens.",
    ),
    MidDevPromptFamily(
        "middev-narrative-explanation",
        CorpusDomain.CONVERSATIONAL_PROSE,
        "Explain {topic} through a short realistic narrative about a research team discovering a problem and correcting it. Keep the explanation technically accurate and about {target_length} continuation tokens.",
    ),
)


MID_DEV_TOPICS = (
    "reproducible random seeds",
    "calibration drift",
    "held-out evaluation",
    "source-level uncertainty",
    "tokenization changes",
    "protected spans",
    "matched negative controls",
    "model revision pinning",
    "deterministic replay",
    "multiple testing",
    "measurement uncertainty",
    "failure logging",
    "domain shift",
    "prompt boundary handling",
    "candidate enumeration",
    "semantic fidelity checks",
    "edit budget accounting",
    "confidence intervals",
    "data provenance",
    "selection leakage",
    "independent source groups",
    "randomized baselines",
    "plan freezing",
    "repetition masking",
    "counterfactual retokenization",
    "alignment ambiguity",
    "risk tier ceilings",
    "beam search pruning",
    "Pareto frontiers",
    "control score stability",
    "false-positive monitoring",
    "sampling-table identity",
    "key separation",
    "effect-size reporting",
    "bootstrap resampling",
    "null-result interpretation",
)


class MidDevCorpusError(ValueError):
    pass


def _prompt_source_hash() -> str:
    return sha256_json(
        {
            "algorithm_version": MID_DEV_CORPUS_ALGORITHM_VERSION,
            "source_id": MID_DEV_PROMPT_SOURCE_ID,
            "license_id": MID_DEV_PROMPT_LICENSE_ID,
            "provenance": MID_DEV_PROMPT_PROVENANCE,
            "families": MID_DEV_PROMPT_FAMILIES,
            "topics": MID_DEV_TOPICS,
            "target_lengths": MID_DEV_TARGET_LENGTHS,
        }
    )


def build_mid_dev_prompt_records() -> tuple[PromptRecord, ...]:
    expected_topic_count = len(MID_DEV_PROMPT_FAMILIES) * len(MID_DEV_TARGET_LENGTHS) * MID_DEV_SOURCES_PER_FAMILY_LENGTH
    if len(MID_DEV_TOPICS) != expected_topic_count:
        raise RuntimeError("MidDev topics do not match the frozen source matrix")
    source_hash = _prompt_source_hash()
    output: list[PromptRecord] = []
    topic_index = 0
    for target_length in MID_DEV_TARGET_LENGTHS:
        for family in MID_DEV_PROMPT_FAMILIES:
            for local_index in range(MID_DEV_SOURCES_PER_FAMILY_LENGTH):
                topic = MID_DEV_TOPICS[topic_index]
                prompt_id = f"middev-{target_length}-{family.family_id}-{local_index:02d}"
                output.append(
                    PromptRecord.create(
                        prompt_id=prompt_id,
                        prompt_family_id=family.family_id,
                        domain=family.domain,
                        split=CorpusSplit.ATTACK_DEVELOPMENT,
                        source_id=MID_DEV_PROMPT_SOURCE_ID,
                        source_hash=source_hash,
                        license_id=MID_DEV_PROMPT_LICENSE_ID,
                        provenance=MID_DEV_PROMPT_PROVENANCE,
                        text=family.template.format(topic=topic, target_length=target_length),
                    )
                )
                topic_index += 1
    return tuple(sorted(output, key=lambda value: value.prompt_id))


def mid_dev_target_length_for_prompt(prompt_id: str) -> int:
    require_clean_string("prompt_id", prompt_id)
    for value in MID_DEV_TARGET_LENGTHS:
        if prompt_id.startswith(f"middev-{value}-"):
            return value
    raise MidDevCorpusError("prompt_id does not bind a frozen MidDev target length")


@dataclass(frozen=True, slots=True)
class MidDevAttackArtifact:
    algorithm_version: str
    manifest: CorpusManifest
    source_count: int
    target_lengths: tuple[int, ...]
    family_ids: tuple[str, ...]
    source_profile_hash: str
    artifact_hash: str

    def __post_init__(self) -> None:
        require_clean_string("algorithm_version", self.algorithm_version)
        if self.algorithm_version != MID_DEV_CORPUS_ALGORITHM_VERSION:
            raise ValueError("unsupported MidDev corpus algorithm version")
        if not isinstance(self.manifest, CorpusManifest):
            raise TypeError("manifest must be a CorpusManifest")
        require_int("source_count", self.source_count)
        if self.source_count != MID_DEV_SOURCE_COUNT:
            raise ValueError("MidDev source_count must match the frozen profile")
        if self.target_lengths != MID_DEV_TARGET_LENGTHS:
            raise ValueError("MidDev target lengths must match the frozen profile")
        expected_families = tuple(value.family_id for value in MID_DEV_PROMPT_FAMILIES)
        if self.family_ids != expected_families:
            raise ValueError("MidDev family IDs must match the frozen profile")
        require_sha256("source_profile_hash", self.source_profile_hash)
        require_sha256("artifact_hash", self.artifact_hash)
        _validate_mid_dev_manifest(self.manifest)
        if self.artifact_hash != sha256_json(self.payload()):
            raise ValueError("artifact_hash does not match MidDev attack artifact")

    def payload(self) -> dict[str, object]:
        return {
            "algorithm_version": self.algorithm_version,
            "manifest_hash": self.manifest.manifest_hash,
            "source_count": self.source_count,
            "target_lengths": self.target_lengths,
            "family_ids": self.family_ids,
            "source_profile_hash": self.source_profile_hash,
        }


def _validate_mid_dev_manifest(manifest: CorpusManifest) -> None:
    prompts = manifest.prompts
    samples = manifest.samples
    if len(prompts) != MID_DEV_SOURCE_COUNT:
        raise MidDevCorpusError(f"MidDev must contain exactly {MID_DEV_SOURCE_COUNT} independent prompts")
    if len(samples) != MID_DEV_SOURCE_COUNT * 2:
        raise MidDevCorpusError("MidDev must contain exactly one matched on/off pair per source")
    if len({sample.match_id for sample in samples}) != MID_DEV_SOURCE_COUNT:
        raise MidDevCorpusError("MidDev match IDs must identify exactly 36 independent source groups")
    if len({prompt.prompt_id for prompt in prompts}) != MID_DEV_SOURCE_COUNT:
        raise MidDevCorpusError("MidDev prompt IDs must be unique")
    if len({prompt.text_sha256 for prompt in prompts}) != MID_DEV_SOURCE_COUNT:
        raise MidDevCorpusError("MidDev prompt texts must be unique across source groups")
    if any(prompt.split is not CorpusSplit.ATTACK_DEVELOPMENT for prompt in prompts):
        raise MidDevCorpusError("MidDev prompts must use attack-development split only")
    if any(sample.split is not CorpusSplit.ATTACK_DEVELOPMENT for sample in samples):
        raise MidDevCorpusError("MidDev samples must use attack-development split only")
    if any(sample.watermark.key_split is not KeySplit.DEV for sample in samples):
        raise MidDevCorpusError("MidDev samples must use DEV_KEYS only")
    expected_family_ids = {value.family_id for value in MID_DEV_PROMPT_FAMILIES}
    if {prompt.prompt_family_id for prompt in prompts} != expected_family_ids:
        raise MidDevCorpusError("MidDev must contain every frozen prompt family")
    prompt_by_id = {prompt.prompt_id: prompt for prompt in prompts}
    length_counts: Counter[int] = Counter()
    family_length_counts: Counter[tuple[str, int]] = Counter()
    for prompt in prompts:
        target_length = mid_dev_target_length_for_prompt(prompt.prompt_id)
        length_counts[target_length] += 1
        family_length_counts[(prompt.prompt_family_id, target_length)] += 1
    if dict(length_counts) != {value: MID_DEV_SOURCES_PER_LENGTH for value in MID_DEV_TARGET_LENGTHS}:
        raise MidDevCorpusError("MidDev source counts must be balanced across 128/256 lengths")
    expected_family_length_counts = {
        (family.family_id, target_length): MID_DEV_SOURCES_PER_FAMILY_LENGTH
        for target_length in MID_DEV_TARGET_LENGTHS
        for family in MID_DEV_PROMPT_FAMILIES
    }
    if dict(family_length_counts) != expected_family_length_counts:
        raise MidDevCorpusError("MidDev source counts must be balanced across prompt-family and length cells")
    by_match: dict[str, list[CorpusSample]] = {}
    for sample in samples:
        by_match.setdefault(sample.match_id, []).append(sample)
        prompt = prompt_by_id.get(sample.prompt_id)
        if prompt is None:
            raise MidDevCorpusError("MidDev sample references an unknown prompt")
        expected_length = mid_dev_target_length_for_prompt(prompt.prompt_id)
        if sample.target_length != expected_length:
            raise MidDevCorpusError("MidDev sample target length does not match its prompt cell")
        if sample.prompt_family_id != prompt.prompt_family_id or sample.domain is not prompt.domain:
            raise MidDevCorpusError("MidDev sample prompt metadata drifted")
    for values in by_match.values():
        if len(values) != 2:
            raise MidDevCorpusError("each MidDev source group must contain exactly two samples")
        if {value.label for value in values} != {WatermarkLabel.WATERMARKED, WatermarkLabel.UNWATERMARKED}:
            raise MidDevCorpusError("each MidDev source group must contain one watermarked and one control sample")
        if len({value.prompt_id for value in values}) != 1:
            raise MidDevCorpusError("matched MidDev samples must share one prompt")
        if len({value.generation.seed for value in values}) != 1:
            raise MidDevCorpusError("matched MidDev samples must share one generation seed")
        if len({value.generation.matching_signature_hash for value in values}) != 1:
            raise MidDevCorpusError("matched MidDev samples must share generation parameters")
        if values[0].text_sha256 == values[1].text_sha256:
            raise MidDevCorpusError("matched MidDev on/off generations must not be text-identical")
    if len({sample.text_sha256 for sample in samples}) != len(samples):
        raise MidDevCorpusError("MidDev generated texts must be globally unique")


def build_mid_dev_attack_artifact(
    corpus_id: str,
    prompts: Sequence[PromptRecord],
    samples: Sequence[CorpusSample],
) -> MidDevAttackArtifact:
    require_clean_string("corpus_id", corpus_id)
    manifest = build_corpus_manifest(corpus_id, prompts, samples)
    _validate_mid_dev_manifest(manifest)
    profile_payload = {
        "algorithm_version": MID_DEV_CORPUS_ALGORITHM_VERSION,
        "source_count": MID_DEV_SOURCE_COUNT,
        "target_lengths": MID_DEV_TARGET_LENGTHS,
        "families": MID_DEV_PROMPT_FAMILIES,
        "prompt_source_hash": _prompt_source_hash(),
    }
    source_profile_hash = sha256_json(profile_payload)
    payload = {
        "algorithm_version": MID_DEV_CORPUS_ALGORITHM_VERSION,
        "manifest_hash": manifest.manifest_hash,
        "source_count": MID_DEV_SOURCE_COUNT,
        "target_lengths": MID_DEV_TARGET_LENGTHS,
        "family_ids": tuple(value.family_id for value in MID_DEV_PROMPT_FAMILIES),
        "source_profile_hash": source_profile_hash,
    }
    return MidDevAttackArtifact(
        MID_DEV_CORPUS_ALGORITHM_VERSION,
        manifest,
        MID_DEV_SOURCE_COUNT,
        MID_DEV_TARGET_LENGTHS,
        tuple(value.family_id for value in MID_DEV_PROMPT_FAMILIES),
        source_profile_hash,
        sha256_json(payload),
    )
