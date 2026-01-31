"""CloudWatch-based auto-termination for EC2 instances.

This module provides commands to enable, disable, and check the status of
automatic EC2 instance termination based on CPU idle detection. When enabled,
a CloudWatch alarm monitors CPU utilization and terminates the instance when
CPU falls below a threshold for a specified duration.

WARNING: Termination is irreversible and deletes instance store volumes.
"""

from typing import TYPE_CHECKING

import typer
from rich.panel import Panel

if TYPE_CHECKING:
    from mypy_boto3_cloudwatch.type_defs import MetricAlarmTypeDef

from remote.instance_resolver import resolve_instance_or_exit
from remote.pricing import get_current_region
from remote.utils import (
    confirm_action,
    console,
    get_cloudwatch_client,
    get_status_style,
    handle_aws_errors,
    handle_cli_errors,
    print_error,
    print_success,
    print_warning,
)

app = typer.Typer()


def _get_existing_alarm(alarm_name: str) -> "MetricAlarmTypeDef | None":
    """Get existing alarm by name, or None if not found.

    Args:
        alarm_name: The CloudWatch alarm name

    Returns:
        Alarm dict if found, None otherwise
    """
    with handle_aws_errors("CloudWatch", "describe_alarms"):
        response = get_cloudwatch_client().describe_alarms(
            AlarmNames=[alarm_name],
            AlarmTypes=["MetricAlarm"],
        )
        alarms = response.get("MetricAlarms", [])
        return alarms[0] if alarms else None


def _create_auto_terminate_alarm(
    instance_id: str,
    instance_name: str,
    threshold: int,
    duration_minutes: int,
) -> None:
    """Create or update a CloudWatch alarm for auto-termination.

    Args:
        instance_id: EC2 instance ID (e.g., "i-0123456789abcdef0")
        instance_name: Human-readable instance name for description
        threshold: CPU percentage threshold (e.g., 5 means < 5%)
        duration_minutes: How long CPU must be below threshold
    """
    alarm_name = f"remotepy-autoterminate-{instance_id}"
    region = get_current_region()
    terminate_action = f"arn:aws:automate:{region}:ec2:terminate"

    # CloudWatch uses 5-minute minimum periods
    period_seconds = 300
    evaluation_periods = max(1, duration_minutes // 5)

    with handle_aws_errors("CloudWatch", "put_metric_alarm"):
        get_cloudwatch_client().put_metric_alarm(
            # Alarm identification
            AlarmName=alarm_name,
            AlarmDescription=(
                f"Auto-terminate {instance_name} ({instance_id}) "
                f"when CPU < {threshold}% for {duration_minutes} minutes"
            ),
            # Metric configuration
            MetricName="CPUUtilization",
            Namespace="AWS/EC2",
            Statistic="Average",
            Dimensions=[
                {
                    "Name": "InstanceId",
                    "Value": instance_id,
                }
            ],
            # Threshold configuration
            Period=period_seconds,
            EvaluationPeriods=evaluation_periods,
            Threshold=float(threshold),
            ComparisonOperator="LessThanThreshold",
            # Behavior when no data
            TreatMissingData="missing",  # Don't trigger on missing data
            # Action to take when alarm triggers
            AlarmActions=[terminate_action],
            # Tags for organization
            Tags=[
                {"Key": "CreatedBy", "Value": "remotepy"},
                {"Key": "InstanceName", "Value": instance_name},
            ],
        )


def _delete_auto_terminate_alarm(instance_id: str) -> bool:
    """Delete the auto-terminate alarm for an instance.

    Args:
        instance_id: EC2 instance ID

    Returns:
        True if alarm existed and was deleted, False if no alarm found
    """
    alarm_name = f"remotepy-autoterminate-{instance_id}"

    # Check if alarm exists first
    existing = _get_existing_alarm(alarm_name)
    if not existing:
        return False

    with handle_aws_errors("CloudWatch", "delete_alarms"):
        get_cloudwatch_client().delete_alarms(AlarmNames=[alarm_name])
    return True


@app.command()
@handle_cli_errors
def enable(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    threshold: int = typer.Option(
        5,
        "--threshold",
        "-t",
        help="CPU threshold percentage (default: 5)",
    ),
    duration: int = typer.Option(
        30,
        "--duration",
        "-d",
        help="Duration in minutes before termination (default: 30)",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Enable auto-termination based on CPU idle detection.

    Creates a CloudWatch alarm that TERMINATES the instance when CPU
    utilization falls below the threshold for the specified duration.

    WARNING: Termination is irreversible and deletes instance store volumes.

    Examples:
        remote instance auto-terminate enable
        remote instance auto-terminate enable my-server
        remote instance auto-terminate enable --threshold 10 --duration 60
        remote instance auto-terminate enable my-server --threshold 10 --yes
    """
    # Validate inputs
    if not 1 <= threshold <= 99:
        print_error("Threshold must be between 1 and 99 percent")
        raise typer.Exit(1)

    if not 5 <= duration <= 1440:
        print_error("Duration must be between 5 and 1440 minutes")
        raise typer.Exit(1)

    # Resolve instance
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Check for existing alarm
    alarm_name = f"remotepy-autoterminate-{instance_id}"
    existing = _get_existing_alarm(alarm_name)
    action = "update" if existing else "enable"

    # Confirm with user
    if not yes:
        details = f"CPU < {threshold}% for {duration} min will TERMINATE instance"
        if not confirm_action(
            f"{action} auto-termination for",
            "instance",
            instance_name,
            details=details,
        ):
            print_warning("Cancelled.")
            return

    # Create/update the alarm
    _create_auto_terminate_alarm(instance_id, instance_name, threshold, duration)

    if existing:
        print_success(f"Updated auto-termination for '{instance_name}'")
    else:
        print_success(f"Enabled auto-termination for '{instance_name}'")

    print_warning(f"Instance will be TERMINATED when CPU < {threshold}% for {duration} minutes")


@app.command()
@handle_cli_errors
def disable(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Disable auto-termination for an instance.

    Removes the CloudWatch alarm monitoring CPU utilization.

    Examples:
        remote instance auto-terminate disable
        remote instance auto-terminate disable my-server
        remote instance auto-terminate disable --yes
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Check if alarm exists
    alarm_name = f"remotepy-autoterminate-{instance_id}"
    existing = _get_existing_alarm(alarm_name)

    if not existing:
        print_warning(f"Auto-termination is not enabled for '{instance_name}'")
        return

    # Confirm
    if not yes:
        if not confirm_action("disable auto-termination for", "instance", instance_name):
            print_warning("Cancelled.")
            return

    # Delete
    _delete_auto_terminate_alarm(instance_id)
    print_success(f"Disabled auto-termination for '{instance_name}'")


@app.command()
@handle_cli_errors
def status(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """Show auto-termination status for an instance.

    Displays the current CloudWatch alarm configuration and state.

    Examples:
        remote instance auto-terminate status
        remote instance auto-terminate status my-server
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    alarm_name = f"remotepy-autoterminate-{instance_id}"
    alarm = _get_existing_alarm(alarm_name)

    if not alarm:
        print_warning(f"Auto-termination is not enabled for '{instance_name}'")
        return

    # Extract details from alarm response
    state = alarm.get("StateValue", "UNKNOWN")  # OK, ALARM, INSUFFICIENT_DATA
    threshold = alarm.get("Threshold", 0)
    period = alarm.get("Period", 300)
    eval_periods = alarm.get("EvaluationPeriods", 1)
    duration_minutes = (period * eval_periods) // 60
    state_reason = alarm.get("StateReason", "")

    # Color based on state
    state_style = get_status_style(state.lower())

    lines = [
        f"[cyan]Instance:[/cyan]      {instance_name}",
        f"[cyan]Instance ID:[/cyan]   {instance_id}",
        f"[cyan]Status:[/cyan]        [{state_style}]{state}[/{state_style}]",
        f"[cyan]CPU Threshold:[/cyan] < {threshold:.0f}%",
        f"[cyan]Duration:[/cyan]      {duration_minutes} minutes",
        "",
        f"[dim]{state_reason}[/dim]",
    ]

    panel = Panel(
        "\n".join(lines),
        title="[bold]Auto-Termination Status[/bold]",
        border_style="blue",
        expand=False,
    )
    console.print(panel)
