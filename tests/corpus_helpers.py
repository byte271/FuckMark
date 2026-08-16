from fuckmark.corpus import (
    CorpusDomain,
    CorpusSample,
    CorpusSplit,
    GenerationParameters,
    GenerationTokenRecord,
    KeySplit,
    ModelTokenizerIdentity,
    PaddingSide,
    PromptRecord,
    TokenTrack,
    WatermarkCondition,
    WatermarkLabel,
)
from fuckmark.hashing import sha256_text


REVISION = "a" * 40
WATERMARK_HASH = "b" * 64
SOURCE_HASH = "c" * 64


def model_identity(padding_side: PaddingSide = PaddingSide.LEFT) -> ModelTokenizerIdentity:
    return ModelTokenizerIdentity.create(
        model_id="example/model",
        model_revision=REVISION,
        tokenizer_id="example/tokenizer",
        tokenizer_revision=REVISION,
        chat_template_present=False,
        chat_template_hash=sha256_text(""),
        special_token_map_hash=sha256_text("{}"),
        padding_side=padding_side,
        bos_token_id=None,
        eos_token_id=2,
        pad_token_id=0,
        add_bos_token=False,
        add_eos_token=False,
    )


def generation(seed: int = 1, temperature: float = 0.8) -> GenerationParameters:
    return GenerationParameters.create(
        seed=seed,
        seed_policy_id="paired-seed-policy-v1",
        temperature=temperature,
        top_k=40,
        top_p=0.95,
        max_new_tokens=64,
        do_sample=True,
        dtype="float16",
        device="cuda:0",
        backend_id="transformers",
        backend_version="test-version",
    )


def generation_tokens(
    continuation: tuple[int, ...] = (7, 8, 9),
    identity: ModelTokenizerIdentity | None = None,
) -> GenerationTokenRecord:
    input_ids = (0, 0, 5, 6)
    chosen_identity = identity or model_identity()
    return GenerationTokenRecord.create(
        input_token_ids=input_ids,
        attention_mask=(0, 0, 1, 1),
        generated_sequence_ids=input_ids + continuation,
        continuation_start_index=len(input_ids),
        continuation_token_ids=continuation,
        prompt_length_after_templating=2,
        model_tokenizer_identity_hash=chosen_identity.identity_hash,
    )


def watermark(key_split: KeySplit = KeySplit.DEV) -> WatermarkCondition:
    return WatermarkCondition.create(WATERMARK_HASH, key_split, "key-001")


def prompt(
    prompt_id: str = "prompt-001",
    family_id: str = "family-001",
    split: CorpusSplit = CorpusSplit.ATTACK_DEVELOPMENT,
    text: str = "Explain a small deterministic system.",
) -> PromptRecord:
    return PromptRecord.create(
        prompt_id=prompt_id,
        prompt_family_id=family_id,
        domain=CorpusDomain.GENERAL_EXPLANATORY,
        split=split,
        source_id="fixture-prompts",
        source_hash=SOURCE_HASH,
        license_id="CC0-1.0",
        provenance="tests/corpus_helpers.py",
        text=text,
    )


def sample(
    sample_id: str,
    match_id: str,
    label: WatermarkLabel,
    prompt_record: PromptRecord,
    text: str,
    seed: int,
    key_split: KeySplit = KeySplit.DEV,
    model: ModelTokenizerIdentity | None = None,
    generation_parameters: GenerationParameters | None = None,
    tokens: GenerationTokenRecord | None = None,
) -> CorpusSample:
    chosen_model = model or model_identity()
    return CorpusSample.create(
        sample_id=sample_id,
        match_id=match_id,
        prompt_id=prompt_record.prompt_id,
        prompt_family_id=prompt_record.prompt_family_id,
        domain=prompt_record.domain,
        split=prompt_record.split,
        label=label,
        text=text,
        model=chosen_model,
        generation=generation_parameters or generation(seed),
        watermark=watermark(key_split),
        target_length=64,
        generation_tokens=tokens or generation_tokens((7, 8, 9, seed % 100 + 10), chosen_model),
    )
