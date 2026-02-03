"""CLI commands for EventBridge Scheduler wake/sleep schedules.

This module provides CLI commands for managing scheduled start/stop of EC2 instances.
"""

import typer

from .config import config_manager
from .instance_resolver import resolve_instance_or_exit
from .scheduler import (
    create_schedule,
    delete_all_schedules_for_instance,
    delete_schedule,
    delete_scheduler_role,
    get_schedule,
    get_schedules_for_instance,
    list_schedules,
)
from .utils import (
    confirm_action,
    handle_cli_errors,
    print_error,
    print_info,
    print_success,
    print_warning,
)
from .validation import (
    build_schedule_at_expression,
    build_schedule_cron_expression,
    parse_schedule_date,
    parse_schedule_days,
    parse_schedule_time,
)

app = typer.Typer(
    name="schedule",
    help="Manage scheduled wake/sleep for EC2 instances",
    no_args_is_help=True,
)

# Default days (weekdays)
DEFAULT_DAYS = "mon-fri"


def _get_timezone(timezone_arg: str | None) -> str:
    """Get timezone from argument, config, or auto-detect from system.

    Priority:
    1. Explicit --timezone argument
    2. scheduler_timezone in config
    3. Auto-detect from system (via tzlocal)
    4. Fall back to UTC
    """
    if timezone_arg:
        return timezone_arg

    config_tz = config_manager.get_value("scheduler_timezone")
    if config_tz:
        return config_tz

    # Auto-detect from system
    try:
        from tzlocal import get_localzone_name

        return get_localzone_name()
    except Exception:
        return "UTC"


def _format_cron_for_display(cron_expr: str) -> str:
    """Format a cron expression for human-readable display."""
    # Extract time and days from cron expression
    # Format: cron(minute hour ? * days *)
    try:
        # Remove cron() wrapper
        inner = cron_expr.replace("cron(", "").replace(")", "")
        parts = inner.split()
        if len(parts) >= 5:
            minute, hour = parts[0], parts[1]
            days = parts[4]
            return f"{hour.zfill(2)}:{minute.zfill(2)} on {days}"
    except (ValueError, IndexError):
        pass
    return cron_expr


@app.command()
@handle_cli_errors
def wake(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    time: str = typer.Option(..., "--time", "-t", help="Wake time (e.g., 09:00)"),
    at: str | None = typer.Option(
        None, "--at", "-a", help="One-time date (e.g., tomorrow, tuesday, 2026-02-15)"
    ),
    days: str | None = typer.Option(
        None, "--days", "-d", help="Recurring days (e.g., mon-fri, mon,wed,fri)"
    ),
    timezone: str | None = typer.Option(
        None, "--timezone", "-z", help="IANA timezone (e.g., America/New_York)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Create a wake schedule to start an instance at a specific time.

    Use --at for one-time schedules (e.g., --at tomorrow, --at tuesday).
    Use --days for recurring schedules (e.g., --days mon-fri). Defaults to mon-fri if neither specified.
    """
    instance_name_resolved, instance_id = resolve_instance_or_exit(instance_name)

    # Check for mutually exclusive options
    if at and days:
        print_error("Cannot use both --at and --days. Use --at for one-time, --days for recurring.")
        raise typer.Exit(1)

    # Validate time
    try:
        hour, minute = parse_schedule_time(time)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    tz = _get_timezone(timezone)

    if at:
        # One-time schedule
        try:
            target_date = parse_schedule_date(at)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        schedule_expr = build_schedule_at_expression(target_date, hour, minute)

        if not yes:
            print_info(
                f"Will schedule {instance_name_resolved} ({instance_id}) "
                f"to wake once at {hour:02d}:{minute:02d} on {target_date.isoformat()}"
            )
            if not confirm_action(
                "Create one-time wake schedule", "instance", instance_name_resolved
            ):
                print_warning("Cancelled")
                return

        create_schedule(
            instance_id=instance_id,
            action="wake",
            schedule_expression=schedule_expr,
        )

        print_success(
            f"Created one-time wake schedule for {instance_name_resolved}: "
            f"{hour:02d}:{minute:02d} on {target_date.isoformat()}"
        )
    else:
        # Recurring schedule (default to mon-fri)
        days_str = days or DEFAULT_DAYS
        try:
            day_list = parse_schedule_days(days_str)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        schedule_expr = build_schedule_cron_expression(hour, minute, day_list)

        if not yes:
            print_info(
                f"Will schedule {instance_name_resolved} ({instance_id}) "
                f"to wake at {hour:02d}:{minute:02d} on {','.join(day_list)} ({tz})"
            )
            if not confirm_action("Create wake schedule", "instance", instance_name_resolved):
                print_warning("Cancelled")
                return

        create_schedule(
            instance_id=instance_id,
            action="wake",
            schedule_expression=schedule_expr,
            timezone=tz,
        )

        print_success(
            f"Created wake schedule for {instance_name_resolved}: "
            f"{hour:02d}:{minute:02d} on {','.join(day_list)} ({tz})"
        )


@app.command()
@handle_cli_errors
def sleep(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    time: str = typer.Option(..., "--time", "-t", help="Sleep time (e.g., 18:00)"),
    at: str | None = typer.Option(
        None, "--at", "-a", help="One-time date (e.g., tomorrow, tuesday, 2026-02-15)"
    ),
    days: str | None = typer.Option(
        None, "--days", "-d", help="Recurring days (e.g., mon-fri, mon,wed,fri)"
    ),
    timezone: str | None = typer.Option(
        None, "--timezone", "-z", help="IANA timezone (e.g., America/New_York)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Create a sleep schedule to stop an instance at a specific time.

    Use --at for one-time schedules (e.g., --at tomorrow, --at tuesday).
    Use --days for recurring schedules (e.g., --days mon-fri). Defaults to mon-fri if neither specified.
    """
    instance_name_resolved, instance_id = resolve_instance_or_exit(instance_name)

    # Check for mutually exclusive options
    if at and days:
        print_error("Cannot use both --at and --days. Use --at for one-time, --days for recurring.")
        raise typer.Exit(1)

    # Validate time
    try:
        hour, minute = parse_schedule_time(time)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    tz = _get_timezone(timezone)

    if at:
        # One-time schedule
        try:
            target_date = parse_schedule_date(at)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        schedule_expr = build_schedule_at_expression(target_date, hour, minute)

        if not yes:
            print_info(
                f"Will schedule {instance_name_resolved} ({instance_id}) "
                f"to sleep once at {hour:02d}:{minute:02d} on {target_date.isoformat()}"
            )
            if not confirm_action(
                "Create one-time sleep schedule", "instance", instance_name_resolved
            ):
                print_warning("Cancelled")
                return

        create_schedule(
            instance_id=instance_id,
            action="sleep",
            schedule_expression=schedule_expr,
        )

        print_success(
            f"Created one-time sleep schedule for {instance_name_resolved}: "
            f"{hour:02d}:{minute:02d} on {target_date.isoformat()}"
        )
    else:
        # Recurring schedule (default to mon-fri)
        days_str = days or DEFAULT_DAYS
        try:
            day_list = parse_schedule_days(days_str)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

        schedule_expr = build_schedule_cron_expression(hour, minute, day_list)

        if not yes:
            print_info(
                f"Will schedule {instance_name_resolved} ({instance_id}) "
                f"to sleep at {hour:02d}:{minute:02d} on {','.join(day_list)} ({tz})"
            )
            if not confirm_action("Create sleep schedule", "instance", instance_name_resolved):
                print_warning("Cancelled")
                return

        create_schedule(
            instance_id=instance_id,
            action="sleep",
            schedule_expression=schedule_expr,
            timezone=tz,
        )

        print_success(
            f"Created sleep schedule for {instance_name_resolved}: "
            f"{hour:02d}:{minute:02d} on {','.join(day_list)} ({tz})"
        )


@app.command()
@handle_cli_errors
def status(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """Show schedule status for an instance."""
    instance_name_resolved, instance_id = resolve_instance_or_exit(instance_name)

    schedules = get_schedules_for_instance(instance_id)

    print_info(f"Schedule status for {instance_name_resolved} ({instance_id})")

    has_schedules = False

    if schedules["wake"]:
        has_schedules = True
        wake_sched = schedules["wake"]
        cron_display = _format_cron_for_display(wake_sched.get("ScheduleExpression", ""))
        tz = wake_sched.get("ScheduleExpressionTimezone", "UTC")
        state = wake_sched.get("State", "UNKNOWN")
        typer.echo(f"  Wake:  {cron_display} ({tz}) [{state}]")

    if schedules["sleep"]:
        has_schedules = True
        sleep_sched = schedules["sleep"]
        cron_display = _format_cron_for_display(sleep_sched.get("ScheduleExpression", ""))
        tz = sleep_sched.get("ScheduleExpressionTimezone", "UTC")
        state = sleep_sched.get("State", "UNKNOWN")
        typer.echo(f"  Sleep: {cron_display} ({tz}) [{state}]")

    if not has_schedules:
        print_warning("No schedules configured for this instance")


@app.command()
@handle_cli_errors
def clear(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    wake_only: bool = typer.Option(False, "--wake", help="Clear only wake schedule"),
    sleep_only: bool = typer.Option(False, "--sleep", help="Clear only sleep schedule"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Clear schedules for an instance."""
    instance_name_resolved, instance_id = resolve_instance_or_exit(instance_name)

    # Determine what to clear
    if wake_only and sleep_only:
        print_error("Cannot specify both --wake and --sleep. Use neither to clear both.")
        raise typer.Exit(1)

    if wake_only:
        existing = get_schedule(instance_id, "wake")
        if not existing:
            print_warning(f"No wake schedule configured for {instance_name_resolved}")
            return

        if not yes:
            if not confirm_action("Clear wake schedule", "instance", instance_name_resolved):
                print_warning("Cancelled")
                return

        deleted = delete_schedule(instance_id, "wake")
        if deleted:
            print_success(f"Cleared wake schedule for {instance_name_resolved}")
        return

    if sleep_only:
        existing = get_schedule(instance_id, "sleep")
        if not existing:
            print_warning(f"No sleep schedule configured for {instance_name_resolved}")
            return

        if not yes:
            if not confirm_action("Clear sleep schedule", "instance", instance_name_resolved):
                print_warning("Cancelled")
                return

        deleted = delete_schedule(instance_id, "sleep")
        if deleted:
            print_success(f"Cleared sleep schedule for {instance_name_resolved}")
        return

    # Clear both
    schedules = get_schedules_for_instance(instance_id)
    if not schedules["wake"] and not schedules["sleep"]:
        print_warning(f"No schedules configured for {instance_name_resolved}")
        return

    if not yes:
        if not confirm_action("Clear all schedules", "instance", instance_name_resolved):
            print_warning("Cancelled")
            return

    results = delete_all_schedules_for_instance(instance_id)

    cleared = []
    if results["wake"]:
        cleared.append("wake")
    if results["sleep"]:
        cleared.append("sleep")

    if cleared:
        print_success(f"Cleared {', '.join(cleared)} schedule(s) for {instance_name_resolved}")
    else:
        print_warning("No schedules were deleted")


@app.command("list")
@handle_cli_errors
def list_cmd() -> None:
    """List all remotepy schedules."""
    schedules = list_schedules()

    if not schedules:
        print_warning("No schedules found")
        return

    print_info(f"Found {len(schedules)} schedule(s):")
    for sched in schedules:
        name = sched.get("Name", "unknown")
        state = sched.get("State", "UNKNOWN")
        typer.echo(f"  {name} [{state}]")


@app.command("cleanup-role")
@handle_cli_errors
def cleanup_role(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete the scheduler IAM role (only when no schedules exist)."""
    # Check if schedules still exist
    schedules = list_schedules()
    if schedules:
        print_error(
            f"Cannot delete role: {len(schedules)} schedules still exist. "
            "Clear all schedules first with 'remote schedule clear'."
        )
        raise typer.Exit(1)

    if not yes:
        if not confirm_action("Delete", "IAM role", "remotepy-scheduler-role"):
            print_warning("Cancelled")
            return

    deleted = delete_scheduler_role()
    if deleted:
        print_success("Deleted remotepy-scheduler-role IAM role")
    else:
        print_warning("Role not found or does not exist")
