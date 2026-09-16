import json
from pathlib import Path

from .models import BeaconEvent


def load_events(path: str | Path) -> list[BeaconEvent]:
    path = Path(path)

    events: list[BeaconEvent] = []

    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(line)
                events.append(BeaconEvent.model_validate(data))
            except Exception as exc:
                raise ValueError(
                    f"Failed to parse line {line_number} of {path}"
                ) from exc

    # Beacon events can arrive asynchronously, so don't trust JSONL append order.
    events.sort(
        key=lambda event: (
            event.timestamp,
            event.sequence if event.sequence is not None else 0,
        )
    )

    return events