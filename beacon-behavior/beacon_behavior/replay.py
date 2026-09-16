from dataclasses import dataclass

from .models import BeaconEvent
from .trajectory import (
    ActionType,
    TrajectoryAction,
    build_trajectory,
    get_patch_file_paths,
    get_patch_text,
)


@dataclass
class ReplayStep:
    index: int
    total: int
    actions: list[TrajectoryAction]
    elapsed_seconds: int

    @property
    def event(self) -> BeaconEvent:
        return self.actions[0].event


def build_replay_steps(events: list[BeaconEvent]) -> list[ReplayStep]:
    """Build detailed, user-advanceable steps for a captured run."""
    trajectory = build_trajectory(events, verbose=True)
    meaningful = [
        action
        for action in trajectory
        if action.action_type not in {ActionType.PROMPT, ActionType.TOKENS}
    ]

    if not meaningful:
        return []

    prompt_time = next(
        (
            event.timestamp
            for event in events
            if event.action == "prompt.submitted"
        ),
        meaningful[0].event.timestamp,
    )

    grouped_actions: list[list[TrajectoryAction]] = []

    for action in meaningful:
        if grouped_actions and grouped_actions[-1][0].event is action.event:
            grouped_actions[-1].append(action)
        else:
            grouped_actions.append([action])

    steps: list[ReplayStep] = []
    patch_seen = False

    for index, actions in enumerate(grouped_actions, start=1):
        event = actions[0].event
        semantics: list[TrajectoryAction] = []

        for action in actions:
            action_type = action.action_type

            if action_type == ActionType.VERIFY and not patch_seen:
                action_type = ActionType.DIAGNOSE

            if not any(
                existing.action_type == action_type
                for existing in semantics
            ):
                semantics.append(
                    TrajectoryAction(
                        action_type,
                        action.label,
                        action.event,
                    )
                )

        if any(
            action.action_type == ActionType.PATCH
            for action in actions
        ):
            patch_seen = True

        elapsed = int((event.timestamp - prompt_time).total_seconds())
        steps.append(
            ReplayStep(
                index=index,
                total=len(grouped_actions),
                actions=semantics,
                elapsed_seconds=elapsed,
            )
        )

    return steps


def get_command_text(event: BeaconEvent) -> str | None:
    command = event.command or {}

    for key in ("command", "text", "value"):
        value = command.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def get_command_output(event: BeaconEvent) -> str | None:
    command = event.command or {}

    for key in ("output", "stdout", "result"):
        value = command.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    raw = event.raw or {}
    output = raw.get("attributes", {}).get("output", "")

    if isinstance(output, str) and output.strip():
        return output.strip()

    return None


def describe_step(step: ReplayStep) -> dict[str, str]:
    """Return display-ready details for a replay step."""
    event = step.event
    is_patch = any(
        action.action_type == ActionType.PATCH
        for action in step.actions
    )
    data = {
        "type": "PATCH" if is_patch else "COMMAND",
        "semantics": ", ".join(
            action.action_type.value
            for action in step.actions
        ),
        "elapsed": f"{step.elapsed_seconds}s",
    }

    command = get_command_text(event)
    if command:
        data["command"] = command

    output = get_command_output(event)
    if output:
        data["output"] = output

    if is_patch:
        patch = get_patch_text(event)
        if patch:
            data["patch"] = patch

        files = get_patch_file_paths(event)
        if files:
            data["files"] = ", ".join(sorted(files))

    return data
