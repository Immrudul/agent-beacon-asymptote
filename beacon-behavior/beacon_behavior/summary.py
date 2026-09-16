from dataclasses import dataclass
from datetime import timedelta

from .models import BeaconEvent
from .trajectory import (
    ActionType,
    build_trajectory,
    get_modified_file_paths,
    get_patch_operation_count,
)


@dataclass
class SessionSummary:
    outcome: str
    duration_seconds: int
    task_duration_seconds: int
    test_attempts: int
    failed_attempts: int
    environment_errors: int
    test_verification: bool
    additional_verification: bool
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    patch_operations: int
    files_modified: int
    modified_files: list[str]
    tool_calls: int
    commands_executed: int
    trajectory_length: int
    time_to_first_test_seconds: int | None
    time_to_patch_seconds: int | None
    behavior_pattern: str


def build_summary(events: list[BeaconEvent]) -> SessionSummary:
    if not events:
        return SessionSummary(
            outcome="UNKNOWN",
            duration_seconds=0,
            task_duration_seconds=0,
            test_attempts=0,
            failed_attempts=0,
            environment_errors=0,
            test_verification=False,
            additional_verification=False,
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
            patch_operations=0,
            files_modified=0,
            modified_files=[],
            tool_calls=0,
            commands_executed=0,
            trajectory_length=0,
            time_to_first_test_seconds=None,
            time_to_patch_seconds=None,
            behavior_pattern="UNKNOWN",
        )

    # Use detailed trajectory so the summary works from the
    # underlying semantic actions, not the compressed display.
    trajectory = build_trajectory(
        events,
        verbose=True,
    )

    test_attempts = sum(
        1
        for action in trajectory
        if action.action_type
        in {
            ActionType.ENV_ERROR,
            ActionType.TEST_FAIL,
            ActionType.TEST_PASS,
        }
    )

    failed_attempts = sum(
        1
        for action in trajectory
        if action.action_type == ActionType.TEST_FAIL
    )

    patched = any(
        action.action_type == ActionType.PATCH
        for action in trajectory
    )

    diagnosed = any(
        action.action_type == ActionType.READ_CODE
        for action in trajectory
    )

    #
    # Verification semantics
    #
    # A passing test and an additional inspection only count when they occur
    # after the first patch. Pre-patch inspection is part of diagnosis.
    #
    patch_index = next(
        (
            i
            for i, action in enumerate(trajectory)
            if action.action_type == ActionType.PATCH
        ),
        None,
    )

    environment_errors = sum(
        1
        for action in trajectory
        if action.action_type == ActionType.ENV_ERROR
    )

    test_verification = False
    additional_verification = False

    if patch_index is not None:
        actions_after_patch = trajectory[patch_index + 1 :]

        test_verification = any(
            action.action_type == ActionType.TEST_PASS
            for action in actions_after_patch
        )

        additional_verification = any(
            action.action_type == ActionType.VERIFY
            for action in actions_after_patch
        )

    #
    # Outcome
    #

    if test_verification:
        outcome = "PASS"
    elif test_attempts > 0:
        outcome = "FAIL"
    else:
        outcome = "UNKNOWN"

    #
    # High-level behavior pattern
    #

    if (
        diagnosed
        and patched
        and test_verification
        and additional_verification
    ):
        behavior_pattern = "DEBUG_FIX_VERIFY"

    elif diagnosed and patched and test_verification:
        behavior_pattern = "DEBUG_FIX_TEST"

    elif patched and test_verification and additional_verification:
        behavior_pattern = "FIX_VERIFY"

    elif patched and test_verification:
        behavior_pattern = "FIX_TEST"

    elif diagnosed and patched:
        behavior_pattern = "DEBUG_FIX_INCOMPLETE"

    elif diagnosed:
        behavior_pattern = "DIAGNOSE_ONLY"

    else:
        behavior_pattern = "UNKNOWN"

    #
    # Session duration
    #

    start = min(
        event.timestamp
        for event in events
    )

    end = max(
        event.timestamp
        for event in events
    )

    duration_seconds = int(
        (end - start).total_seconds()
    )

    prompt_events = [
        event
        for event in events
        if event.action == "prompt.submitted"
    ]

    meaningful_actions = [
        action
        for action in trajectory
        if action.action_type != ActionType.TOKENS
    ]

    if prompt_events and meaningful_actions:
        task_start = min(
            event.timestamp
            for event in prompt_events
        )

        task_end = max(
            action.event.timestamp
            for action in meaningful_actions
        )

        task_duration_seconds = int(
            (task_end - task_start).total_seconds()
        )
    else:
        task_duration_seconds = duration_seconds

    #
    # Token usage
    #
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0

    for event in events:
        if event.action != "token.usage":
            continue

        gen_ai = event.gen_ai or {}
        usage = gen_ai.get("usage", {})

        if not isinstance(usage, dict):
            continue

        input = usage.get("input_tokens", 0)
        input_tokens += input if isinstance(input, int) else 0

        cache_read = usage.get("cache_read", {})
        if isinstance(cache_read, dict):
            cached_input = cache_read.get("input_tokens", 0)
            cached_input_tokens += (
                cached_input if isinstance(cached_input, int) else 0
            )

        output = usage.get("output_tokens", 0)
        output_tokens += output if isinstance(output, int) else 0

        reasoning = usage.get("reasoning", {})
        if isinstance(reasoning, dict):
            reasoning_output = reasoning.get("output_tokens", 0)
            reasoning_tokens += (
                reasoning_output
                if isinstance(reasoning_output, int)
                else 0
            )

    #
    # File modification metrics
    #
    modified_files = sorted(get_modified_file_paths(events))
    patch_operations = get_patch_operation_count(events)
    files_modified = len(modified_files)

    #
    # Behavioral efficiency metrics
    #
    tool_calls = sum(
        1
        for event in events
        if event.action == "tool.invoked"
    )

    commands_executed = sum(
        1
        for event in events
        if event.action == "command.executed"
    )

    semantic_trajectory = build_trajectory(
        events,
        verbose=False,
    )

    trajectory_length = sum(
        1
        for action in semantic_trajectory
        if action.action_type
        not in {
            ActionType.PROMPT,
            ActionType.TOKENS,
        }
    )

    prompt_time = next(
        (
            event.timestamp
            for event in events
            if event.action == "prompt.submitted"
        ),
        None,
    )

    first_test_time = next(
        (
            action.event.timestamp
            for action in trajectory
            if action.action_type
            in {
                ActionType.ENV_ERROR,
                ActionType.TEST_FAIL,
                ActionType.TEST_PASS,
            }
        ),
        None,
    )

    patch_time = next(
        (
            action.event.timestamp
            for action in trajectory
            if action.action_type == ActionType.PATCH
        ),
        None,
    )

    time_to_first_test_seconds = (
        int((first_test_time - prompt_time).total_seconds())
        if prompt_time and first_test_time
        else None
    )

    time_to_patch_seconds = (
        int((patch_time - prompt_time).total_seconds())
        if prompt_time and patch_time
        else None
    )

    return SessionSummary(
        outcome=outcome,
        duration_seconds=duration_seconds,
        task_duration_seconds=task_duration_seconds,
        test_attempts=test_attempts,
        failed_attempts=failed_attempts,
        environment_errors=environment_errors,
        test_verification=test_verification,
        additional_verification=additional_verification,
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        patch_operations=patch_operations,
        files_modified=files_modified,
        modified_files=modified_files,
        tool_calls=tool_calls,
        commands_executed=commands_executed,
        trajectory_length=trajectory_length,
        time_to_first_test_seconds=time_to_first_test_seconds,
        time_to_patch_seconds=time_to_patch_seconds,
        behavior_pattern=behavior_pattern,
    )


def format_duration(seconds: int) -> str:
    delta = timedelta(seconds=seconds)

    total_seconds = int(
        delta.total_seconds()
    )

    minutes, seconds = divmod(
        total_seconds,
        60,
    )

    if minutes:
        return f"{minutes}m {seconds}s"

    return f"{seconds}s"


def format_optional_duration(seconds: int | None) -> str:
    if seconds is None:
        return "n/a"

    return format_duration(seconds)
