from dataclasses import dataclass
from datetime import timedelta

from .models import BeaconEvent
from .trajectory import ActionType, build_trajectory


@dataclass
class SessionSummary:
    outcome: str
    duration_seconds: int
    task_duration_seconds: int
    test_attempts: int
    failed_attempts: int
    test_verification: bool
    additional_verification: bool
    behavior_pattern: str


def build_summary(events: list[BeaconEvent]) -> SessionSummary:
    if not events:
        return SessionSummary(
            outcome="UNKNOWN",
            duration_seconds=0,
            task_duration_seconds=0,
            test_attempts=0,
            failed_attempts=0,
            test_verification=False,
            additional_verification=False,
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

    return SessionSummary(
        outcome=outcome,
        duration_seconds=duration_seconds,
        task_duration_seconds=task_duration_seconds,
        test_attempts=test_attempts,
        failed_attempts=failed_attempts,
        test_verification=test_verification,
        additional_verification=additional_verification,
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
