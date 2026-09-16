from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .parser import load_events
from .summary import build_summary, format_duration
from .trajectory import build_trajectory


app = typer.Typer()
console = Console()


@app.command()
def show(
    path: Path,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed behavioral actions instead of compressed phases.",
    ),
):
    """
    Show a Beacon session, summary, and behavioral trajectory.
    """

    events = load_events(path)

    if not events:
        console.print("No Beacon events found.")
        raise typer.Exit()

    first = events[0]

    #
    # Session metadata
    #

    console.print()
    console.print("[bold]Beacon Session[/bold]")
    console.print(f"Session: {first.session_id}")
    console.print(f"Harness: {first.harness_name}")
    console.print(f"Model:   {first.model or 'unknown'}")
    console.print()

    #
    # Session summary
    #

    summary = build_summary(events)

    summary_table = Table(
        title="Session Summary",
        show_header=False,
    )

    summary_table.add_column(
        "Metric",
        style="bold",
    )

    summary_table.add_column(
        "Value",
    )

    summary_table.add_row(
        "Outcome",
        summary.outcome,
    )

    summary_table.add_row(
        "Session duration",
        format_duration(
            summary.duration_seconds
        ),
    )

    summary_table.add_row(
        "Task duration",
        format_duration(
            summary.task_duration_seconds
        ),
    )

    summary_table.add_row(
        "Test attempts",
        str(summary.test_attempts),
    )

    summary_table.add_row(
        "Failed attempts",
        str(summary.failed_attempts),
    )

    summary_table.add_row(
        "Successful verification",
        (
            "yes"
            if summary.successful_verification
            else "no"
        ),
    )

    summary_table.add_row(
        "Behavior pattern",
        summary.behavior_pattern,
    )

    console.print(summary_table)

    #
    # Raw Beacon telemetry
    #

    console.print()
    console.print("[bold]Raw Beacon Events[/bold]")
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

    #
    # Behavioral trajectory
    #

    trajectory = build_trajectory(
        events,
        verbose=verbose,
    )

    console.print()

    if verbose:
        console.print(
            "[bold]Detailed Behavioral Trajectory[/bold]"
        )
    else:
        console.print(
            "[bold]Behavioral Trajectory[/bold]"
        )

    console.print()

    trajectory_table = Table()

    trajectory_table.add_column("Time")
    trajectory_table.add_column("Type")
    trajectory_table.add_column("Action")

    for action in trajectory:
        trajectory_table.add_row(
            action.event.timestamp.strftime(
                "%H:%M:%S"
            ),
            action.action_type.value,
            action.label,
        )

    console.print(trajectory_table)


if __name__ == "__main__":
    app()
