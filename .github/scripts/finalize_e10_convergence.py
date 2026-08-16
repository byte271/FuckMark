from pathlib import Path


path = Path("fuckmark/experiments/schedule_analysis.py")
text = path.read_text()

function_start = text.index("def run_e10_spacing_comparison(")
definition_anchor = "    definition = default_development_experiment_registry().get(DevelopmentExperimentId.E10)\n"
definition_index = text.index(definition_anchor, function_start)
status_block = (
    "    if missing:\n"
    "        status = E10Status.INCOMPLETE\n"
    "    elif unmatched_count:\n"
    "        status = E10Status.WITHHELD_UNMATCHED_COST\n"
    "    else:\n"
    "        status = E10Status.COMPLETE_MATCHED\n"
)
if status_block not in text[function_start:definition_index]:
    text = text[:definition_index] + status_block + text[definition_index:]

class_start = text.index("class E10SpacingComparisonResult:")
class_payload_start = text.index("    def _payload(self) -> dict[str, object]:", class_start)
function_start = text.index("def run_e10_spacing_comparison(", class_payload_start)
canonical_class_payload = (
    "    def _payload(self) -> dict[str, object]:\n"
    "        return {\n"
    "            \"algorithm_version\": self.algorithm_version,\n"
    "            \"experiment_definition_hash\": self.experiment_definition_hash,\n"
    "            \"tiny_dev_artifact_hash\": self.tiny_dev_artifact_hash,\n"
    "            \"detector_identity_hash\": self.detector_identity_hash,\n"
    "            \"threshold_hash\": self.threshold_hash,\n"
    "            \"pair_hashes\": self.pair_hashes,\n"
    "            \"expected_source_count\": self.expected_source_count,\n"
    "            \"observed_source_count\": self.observed_source_count,\n"
    "            \"missing_source_ids\": self.missing_source_ids,\n"
    "            \"matched_pair_count\": self.matched_pair_count,\n"
    "            \"unmatched_cost_pair_count\": self.unmatched_cost_pair_count,\n"
    "            \"mean_coverage_difference_even_minus_clustered\": self.mean_coverage_difference_even_minus_clustered,\n"
    "            \"mean_observation_ratio_difference_even_minus_clustered\": self.mean_observation_ratio_difference_even_minus_clustered,\n"
    "            \"mean_margin_drop_difference_even_minus_clustered\": self.mean_margin_drop_difference_even_minus_clustered,\n"
    "            \"comparison_withheld_for_unmatched_cost\": self.comparison_withheld_for_unmatched_cost,\n"
    "            \"status\": self.status.value,\n"
    "        }\n\n\n"
)
text = text[:class_payload_start] + canonical_class_payload + text[function_start:]

function_start = text.index("def run_e10_spacing_comparison(")
pair_hashes_index = text.index(
    "    pair_hashes = tuple(sorted(value.pair_hash for value in pair_tuple))\n",
    function_start,
)
run_payload_start = text.index("    payload = {\n", pair_hashes_index)
return_start = text.index("    return E10SpacingComparisonResult(", run_payload_start)
canonical_run_payload = (
    "    payload = {\n"
    "        \"algorithm_version\": E10_ALGORITHM_VERSION,\n"
    "        \"experiment_definition_hash\": definition.definition_hash,\n"
    "        \"tiny_dev_artifact_hash\": artifact.artifact_hash,\n"
    "        \"detector_identity_hash\": detector_identity_hash,\n"
    "        \"threshold_hash\": threshold_hash,\n"
    "        \"pair_hashes\": pair_hashes,\n"
    "        \"expected_source_count\": len(expected_ids),\n"
    "        \"observed_source_count\": len(observed_source_ids),\n"
    "        \"missing_source_ids\": missing,\n"
    "        \"matched_pair_count\": len(matched),\n"
    "        \"unmatched_cost_pair_count\": unmatched_count,\n"
    "        \"mean_coverage_difference_even_minus_clustered\": _mean(coverage_values),\n"
    "        \"mean_observation_ratio_difference_even_minus_clustered\": _mean(observation_values),\n"
    "        \"mean_margin_drop_difference_even_minus_clustered\": _mean(margin_values),\n"
    "        \"comparison_withheld_for_unmatched_cost\": unmatched_count > 0,\n"
    "        \"status\": status.value,\n"
    "    }\n"
)
text = text[:run_payload_start] + canonical_run_payload + text[return_start:]

function_start = text.index("def run_e10_spacing_comparison(")
return_start = text.index("    return E10SpacingComparisonResult(", function_start)
next_section = text.index("\n\n\n@dataclass", return_start)
canonical_constructor = (
    "    return E10SpacingComparisonResult(\n"
    "        algorithm_version=E10_ALGORITHM_VERSION,\n"
    "        experiment_definition_hash=definition.definition_hash,\n"
    "        tiny_dev_artifact_hash=artifact.artifact_hash,\n"
    "        detector_identity_hash=detector_identity_hash,\n"
    "        threshold_hash=threshold_hash,\n"
    "        pair_hashes=pair_hashes,\n"
    "        expected_source_count=len(expected_ids),\n"
    "        observed_source_count=len(observed_source_ids),\n"
    "        missing_source_ids=missing,\n"
    "        matched_pair_count=len(matched),\n"
    "        unmatched_cost_pair_count=unmatched_count,\n"
    "        mean_coverage_difference_even_minus_clustered=payload[\"mean_coverage_difference_even_minus_clustered\"],\n"
    "        mean_observation_ratio_difference_even_minus_clustered=payload[\"mean_observation_ratio_difference_even_minus_clustered\"],\n"
    "        mean_margin_drop_difference_even_minus_clustered=payload[\"mean_margin_drop_difference_even_minus_clustered\"],\n"
    "        comparison_withheld_for_unmatched_cost=unmatched_count > 0,\n"
    "        status=status,\n"
    "        result_hash=sha256_json(payload),\n"
    "    )"
)
text = text[:return_start] + canonical_constructor + text[next_section:]
path.write_text(text)
