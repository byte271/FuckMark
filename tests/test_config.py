from pathlib import Path

import pytest

from fuckmark.config import canonical_json_text, canonicalize
from fuckmark.hashing import derive_seed, sha256_json


def test_mapping_order_does_not_change_canonical_json() -> None:
    first = {"b": 2, "a": 1}
    second = {"a": 1, "b": 2}
    assert canonical_json_text(first) == canonical_json_text(second)
    assert sha256_json(first) == sha256_json(second)


def test_tuple_and_list_share_canonical_sequence_representation() -> None:
    assert canonicalize((1, 2, 3)) == [1, 2, 3]
    assert canonicalize([1, 2, 3]) == [1, 2, 3]


def test_path_is_serialized_as_string() -> None:
    assert canonicalize(Path("data/file.json")) == "data/file.json"


def test_non_finite_float_is_rejected() -> None:
    with pytest.raises(ValueError):
        canonical_json_text({"value": float("nan")})


def test_seed_derivation_is_deterministic_and_scoped() -> None:
    a = derive_seed(42, "sample-1", "condition-a")
    b = derive_seed(42, "sample-1", "condition-a")
    c = derive_seed(42, "sample-1", "condition-b")
    assert a == b
    assert a != c


def test_seed_bit_width_is_enforced() -> None:
    value = derive_seed(42, "x", bits=16)
    assert 0 <= value < 2**16
    with pytest.raises(ValueError):
        derive_seed(42, "x", bits=0)


def test_non_string_mapping_keys_are_rejected_instead_of_colliding() -> None:
    with pytest.raises(TypeError):
        canonical_json_text({1: "integer", "1": "string"})


def test_frozenset_is_canonicalized_deterministically() -> None:
    assert canonical_json_text({"x": frozenset({3, 1, 2})}) == '{"x":[1,2,3]}'


def test_negative_zero_is_canonicalized_to_positive_zero() -> None:
    assert canonical_json_text({"x": -0.0}) == canonical_json_text({"x": 0.0})


def test_dataclass_type_is_rejected_without_instance() -> None:
    from dataclasses import dataclass

    @dataclass
    class Example:
        value: int

    with pytest.raises(TypeError):
        canonicalize(Example)
