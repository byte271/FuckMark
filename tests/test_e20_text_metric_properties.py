from itertools import product

from fuckmark.experiments.e20_row_verification import _levenshtein, _word_tokens


def _reference_distance(left, right):
    a = tuple(left)
    b = tuple(right)
    previous = list(range(len(b) + 1))
    for i, left_value in enumerate(a, 1):
        current = [i]
        for j, right_value in enumerate(b, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def _binary_sequences(max_length: int):
    for length in range(max_length + 1):
        yield from product((0, 1), repeat=length)


def test_bit_parallel_levenshtein_matches_reference_on_all_small_binary_sequences() -> None:
    values = tuple(_binary_sequences(5))
    for left in values:
        for right in values:
            assert _levenshtein(left, right) == _reference_distance(left, right)


def test_bit_parallel_levenshtein_matches_reference_on_unicode_words_and_characters() -> None:
    pairs = (
        ("", "abc"),
        ("café", "cafe"),
        ("can't stop", "cannot stop"),
        ("alpha—beta", "alpha beta"),
        ("你好世界", "你好，世界"),
        ("naïve coöperate", "naive cooperate"),
    )
    for left, right in pairs:
        assert _levenshtein(tuple(left), tuple(right)) == _reference_distance(tuple(left), tuple(right))
        assert _levenshtein(_word_tokens(left), _word_tokens(right)) == _reference_distance(
            _word_tokens(left),
            _word_tokens(right),
        )


def test_word_tokenizer_keeps_internal_apostrophe_and_hyphen_but_excludes_punctuation() -> None:
    assert _word_tokens("Can't re-enter, naïve user!") == ("Can't", "re-enter", "naïve", "user")
