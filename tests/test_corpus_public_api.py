import fuckmark


def test_corpus_public_api_is_exported_from_package_root() -> None:
    names = (
        "CorpusManifest",
        "CorpusSample",
        "PromptRecord",
        "GenerationTokenRecord",
        "TextOnlyTokenRecord",
        "ModelTokenizerIdentity",
        "GenerationParameters",
        "WatermarkCondition",
        "build_corpus_manifest",
    )
    for name in names:
        assert hasattr(fuckmark, name)


def test_corpus_manifest_component_version_is_stable() -> None:
    assert fuckmark.CORPUS_MANIFEST_ALGORITHM_VERSION == "fuckmark-corpus-manifest-v1"
