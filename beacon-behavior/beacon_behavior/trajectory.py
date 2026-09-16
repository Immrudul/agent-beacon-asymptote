from enum import Enum

from .models import BeaconEvent


class ActionType(str, Enum):
    PROMPT = "PROMPT"
    INSPECT = "INSPECT"
    TEST = "TEST"
    PATCH = "PATCH"
    APPROVAL = "APPROVAL"
    TOOL = "TOOL"
    TOKENS = "TOKENS"
    OTHER = "OTHER"


class TrajectoryAction:
    def __init__(
        self,
        action_type: ActionType,
        label: str,
        event: BeaconEvent,
    ):
        self.action_type = action_type
        self.label = label
        self.event = event


def classify_event(event: BeaconEvent) -> TrajectoryAction:
    action = event.action

    if action == "prompt.submitted":
        prompt_text = (event.prompt or {}).get("text", "")
        return TrajectoryAction(
            ActionType.PROMPT,
            prompt_text,
            event,
        )

    if action == "approval.requested":
        tool_name = (event.tool or {}).get("name", "unknown")
        return TrajectoryAction(
            ActionType.APPROVAL,
            f"Approved {tool_name}",
            event,
        )

    if action == "token.usage":
        return TrajectoryAction(
            ActionType.TOKENS,
            "Token usage",
            event,
        )

    if action == "tool.invoked":
        tool_name = (event.tool or {}).get("name", "unknown")

        if tool_name == "apply_patch":
            return TrajectoryAction(
                ActionType.PATCH,
                "Modified code",
                event,
            )

        return TrajectoryAction(
            ActionType.TOOL,
            f"Tool: {tool_name}",
            event,
        )

    if action == "command.executed":
        command = (event.command or {}).get("command", "")
        lower = command.lower()

        if "pytest" in lower:
            return TrajectoryAction(
                ActionType.TEST,
                command,
                event,
            )

        if any(
            keyword in lower
            for keyword in [
                "get-content",
                "get-childitem",
                "select-string",
                "rg ",
                "cat ",
                "ls ",
            ]
        ):
            return TrajectoryAction(
                ActionType.INSPECT,
                command,
                event,
            )

        return TrajectoryAction(
            ActionType.TOOL,
            command,
            event,
        )

    return TrajectoryAction(
        ActionType.OTHER,
        event.message or event.action,
        event,
    )


def build_trajectory(events: list[BeaconEvent]) -> list[TrajectoryAction]:
    return [classify_event(event) for event in events]