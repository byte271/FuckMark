from dataclasses import replace

import pytest

from fuckmark.observations import build_token_ngrams


def test_token_ngram_rejects_index_start_geometry_mismatch() -> None:
    ngram = build_token_ngrams((10, 20, 30, 40), 3)[0]
    assert ngram.index == ngram.start == 0
    with pytest.raises(ValueError, match="index|start|geometry"):
        replace(ngram, index=ngram.index + 1)
