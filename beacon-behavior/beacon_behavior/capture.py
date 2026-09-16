import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_BEACON_LOG = Path(
    r"C:\ProgramData\Beacon\Endpoint\logs\runtime.jsonl"
)


@dataclass
class CapturedRun:
    events: list[dict[str, Any]]
    session_id: str
    prompt: str
    start_timestamp: str
    end_timestamp: str


def load_raw_events(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    events: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}"
                ) from exc

    return events


def get_action(event: dict[str, Any]) -> str:
    return event.get("event", {}).get("action", "")


def get_session_id(event: dict[str, Any]) -> str | None:
    return event.get("session", {}).get("id")


def get_prompt_text(event: dict[str, Any]) -> str:
    return event.get("prompt", {}).get("text", "")


def find_latest_prompt_index(
    events: list[dict[str, Any]],
    session_id: str | None = None,
) -> int:
    candidates: list[int] = []

    for index, event in enumerate(events):
        if get_action(event) != "prompt.submitted":
            continue

        if session_id is not None and get_session_id(event) != session_id:
            continue

        candidates.append(index)

    if not candidates:
        if session_id:
            raise ValueError(
                "No prompt.submitted event found "
                f"for session {session_id}."
            )

        raise ValueError("No prompt.submitted event found.")

    return candidates[-1]


def capture_latest_run(
    log_path: str | Path = DEFAULT_BEACON_LOG,
    session_id: str | None = None,
) -> CapturedRun:
    events = load_raw_events(log_path)
    prompt_index = find_latest_prompt_index(events, session_id=session_id)
    prompt_event = events[prompt_index]
    captured_session_id = get_session_id(prompt_event)

    if captured_session_id is None:
        raise ValueError("Latest prompt has no session id.")

    captured_events: list[dict[str, Any]] = []
    end_timestamp: str | None = None

    for event in events[prompt_index:]:
        if get_session_id(event) != captured_session_id:
            continue

        captured_events.append(event)

        if get_action(event) == "token.usage":
            end_timestamp = event.get("timestamp")
            break

    if not captured_events:
        raise ValueError("No events found for latest run.")

    if end_timestamp is None:
        raise ValueError(
            "Latest run does not appear complete: no token.usage event "
            "was found after the prompt."
        )

    return CapturedRun(
        events=captured_events,
        session_id=captured_session_id,
        prompt=get_prompt_text(prompt_event),
        start_timestamp=prompt_event.get("timestamp", ""),
        end_timestamp=end_timestamp,
    )


def write_run(run: CapturedRun, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for event in run.events:
            file.write(json.dumps(event, separators=(",", ":")))
            file.write("\n")

    return output_path
