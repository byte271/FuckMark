from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .._validation import require_clean_string, require_sha256
from ..hashing import sha256_json
from ..transforms.scheduler import SchedulePolicy


DEVELOPMENT_EXPERIMENT_REGISTRY_VERSION = "development-experiment-registry-v1"


class DevelopmentExperimentId(str, Enum):
    E02 = "E02"
    E03 = "E03"
    E04 = "E04"
    E05 = "E05"
    E06 = "E06"
    E07 = "E07"
    E08 = "E08"
    E09 = "E09"
    E10 = "E10"
    E11 = "E11"


class DevelopmentDataScope(str, Enum):
    ATTACK_DEVELOPMENT = "attack_development"
    MECHANISM_FIXTURE = "mechanism_fixture"


class TransformSelectionAccess(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    KEY_BLIND = "key_blind"


@dataclass(frozen=True, slots=True)
class DevelopmentExperimentDefinition:
    experiment_id: DevelopmentExperimentId
    objective: str
    data_scope: DevelopmentDataScope
    requires_calibration: bool
    selection_access: TransformSelectionAccess
    scheduler_policies: tuple[SchedulePolicy, ...]
    dependencies: tuple[DevelopmentExperimentId, ...]
    evidence_criterion: str
    failure_rule: str
    interpretation_boundary: str
    definition_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, DevelopmentExperimentId):
            raise TypeError("experiment_id must be a DevelopmentExperimentId")
        if not isinstance(self.data_scope, DevelopmentDataScope):
            raise TypeError("data_scope must be a DevelopmentDataScope")
        if type(self.requires_calibration) is not bool:
            raise TypeError("requires_calibration must be a bool")
        if not isinstance(self.selection_access, TransformSelectionAccess):
            raise TypeError("selection_access must be a TransformSelectionAccess")
        for name, value in (
            ("objective", self.objective),
            ("evidence_criterion", self.evidence_criterion),
            ("failure_rule", self.failure_rule),
            ("interpretation_boundary", self.interpretation_boundary),
        ):
            require_clean_string(name, value)
        if not isinstance(self.scheduler_policies, tuple):
            raise TypeError("scheduler_policies must be a tuple")
        if any(not isinstance(value, SchedulePolicy) for value in self.scheduler_policies):
            raise TypeError("scheduler_policies must contain SchedulePolicy values")
        if len(set(self.scheduler_policies)) != len(self.scheduler_policies):
            raise ValueError("scheduler_policies must not contain duplicates")
        if not isinstance(self.dependencies, tuple):
            raise TypeError("dependencies must be a tuple")
        if any(not isinstance(value, DevelopmentExperimentId) for value in self.dependencies):
            raise TypeError("dependencies must contain DevelopmentExperimentId values")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must not contain duplicates")
        if self.experiment_id in self.dependencies:
            raise ValueError("an experiment cannot depend on itself")
        if self.selection_access is TransformSelectionAccess.NOT_APPLICABLE and self.scheduler_policies:
            raise ValueError("non-transform experiments cannot declare scheduler policies")
        if self.scheduler_policies and self.selection_access is not TransformSelectionAccess.KEY_BLIND:
            raise ValueError("development transform schedules must use the key-blind selection boundary")
        require_sha256("definition_hash", self.definition_hash)
        if self.definition_hash != sha256_json(self._payload()):
            raise ValueError("definition_hash does not match experiment definition")

    def _payload(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id.value,
            "objective": self.objective,
            "data_scope": self.data_scope.value,
            "requires_calibration": self.requires_calibration,
            "selection_access": self.selection_access.value,
            "scheduler_policies": tuple(value.value for value in self.scheduler_policies),
            "dependencies": tuple(value.value for value in self.dependencies),
            "evidence_criterion": self.evidence_criterion,
            "failure_rule": self.failure_rule,
            "interpretation_boundary": self.interpretation_boundary,
        }

    @classmethod
    def create(
        cls,
        experiment_id: DevelopmentExperimentId,
        objective: str,
        data_scope: DevelopmentDataScope,
        requires_calibration: bool,
        selection_access: TransformSelectionAccess,
        scheduler_policies: tuple[SchedulePolicy, ...],
        dependencies: tuple[DevelopmentExperimentId, ...],
        evidence_criterion: str,
        failure_rule: str,
        interpretation_boundary: str,
    ) -> DevelopmentExperimentDefinition:
        payload = {
            "experiment_id": experiment_id.value,
            "objective": objective,
            "data_scope": data_scope.value,
            "requires_calibration": requires_calibration,
            "selection_access": selection_access.value,
            "scheduler_policies": tuple(value.value for value in scheduler_policies),
            "dependencies": tuple(value.value for value in dependencies),
            "evidence_criterion": evidence_criterion,
            "failure_rule": failure_rule,
            "interpretation_boundary": interpretation_boundary,
        }
        return cls(
            experiment_id,
            objective,
            data_scope,
            requires_calibration,
            selection_access,
            scheduler_policies,
            dependencies,
            evidence_criterion,
            failure_rule,
            interpretation_boundary,
            sha256_json(payload),
        )


_INTERPRETATION_BOUNDARY = "Development evidence cannot establish proprietary-system transfer or a confirmatory break claim"


def _definition(
    experiment_id: DevelopmentExperimentId,
    objective: str,
    data_scope: DevelopmentDataScope,
    requires_calibration: bool,
    selection_access: TransformSelectionAccess,
    scheduler_policies: tuple[SchedulePolicy, ...],
    dependencies: tuple[DevelopmentExperimentId, ...],
    evidence_criterion: str,
    failure_rule: str,
) -> DevelopmentExperimentDefinition:
    return DevelopmentExperimentDefinition.create(
        experiment_id,
        objective,
        data_scope,
        requires_calibration,
        selection_access,
        scheduler_policies,
        dependencies,
        evidence_criterion,
        failure_rule,
        _INTERPRETATION_BOUNDARY,
    )


DEVELOPMENT_EXPERIMENTS = (
    _definition(
        DevelopmentExperimentId.E02,
        "Establish detector power before perturbation",
        DevelopmentDataScope.ATTACK_DEVELOPMENT,
        True,
        TransformSelectionAccess.NOT_APPLICABLE,
        (),
        (),
        "Report TPR, FPR, AUC, and score distributions by frozen strata",
        "Weak pristine TPR marks the cell underpowered and cannot be interpreted as easy removal",
    ),
    _definition(
        DevelopmentExperimentId.E03,
        "Quantify denominator and mask behavior under controlled repetition",
        DevelopmentDataScope.MECHANISM_FIXTURE,
        False,
        TransformSelectionAccess.NOT_APPLICABLE,
        (),
        (),
        "Mask changes must reproduce pinned adapter behavior",
        "Unexpected mask behavior triggers adapter debugging",
    ),
    _definition(
        DevelopmentExperimentId.E04,
        "Validate local observation damage for one substitution",
        DevelopmentDataScope.MECHANISM_FIXTURE,
        False,
        TransformSelectionAccess.NOT_APPLICABLE,
        (),
        (),
        "Changed windows must agree with deterministic alignment and n-gram geometry",
        "Persistent unexplained suffix change rejects the observation implementation",
    ),
    _definition(
        DevelopmentExperimentId.E05,
        "Measure insertion index shift and recovered suffix observations",
        DevelopmentDataScope.MECHANISM_FIXTURE,
        False,
        TransformSelectionAccess.NOT_APPLICABLE,
        (),
        (DevelopmentExperimentId.E04,),
        "Conserved suffix n-grams must be recovered after resynchronization",
        "Index-only all-suffix destruction is an implementation failure",
    ),
    _definition(
        DevelopmentExperimentId.E06,
        "Measure deletion index shift and recovered suffix observations",
        DevelopmentDataScope.MECHANISM_FIXTURE,
        False,
        TransformSelectionAccess.NOT_APPLICABLE,
        (),
        (DevelopmentExperimentId.E04,),
        "Conserved suffix n-grams must be recovered after resynchronization",
        "Failure blocks downstream observation metrics",
    ),
    _definition(
        DevelopmentExperimentId.E07,
        "Compare word-edit rate and observation replacement as predictors of detector margin drop",
        DevelopmentDataScope.ATTACK_DEVELOPMENT,
        True,
        TransformSelectionAccess.KEY_BLIND,
        (),
        (DevelopmentExperimentId.E02, DevelopmentExperimentId.E04, DevelopmentExperimentId.E05, DevelopmentExperimentId.E06),
        "Prediction error comparison must be evaluated outside the fitting rows",
        "No predictor superiority claim is allowed from development-only fit performance",
    ),
    _definition(
        DevelopmentExperimentId.E08,
        "Estimate detector response over realized observation-replacement bins",
        DevelopmentDataScope.ATTACK_DEVELOPMENT,
        True,
        TransformSelectionAccess.KEY_BLIND,
        (),
        (DevelopmentExperimentId.E02, DevelopmentExperimentId.E07),
        "Report curves with uncertainty and measured monotonicity",
        "Non-monotonic results remain visible and cannot be smoothed away",
    ),
    _definition(
        DevelopmentExperimentId.E09,
        "Create a seeded non-optimized transform baseline",
        DevelopmentDataScope.ATTACK_DEVELOPMENT,
        True,
        TransformSelectionAccess.KEY_BLIND,
        (SchedulePolicy.RANDOM_VALID,),
        (DevelopmentExperimentId.E02,),
        "A seeded random baseline must exist for optimizer comparisons",
        "Missing random baseline invalidates better-than-baseline claims",
    ),
    _definition(
        DevelopmentExperimentId.E10,
        "Compare clustered and evenly spaced edits at matched cost",
        DevelopmentDataScope.ATTACK_DEVELOPMENT,
        True,
        TransformSelectionAccess.KEY_BLIND,
        (SchedulePolicy.CLUSTERED, SchedulePolicy.EVEN_SPACING),
        (DevelopmentExperimentId.E02,),
        "Use the same candidate pool and matched realized cost for paired coverage and detector comparison",
        "Unmatched cost requires adjustment or withholding the comparison",
    ),
    _definition(
        DevelopmentExperimentId.E11,
        "Test key-blind interval-union scheduling without secret feedback",
        DevelopmentDataScope.ATTACK_DEVELOPMENT,
        True,
        TransformSelectionAccess.KEY_BLIND,
        (SchedulePolicy.RANDOM_VALID, SchedulePolicy.COVERAGE_GREEDY_KEY_BLIND),
        (DevelopmentExperimentId.E02, DevelopmentExperimentId.E09),
        "Compare realized replacement per edit under the same candidate pool and budget",
        "Any key, g-value, or detector-score access during selection contaminates the T1 experiment",
    ),
)


@dataclass(frozen=True, slots=True)
class DevelopmentExperimentRegistry:
    version: str
    definitions: tuple[DevelopmentExperimentDefinition, ...]
    registry_hash: str

    def __post_init__(self) -> None:
        require_clean_string("version", self.version)
        if self.version != DEVELOPMENT_EXPERIMENT_REGISTRY_VERSION:
            raise ValueError("unsupported development experiment registry version")
        if not isinstance(self.definitions, tuple):
            raise TypeError("definitions must be a tuple")
        if any(not isinstance(value, DevelopmentExperimentDefinition) for value in self.definitions):
            raise TypeError("definitions must contain DevelopmentExperimentDefinition values")
        expected_ids = tuple(DevelopmentExperimentId)
        actual_ids = tuple(value.experiment_id for value in self.definitions)
        if actual_ids != expected_ids:
            raise ValueError("development experiment registry must contain E02 through E11 in exact order")
        id_positions = {value: index for index, value in enumerate(actual_ids)}
        for definition in self.definitions:
            for dependency in definition.dependencies:
                if id_positions[dependency] >= id_positions[definition.experiment_id]:
                    raise ValueError("experiment dependencies must refer only to earlier experiment IDs")
        require_sha256("registry_hash", self.registry_hash)
        if self.registry_hash != sha256_json(self._payload()):
            raise ValueError("registry_hash does not match development experiment registry")

    def _payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "definition_hashes": tuple(value.definition_hash for value in self.definitions),
        }

    def get(self, experiment_id: DevelopmentExperimentId) -> DevelopmentExperimentDefinition:
        if not isinstance(experiment_id, DevelopmentExperimentId):
            raise TypeError("experiment_id must be a DevelopmentExperimentId")
        return self.definitions[list(DevelopmentExperimentId).index(experiment_id)]


def default_development_experiment_registry() -> DevelopmentExperimentRegistry:
    payload = {
        "version": DEVELOPMENT_EXPERIMENT_REGISTRY_VERSION,
        "definition_hashes": tuple(value.definition_hash for value in DEVELOPMENT_EXPERIMENTS),
    }
    return DevelopmentExperimentRegistry(
        DEVELOPMENT_EXPERIMENT_REGISTRY_VERSION,
        DEVELOPMENT_EXPERIMENTS,
        sha256_json(payload),
    )
