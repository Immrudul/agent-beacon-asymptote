from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import BeaconEvent
from .summary import SessionSummary, build_summary
from .trajectory import ActionType, build_trajectory


@dataclass
class TrajectoryDiffEntry:
    kind: str
    action: str


@dataclass
class RunComparison:
    summary_a: SessionSummary
    summary_b: SessionSummary
    trajectory_a: list[str]
    trajectory_b: list[str]
    trajectory_diff: list[TrajectoryDiffEntry]


def trajectory_signature(
    events: list[BeaconEvent],
) -> list[str]:
    """
    Build a compact behavioral signature for a run.
    """
    trajectory = build_trajectory(events)

    ignored_types = {
        ActionType.PROMPT,
        ActionType.TOKENS,
    }

    return [
        action.action_type.value
        for action in trajectory
        if action.action_type not in ignored_types
    ]


def build_trajectory_diff(
    trajectory_a: list[str],
    trajectory_b: list[str],
) -> list[TrajectoryDiffEntry]:
    """
    Produce a sequence-aware behavioral diff.

    kind:
        equal   -> behavior appears in both runs
        remove  -> appears only in run 1
        add     -> appears only in run 2
    """
    matcher = SequenceMatcher(
        a=trajectory_a,
        b=trajectory_b,
        autojunk=False,
    )

    diff: list[TrajectoryDiffEntry] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for action in trajectory_a[i1:i2]:
                diff.append(
                    TrajectoryDiffEntry(
                        kind="equal",
                        action=action,
                    )
                )

        elif tag == "delete":
            for action in trajectory_a[i1:i2]:
                diff.append(
                    TrajectoryDiffEntry(
                        kind="remove",
                        action=action,
                    )
                )

        elif tag == "insert":
            for action in trajectory_b[j1:j2]:
                diff.append(
                    TrajectoryDiffEntry(
                        kind="add",
                        action=action,
                    )
                )

        elif tag == "replace":
            for action in trajectory_a[i1:i2]:
                diff.append(
                    TrajectoryDiffEntry(
                        kind="remove",
                        action=action,
                    )
                )

            for action in trajectory_b[j1:j2]:
                diff.append(
                    TrajectoryDiffEntry(
                        kind="add",
                        action=action,
                    )
                )

    return diff


def build_comparison(
    events_a: list[BeaconEvent],
    events_b: list[BeaconEvent],
) -> RunComparison:
    trajectory_a = trajectory_signature(events_a)
    trajectory_b = trajectory_signature(events_b)

    return RunComparison(
        summary_a=build_summary(events_a),
        summary_b=build_summary(events_b),
        trajectory_a=trajectory_a,
        trajectory_b=trajectory_b,
        trajectory_diff=build_trajectory_diff(
            trajectory_a,
            trajectory_b,
        ),
    )