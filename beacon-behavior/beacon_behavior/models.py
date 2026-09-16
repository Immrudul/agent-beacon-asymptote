from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BeaconEvent(BaseModel):
    timestamp: datetime
    sequence: int | None = None

    event: dict[str, Any]
    harness: dict[str, Any] = Field(default_factory=dict)
    session: dict[str, Any] = Field(default_factory=dict)

    model: str | None = None
    message: str | None = None

    tool: dict[str, Any] | None = None
    command: dict[str, Any] | None = None
    prompt: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    gen_ai: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None

    @property
    def action(self) -> str:
        return self.event.get("action", "unknown")

    @property
    def session_id(self) -> str | None:
        return self.session.get("id")

    @property
    def harness_name(self) -> str | None:
        return self.harness.get("name")