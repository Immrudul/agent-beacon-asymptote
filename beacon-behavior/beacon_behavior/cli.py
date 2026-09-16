from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .parser import load_events
from .trajectory import build_trajectory


app = typer.Typer()
console = Console()


@app.command()
def show(path: Path):
    """Show the ordered events and behavioral trajectory from a Beacon JSONL trace."""

    events = load_events(path)

    if not events:
        console.print("No Beacon events found.")
        raise typer.Exit()

    first = events[0]

    console.print()
    console.print("[bold]Beacon Session[/bold]")
    console.print(f"Session: {first.session_id}")
    console.print(f"Harness: {first.harness_name}")
    console.print(f"Model:   {first.model or 'unknown'}")
    console.print()

    raw_table = Table()

    raw_table.add_column("Time")
    raw_table.add_column("Seq")
    raw_table.add_column("Action")
    raw_table.add_column("Message")

    for event in events:
        raw_table.add_row(
            event.timestamp.strftime("%H:%M:%S"),
            str(event.sequence or ""),
            event.action,
            event.message or "",
        )

    console.print(raw_table)

    trajectory = build_trajectory(events)

    console.print()
    console.print("[bold]Behavioral Trajectory[/bold]")
    console.print()

    trajectory_table = Table()

    trajectory_table.add_column("Time")
    trajectory_table.add_column("Type")
    trajectory_table.add_column("Action")

    for action in trajectory:
        trajectory_table.add_row(
            action.event.timestamp.strftime("%H:%M:%S"),
            action.action_type.value,
            action.label,
        )

    console.print(trajectory_table)


if __name__ == "__main__":
    app()