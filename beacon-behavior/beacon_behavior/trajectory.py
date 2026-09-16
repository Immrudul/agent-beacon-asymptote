from enum import Enum

from .models import BeaconEvent


class ActionType(str, Enum):
    PROMPT = "PROMPT"
    INSPECT_REPO = "INSPECT_REPO"
    READ_CODE = "READ_CODE"
    TEST_FAIL = "TEST_FAIL"
    TEST_PASS = "TEST_PASS"
    PATCH = "PATCH"
    VERIFY = "VERIFY"
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


def get_command_output(event: BeaconEvent) -> str:
    raw = event.raw or {}
    attributes = raw.get("attributes", {})
    return attributes.get("output", "")


def classify_event(event: BeaconEvent) -> list[TrajectoryAction]:
    action = event.action
    results: list[TrajectoryAction] = []

    if action == "prompt.submitted":
        prompt_text = (event.prompt or {}).get("text", "")

        results.append(
            TrajectoryAction(
                ActionType.PROMPT,
                prompt_text,
                event,
            )
        )

        return results

    if action == "token.usage":
        results.append(
            TrajectoryAction(
                ActionType.TOKENS,
                "Token usage",
                event,
            )
        )

        return results

    if action == "tool.invoked":
        tool_name = (event.tool or {}).get("name", "unknown")

        # Codex emits generic exec wrapper events alongside
        # the actual command.executed event, so skip those.
        if tool_name == "exec":
            return results

        if tool_name == "apply_patch":
            results.append(
                TrajectoryAction(
                    ActionType.PATCH,
                    "Modified code",
                    event,
                )
            )

            return results

        results.append(
            TrajectoryAction(
                ActionType.OTHER,
                f"Tool: {tool_name}",
                event,
            )
        )

        return results

    if action == "approval.requested":
        # Keep approvals in raw telemetry,
        # but exclude them from the behavioral story.
        return results

    if action == "session.started":
        return results

    if action == "command.executed":
        command = (event.command or {}).get("command", "")
        lower = command.lower()

        output = get_command_output(event)
        output_lower = output.lower()

        #
        # Repository exploration
        #
        if "get-childitem" in lower:
            results.append(
                TrajectoryAction(
                    ActionType.INSPECT_REPO,
                    "Inspected repository",
                    event,
                )
            )

        if "rg " in lower or lower.startswith("rg"):
            results.append(
                TrajectoryAction(
                    ActionType.INSPECT_REPO,
                    "Inspected repository",
                    event,
                )
            )

        if lower.startswith("ls ") or lower == "ls":
            results.append(
                TrajectoryAction(
                    ActionType.INSPECT_REPO,
                    "Inspected repository",
                    event,
                )
            )

        #
        # Reading tests / implementation
        #
        if "get-content" in lower and "test_solver.py" in lower:
            results.append(
                TrajectoryAction(
                    ActionType.READ_CODE,
                    "Read tests",
                    event,
                )
            )

        if "get-content" in lower and "solve.py" in lower:
            results.append(
                TrajectoryAction(
                    ActionType.READ_CODE,
                    "Read implementation",
                    event,
                )
            )

        #
        # Test execution
        #
        if "pytest" in lower:
            if "passed" in output_lower:
                results.append(
                    TrajectoryAction(
                        ActionType.TEST_PASS,
                        "Tests passed",
                        event,
                    )
                )

            elif (
                "failed" in output_lower
                or "error" in output_lower
                or "no module named pytest" in output_lower
            ):
                results.append(
                    TrajectoryAction(
                        ActionType.TEST_FAIL,
                        "Tests failed",
                        event,
                    )
                )

            else:
                results.append(
                    TrajectoryAction(
                        ActionType.TEST_FAIL,
                        "Test run unsuccessful",
                        event,
                    )
                )

        #
        # Verification
        #
        if "git diff" in lower:
            results.append(
                TrajectoryAction(
                    ActionType.VERIFY,
                    "Verified code changes",
                    event,
                )
            )

        if "select-string" in lower:
            results.append(
                TrajectoryAction(
                    ActionType.VERIFY,
                    "Inspected patched code",
                    event,
                )
            )

        #
        # Fallback
        #
        if not results:
            results.append(
                TrajectoryAction(
                    ActionType.OTHER,
                    command,
                    event,
                )
            )

        return results

    return results


def deduplicate_consecutive(
    actions: list[TrajectoryAction],
) -> list[TrajectoryAction]:
    if not actions:
        return []

    compressed: list[TrajectoryAction] = [actions[0]]

    for action in actions[1:]:
        previous = compressed[-1]

        if (
            action.action_type == previous.action_type
            and action.label == previous.label
        ):
            continue

        compressed.append(action)

    return compressed


def build_trajectory(
    events: list[BeaconEvent],
) -> list[TrajectoryAction]:
    trajectory: list[TrajectoryAction] = []

    for event in events:
        actions = classify_event(event)
        trajectory.extend(actions)

    return deduplicate_consecutive(trajectory)