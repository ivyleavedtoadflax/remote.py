"""CloudWatch-based auto-shutdown for EC2 instances.

This module provides commands to enable, disable, and check the status of
automatic EC2 instance shutdown based on CPU idle detection. When enabled,
a CloudWatch alarm monitors CPU utilization and stops the instance when
CPU falls below a threshold for a specified duration.

Note: Shutdown stops the instance but preserves it - it can be started again.
"""

from typing import TYPE_CHECKING

import typer
from rich.panel import Panel

if TYPE_CHECKING:
    from mypy_boto3_cloudwatch.type_defs import MetricAlarmTypeDef

from remote.exceptions import InvalidInputError
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
from remote.validation import validate_instance_id

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


def _create_auto_shutdown_alarm(
    instance_id: str,
    instance_name: str,
    threshold: int,
    duration_minutes: int,
) -> None:
    """Create or update a CloudWatch alarm for auto-shutdown.

    Args:
        instance_id: EC2 instance ID (e.g., "i-0123456789abcdef0")
        instance_name: Human-readable instance name for description
        threshold: CPU percentage threshold (e.g., 5 means < 5%)
        duration_minutes: How long CPU must be below threshold
    """
    alarm_name = f"remotepy-autoshutdown-{instance_id}"
    region = get_current_region()
    stop_action = f"arn:aws:automate:{region}:ec2:stop"

    # CloudWatch uses 5-minute minimum periods
    period_seconds = 300
    evaluation_periods = max(1, duration_minutes // 5)

    with handle_aws_errors("CloudWatch", "put_metric_alarm"):
        get_cloudwatch_client().put_metric_alarm(
            # Alarm identification
            AlarmName=alarm_name,
            AlarmDescription=(
                f"Auto-shutdown {instance_name} ({instance_id}) "
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
            AlarmActions=[stop_action],
            # Tags for organization
            Tags=[
                {"Key": "CreatedBy", "Value": "remotepy"},
                {"Key": "InstanceName", "Value": instance_name},
            ],
        )


def delete_auto_shutdown_alarm(instance_id: str) -> bool:
    """Delete the auto-shutdown alarm for an instance.

    This function is used by the terminate command to clean up
    auto-shutdown alarms when an instance is terminated.

    Args:
        instance_id: EC2 instance ID

    Returns:
        True if alarm existed and was deleted, False if no alarm found
    """
    alarm_name = f"remotepy-autoshutdown-{instance_id}"

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
        help="Duration in minutes before shutdown (default: 30)",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Enable auto-shutdown based on CPU idle detection.

    Creates a CloudWatch alarm that STOPS the instance when CPU
    utilization falls below the threshold for the specified duration.

    The instance can be started again afterwards.

    Examples:
        remote instance auto-shutdown enable
        remote instance auto-shutdown enable my-server
        remote instance auto-shutdown enable --threshold 10 --duration 60
        remote instance auto-shutdown enable my-server --threshold 10 --yes
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
    alarm_name = f"remotepy-autoshutdown-{instance_id}"
    existing = _get_existing_alarm(alarm_name)
    action = "update" if existing else "enable"

    # Confirm with user
    if not yes:
        details = f"CPU < {threshold}% for {duration} min will stop instance"
        if not confirm_action(
            f"{action} auto-shutdown for",
            "instance",
            instance_name,
            details=details,
        ):
            print_warning("Cancelled.")
            return

    # Create/update the alarm
    _create_auto_shutdown_alarm(instance_id, instance_name, threshold, duration)

    if existing:
        print_success(f"Updated auto-shutdown for '{instance_name}'")
    else:
        print_success(f"Enabled auto-shutdown for '{instance_name}'")

    print_warning(f"Instance will be stopped when CPU < {threshold}% for {duration} minutes")


@app.command()
@handle_cli_errors
def disable(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    instance_id: str | None = typer.Option(
        None,
        "--instance-id",
        help="Instance ID (use to delete orphaned alarms when instance is terminated)",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Disable auto-shutdown for an instance.

    Removes the CloudWatch alarm monitoring CPU utilization.

    Use --instance-id to clean up orphaned alarms when the instance
    has already been terminated.

    Examples:
        remote instance auto-shutdown disable
        remote instance auto-shutdown disable my-server
        remote instance auto-shutdown disable --yes
        remote instance auto-shutdown disable --instance-id i-0123456789abcdef0 --yes
    """
    # If instance ID provided directly, use it (for orphaned alarm cleanup)
    if instance_id:
        try:
            validate_instance_id(instance_id)
        except InvalidInputError:
            print_error("Invalid instance ID format. Expected format: i-xxxxxxxxxxxxxxxxx")
            raise typer.Exit(1)
        display_name = instance_id
    else:
        instance_name, instance_id = resolve_instance_or_exit(instance_name)
        display_name = instance_name

    # Check if alarm exists
    alarm_name = f"remotepy-autoshutdown-{instance_id}"
    existing = _get_existing_alarm(alarm_name)

    if not existing:
        print_warning(f"Auto-shutdown is not enabled for '{display_name}'")
        return

    # Confirm
    if not yes:
        if not confirm_action("disable auto-shutdown for", "instance", display_name):
            print_warning("Cancelled.")
            return

    # Delete
    delete_auto_shutdown_alarm(instance_id)
    print_success(f"Disabled auto-shutdown for '{display_name}'")


@app.command()
@handle_cli_errors
def status(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """Show auto-shutdown status for an instance.

    Displays the current CloudWatch alarm configuration and state.

    Examples:
        remote instance auto-shutdown status
        remote instance auto-shutdown status my-server
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    alarm_name = f"remotepy-autoshutdown-{instance_id}"
    alarm = _get_existing_alarm(alarm_name)

    if not alarm:
        print_warning(f"Auto-shutdown is not enabled for '{instance_name}'")
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
        title="[bold]Auto-Shutdown Status[/bold]",
        border_style="blue",
        expand=False,
    )
    console.print(panel)
