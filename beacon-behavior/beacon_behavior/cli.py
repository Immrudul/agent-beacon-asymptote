from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .compare import build_comparison
from .parser import load_events
from .summary import build_summary, format_duration
from .trajectory import build_trajectory


app = typer.Typer()

console = Console()


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def get_run_metadata(events):
    if not events:
        return {
            "session": "unknown",
            "harness": "unknown",
            "model": "unknown",
        }

    session = next(
        (
            event.session_id
            for event in events
            if event.session_id
        ),
        "unknown",
    )

    harness = next(
        (
            event.harness_name
            for event in events
            if event.harness_name
        ),
        "unknown",
    )

    model = next(
        (
            event.model
            for event in events
            if event.model
        ),
        "unknown",
    )

    return {
        "session": session,
        "harness": harness,
        "model": model,
    }


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

    metadata = get_run_metadata(events)

    #
    # Session metadata
    #
    console.print()

    console.print("[bold]Beacon Session[/bold]")

    console.print(
        f"Session: {metadata['session']}"
    )

    console.print(
        f"Harness: {metadata['harness']}"
    )

    console.print(
        f"Model:   {metadata['model']}"
    )

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
        "Test verification",
        yes_no(
            summary.test_verification
        ),
    )

    summary_table.add_row(
        "Additional verification",
        yes_no(
            summary.additional_verification
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

    console.print(
        "[bold]Raw Beacon Events[/bold]"
    )

    console.print()

    raw_table = Table()

    raw_table.add_column("Time")
    raw_table.add_column("Seq")
    raw_table.add_column("Action")
    raw_table.add_column("Message")

    for event in events:
        raw_table.add_row(
            event.timestamp.strftime(
                "%H:%M:%S"
            ),
            (
                str(event.sequence)
                if event.sequence is not None
                else ""
            ),
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


@app.command()
def diff(
    path_a: Path,
    path_b: Path,
):
    """
    Compare two Beacon runs.
    """
    events_a = load_events(path_a)
    events_b = load_events(path_b)

    if not events_a:
        console.print(
            f"No Beacon events found in {path_a}."
        )
        raise typer.Exit()

    if not events_b:
        console.print(
            f"No Beacon events found in {path_b}."
        )
        raise typer.Exit()

    comparison = build_comparison(
        events_a,
        events_b,
    )

    metadata_a = get_run_metadata(
        events_a
    )

    metadata_b = get_run_metadata(
        events_b
    )

    #
    # Comparison header
    #
    console.print()

    console.print(
        "[bold]Run Comparison[/bold]"
    )

    console.print()

    console.print(
        f"Run 1: {path_a.name}"
    )

    console.print(
        f"Run 2: {path_b.name}"
    )

    console.print()

    #
    # Summary comparison
    #
    comparison_table = Table()

    comparison_table.add_column(
        "Metric",
        style="bold",
    )

    comparison_table.add_column(
        "Run 1",
    )

    comparison_table.add_column(
        "Run 2",
    )

    comparison_table.add_row(
        "Harness",
        metadata_a["harness"],
        metadata_b["harness"],
    )

    comparison_table.add_row(
        "Model",
        metadata_a["model"],
        metadata_b["model"],
    )

    comparison_table.add_row(
        "Outcome",
        comparison.summary_a.outcome,
        comparison.summary_b.outcome,
    )

    comparison_table.add_row(
        "Task duration",
        format_duration(
            comparison
            .summary_a
            .task_duration_seconds
        ),
        format_duration(
            comparison
            .summary_b
            .task_duration_seconds
        ),
    )

    comparison_table.add_row(
        "Test attempts",
        str(
            comparison
            .summary_a
            .test_attempts
        ),
        str(
            comparison
            .summary_b
            .test_attempts
        ),
    )

    comparison_table.add_row(
        "Failed attempts",
        str(
            comparison
            .summary_a
            .failed_attempts
        ),
        str(
            comparison
            .summary_b
            .failed_attempts
        ),
    )

    comparison_table.add_row(
        "Test verification",
        yes_no(
            comparison
            .summary_a
            .test_verification
        ),
        yes_no(
            comparison
            .summary_b
            .test_verification
        ),
    )

    comparison_table.add_row(
        "Additional verification",
        yes_no(
            comparison
            .summary_a
            .additional_verification
        ),
        yes_no(
            comparison
            .summary_b
            .additional_verification
        ),
    )

    comparison_table.add_row(
        "Behavior pattern",
        comparison
        .summary_a
        .behavior_pattern,
        comparison
        .summary_b
        .behavior_pattern,
    )

    console.print(
        comparison_table
    )

    #
    # Trajectory comparison
    #
    console.print()

    console.print(
        "[bold]Trajectory Comparison[/bold]"
    )

    console.print()

    trajectory_table = Table()

    trajectory_table.add_column(
        "Run",
        style="bold",
    )

    trajectory_table.add_column(
        "Behavior"
    )

    trajectory_table.add_row(
        "Run 1",
        " → ".join(
            comparison.trajectory_a
        ),
    )

    trajectory_table.add_row(
        "Run 2",
        " → ".join(
            comparison.trajectory_b
        ),
    )

    console.print(
        trajectory_table
    )

    #
    # Sequence diff
    #
    console.print()

    difference_count = sum(
        1
        for entry in comparison.trajectory_diff
        if entry.kind != "equal"
    )

    console.print(
        f"[bold]Trajectory Diff[/bold] "
        f"({difference_count} differences)"
    )

    console.print()

    diff_table = Table(
        show_header=False,
    )

    diff_table.add_column(
        "Change",
        width=3,
    )

    diff_table.add_column(
        "Behavior",
    )

    for entry in comparison.trajectory_diff:
        if entry.kind == "equal":
            marker = " "
            style = None

        elif entry.kind == "remove":
            marker = "-"
            style = "red"

        elif entry.kind == "add":
            marker = "+"
            style = "green"

        else:
            marker = "?"
            style = "yellow"

        diff_table.add_row(
            marker,
            entry.action,
            style=style,
        )

    console.print(
        diff_table
    )


if __name__ == "__main__":
    app()
