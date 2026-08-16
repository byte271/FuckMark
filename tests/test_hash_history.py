from fuckmark.adapters._lcg import BoundedHashHistory


def test_bounded_hash_history_matches_zero_initialized_fixed_window() -> None:
    values = (0, 5, 0, 7, 5, 9, 0, 11)
    for size in range(1, 7):
        compact = BoundedHashHistory(size)
        naive = [0] * size
        for value in values:
            assert compact.contains(value) == (value in naive)
            compact.push(value)
            naive = [value, *naive[:-1]]


def test_bounded_hash_history_does_not_preallocate_declared_capacity() -> None:
    history = BoundedHashHistory(10**9)
    assert len(history._values) == 0
    history.push(7)
    assert len(history._values) == 1
    assert history.contains(7) is True


def test_adapters_do_not_preallocate_declared_context_history_capacity() -> None:
    from fuckmark.adapters.deepmind_reference import DeepMindReferenceAdapter, DeepMindReferenceConfig
    from fuckmark.adapters.huggingface_synthid import HuggingFaceSynthIDAdapter, HuggingFaceSynthIDConfig

    deepmind = DeepMindReferenceAdapter(DeepMindReferenceConfig(3, (7,), 10**9))
    huggingface = HuggingFaceSynthIDAdapter(
        HuggingFaceSynthIDConfig(3, (7,), context_history_size=10**9, sampling_table_size=8),
        bytes((0, 1, 0, 1, 0, 1, 0, 1)),
        "fixture",
    )
    assert deepmind.compute_context_repetition_mask([1, 2, 3, 4]) == (True, True)
    assert huggingface.compute_context_repetition_mask([1, 2, 3, 4]) == (True, True)
