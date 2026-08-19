from fuckmark.experiments.candidate_density_diagnosis import (
    GENUINE_STRICT_B4_CANDIDATE_SCARCITY,
    STRICT_VISIBLE_COST_CEILING_DOMINATES,
    build_strict_scarcity_diagnosis,
    strict_character_edit_budget,
)
from fuckmark.hashing import sha256_text


def _artifact(lengths, b4_values, b6_values):
    rows = []
    counts = {}
    for index, (length, b4, b6) in enumerate(zip(lengths, b4_values, b6_values)):
        sample_id = f"source-{index}"
        counts[sample_id] = length
        rows.append(
            {
                "source_sample_id": sample_id,
                "strict_b4_reachable": b4,
                "strict_b6_reachable": b6,
            }
        )
    candidate = {
        "artifact_hash": sha256_text("candidate-density"),
        "rows": rows,
    }
    return candidate, counts


def test_strict_character_edit_budget_is_integer_floor():
    assert strict_character_edit_budget(226) == 3
    assert strict_character_edit_budget(263) == 3
    assert strict_character_edit_budget(267) == 4
    assert strict_character_edit_budget(400) == 6


def test_frozen_tinydev_shape_is_cost_ceiling_not_candidate_scarcity():
    lengths = (293, 263, 313, 247, 226, 267, 332, 317)
    b4 = (True, False, True, False, False, True, True, True)
    b6 = (False,) * 8
    candidate, counts = _artifact(lengths, b4, b6)
    artifact = build_strict_scarcity_diagnosis(
        source_corpus_hash=sha256_text("tinydev-corpus"),
        candidate_density_artifact=candidate,
        source_character_counts=counts,
    )
    assert artifact.decision == STRICT_VISIBLE_COST_CEILING_DOMINATES
    assert artifact.family_expansion_permitted is False
    assert sum(row.b4_cost_ceiling_limited for row in artifact.rows) == 3
    assert sum(row.b4_candidate_limited for row in artifact.rows) == 0
    assert sum(row.b6_cost_ceiling_limited for row in artifact.rows) == 8
    assert sum(row.b6_candidate_limited for row in artifact.rows) == 0


def test_candidate_scarcity_requires_budget_to_be_theoretically_reachable():
    candidate, counts = _artifact((500,), (False,), (False,))
    artifact = build_strict_scarcity_diagnosis(
        source_corpus_hash=sha256_text("tinydev-corpus"),
        candidate_density_artifact=candidate,
        source_character_counts=counts,
    )
    assert artifact.decision == GENUINE_STRICT_B4_CANDIDATE_SCARCITY
    assert artifact.family_expansion_permitted is True
    assert artifact.rows[0].maximum_minimum_cost_operations == 7
    assert artifact.rows[0].b4_candidate_limited is True


def test_character_count_ids_must_exactly_match_rows():
    candidate, counts = _artifact((400,), (True,), (False,))
    counts["extra"] = 400
    try:
        build_strict_scarcity_diagnosis(
            source_corpus_hash=sha256_text("tinydev-corpus"),
            candidate_density_artifact=candidate,
            source_character_counts=counts,
        )
    except ValueError as error:
        assert "exactly match" in str(error)
    else:
        raise AssertionError("expected exact ID binding failure")
