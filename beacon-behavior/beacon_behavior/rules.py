from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .models import BeaconEvent
from .summary import build_summary
from .trajectory import ActionType, build_trajectory


class RuleLimits(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    test_attempts: int | None = None
    failed_attempts: int | None = None
    files_modified: int | None = None
    patch_operations: int | None = None


class BehaviorRules(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    require: list[str] = Field(
        default_factory=list
    )

    require_after_patch: list[str] = Field(
        default_factory=list
    )

    limits: RuleLimits = Field(
        default_factory=RuleLimits
    )

    require_additional_verification: bool = False


@dataclass
class RuleResult:
    passed: bool
    description: str


@dataclass
class EvaluationResult:
    passed: bool
    results: list[RuleResult]


def load_rules(
    path: str | Path,
) -> BehaviorRules:
    path = Path(path)

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = yaml.safe_load(file) or {}

    return BehaviorRules.model_validate(
        data
    )


def evaluate_run(
    events: list[BeaconEvent],
    rules: BehaviorRules,
) -> EvaluationResult:
    summary = build_summary(events)

    trajectory = build_trajectory(
        events,
        verbose=True,
    )

    results: list[RuleResult] = []

    #
    # Actions observed anywhere in the run
    #
    observed_actions = {
        action.action_type.value
        for action in trajectory
    }

    for required_action in rules.require:
        passed = (
            required_action
            in observed_actions
        )

        results.append(
            RuleResult(
                passed=passed,
                description=(
                    f"observed {required_action}"
                    if passed
                    else f"required {required_action} was not observed"
                ),
            )
        )

    #
    # Actions required after PATCH
    #
    patch_index = next(
        (
            index
            for index, action
            in enumerate(trajectory)
            if action.action_type
            == ActionType.PATCH
        ),
        None,
    )

    if patch_index is None:
        actions_after_patch: set[str] = set()
    else:
        actions_after_patch = {
            action.action_type.value
            for action
            in trajectory[
                patch_index + 1 :
            ]
        }

    for required_action in rules.require_after_patch:
        passed = (
            patch_index is not None
            and required_action
            in actions_after_patch
        )

        if patch_index is None:
            description = (
                f"{required_action} required after PATCH, "
                "but no PATCH was observed"
            )

        elif passed:
            description = (
                f"{required_action} occurred after PATCH"
            )

        else:
            description = (
                f"{required_action} required after PATCH "
                "but was not observed"
            )

        results.append(
            RuleResult(
                passed=passed,
                description=description,
            )
        )

    #
    # Numeric limits
    #
    limits = rules.limits

    if limits.test_attempts is not None:
        passed = (
            summary.test_attempts
            <= limits.test_attempts
        )

        results.append(
            RuleResult(
                passed=passed,
                description=(
                    f"test attempts: "
                    f"{summary.test_attempts} "
                    f"<= {limits.test_attempts}"
                ),
            )
        )

    if limits.failed_attempts is not None:
        passed = (
            summary.failed_attempts
            <= limits.failed_attempts
        )

        results.append(
            RuleResult(
                passed=passed,
                description=(
                    f"failed attempts: "
                    f"{summary.failed_attempts} "
                    f"<= {limits.failed_attempts}"
                ),
            )
        )

    if limits.files_modified is not None:
        passed = (
            summary.files_modified
            <= limits.files_modified
        )

        results.append(
            RuleResult(
                passed=passed,
                description=(
                    f"files modified: "
                    f"{summary.files_modified} "
                    f"<= {limits.files_modified}"
                ),
            )
        )

    if limits.patch_operations is not None:
        passed = (
            summary.patch_operations
            <= limits.patch_operations
        )

        results.append(
            RuleResult(
                passed=passed,
                description=(
                    f"patch operations: "
                    f"{summary.patch_operations} "
                    f"<= {limits.patch_operations}"
                ),
            )
        )

    #
    # Additional verification requirement
    #
    if rules.require_additional_verification:
        passed = (
            summary.additional_verification
        )

        results.append(
            RuleResult(
                passed=passed,
                description=(
                    "additional verification observed"
                    if passed
                    else (
                        "additional verification required "
                        "but not observed"
                    )
                ),
            )
        )

    overall_passed = all(
        result.passed
        for result in results
    )

    return EvaluationResult(
        passed=overall_passed,
        results=results,
    )