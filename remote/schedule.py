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
    get_schedules_for_instance,
    list_schedules,
    parse_schedule_name,
)
from .utils import (
    confirm_action,
    console,
    create_table,
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
    validate_schedule_name,
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
    schedule_name: str | None = typer.Option(
        None, "--name", "-n", help="Schedule name (for multiple schedules per instance)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Create a wake schedule to start an instance at a specific time.

    Use --at for one-time schedules (e.g., --at tomorrow, --at tuesday).
    Use --days for recurring schedules (e.g., --days mon-fri). Defaults to mon-fri if neither specified.
    Use --name to create multiple wake schedules (e.g., --name morning, --name afternoon).
    """
    instance_name_resolved, instance_id = resolve_instance_or_exit(instance_name)

    # Check for mutually exclusive options
    if at and days:
        print_error("Cannot use both --at and --days. Use --at for one-time, --days for recurring.")
        raise typer.Exit(1)

    # Validate schedule name if provided
    if schedule_name:
        try:
            schedule_name = validate_schedule_name(schedule_name)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

    # Validate time
    try:
        hour, minute = parse_schedule_time(time)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    name_suffix = f" [{schedule_name}]" if schedule_name else ""
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
                f"to wake once at {hour:02d}:{minute:02d} on {target_date.isoformat()}{name_suffix}"
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
            name=schedule_name,
        )

        print_success(
            f"Created one-time wake schedule{name_suffix} for {instance_name_resolved}: "
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
                f"to wake at {hour:02d}:{minute:02d} on {','.join(day_list)} ({tz}){name_suffix}"
            )
            if not confirm_action("Create wake schedule", "instance", instance_name_resolved):
                print_warning("Cancelled")
                return

        create_schedule(
            instance_id=instance_id,
            action="wake",
            schedule_expression=schedule_expr,
            timezone=tz,
            name=schedule_name,
        )

        print_success(
            f"Created wake schedule{name_suffix} for {instance_name_resolved}: "
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
    schedule_name: str | None = typer.Option(
        None, "--name", "-n", help="Schedule name (for multiple schedules per instance)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Create a sleep schedule to stop an instance at a specific time.

    Use --at for one-time schedules (e.g., --at tomorrow, --at tuesday).
    Use --days for recurring schedules (e.g., --days mon-fri). Defaults to mon-fri if neither specified.
    Use --name to create multiple sleep schedules (e.g., --name morning, --name evening).
    """
    instance_name_resolved, instance_id = resolve_instance_or_exit(instance_name)

    # Check for mutually exclusive options
    if at and days:
        print_error("Cannot use both --at and --days. Use --at for one-time, --days for recurring.")
        raise typer.Exit(1)

    # Validate schedule name if provided
    if schedule_name:
        try:
            schedule_name = validate_schedule_name(schedule_name)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

    # Validate time
    try:
        hour, minute = parse_schedule_time(time)
    except Exception as e:
        print_error(str(e))
        raise typer.Exit(1)

    name_suffix = f" [{schedule_name}]" if schedule_name else ""
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
                f"to sleep once at {hour:02d}:{minute:02d} on {target_date.isoformat()}{name_suffix}"
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
            name=schedule_name,
        )

        print_success(
            f"Created one-time sleep schedule{name_suffix} for {instance_name_resolved}: "
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
                f"to sleep at {hour:02d}:{minute:02d} on {','.join(day_list)} ({tz}){name_suffix}"
            )
            if not confirm_action("Create sleep schedule", "instance", instance_name_resolved):
                print_warning("Cancelled")
                return

        create_schedule(
            instance_id=instance_id,
            action="sleep",
            schedule_expression=schedule_expr,
            timezone=tz,
            name=schedule_name,
        )

        print_success(
            f"Created sleep schedule{name_suffix} for {instance_name_resolved}: "
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

    if not schedules:
        print_warning("No schedules configured for this instance")
        return

    for sched in schedules:
        action = sched.get("action", "?")
        parsed_name = sched.get("parsed_name")
        expr = sched.get("ScheduleExpression", "")
        cron_display = _format_cron_for_display(expr) if expr.startswith("cron(") else expr
        tz = sched.get("ScheduleExpressionTimezone", "UTC")
        state = sched.get("State", "UNKNOWN")
        name_display = f" [{parsed_name}]" if parsed_name else ""
        label = f"{action.capitalize()}{name_display}:"
        typer.echo(f"  {label:20s} {cron_display} ({tz}) [{state}]")


@app.command()
@handle_cli_errors
def clear(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    wake_only: bool = typer.Option(False, "--wake", help="Clear only wake schedules"),
    sleep_only: bool = typer.Option(False, "--sleep", help="Clear only sleep schedules"),
    schedule_name: str | None = typer.Option(
        None, "--name", "-n", help="Clear only schedules with this name"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Clear schedules for an instance.

    Without --name: clears ALL schedules (or filtered by --wake/--sleep).
    With --name: clears only the named schedule(s) (wake+sleep, or filtered by --wake/--sleep).
    """
    instance_name_resolved, instance_id = resolve_instance_or_exit(instance_name)

    # Determine what to clear
    if wake_only and sleep_only:
        print_error("Cannot specify both --wake and --sleep. Use neither to clear both.")
        raise typer.Exit(1)

    # Validate schedule name if provided
    if schedule_name:
        try:
            schedule_name = validate_schedule_name(schedule_name)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)

    if schedule_name:
        # Clear specific named schedules
        actions: list[str] = []
        if wake_only:
            actions = ["wake"]
        elif sleep_only:
            actions = ["sleep"]
        else:
            actions = ["wake", "sleep"]

        # Check if any matching schedules exist
        schedules = get_schedules_for_instance(instance_id)
        matching = [
            s
            for s in schedules
            if s.get("parsed_name") == schedule_name and s.get("action") in actions
        ]

        if not matching:
            print_warning(
                f"No {'/'.join(actions)} schedule named '{schedule_name}' "
                f"for {instance_name_resolved}"
            )
            return

        if not yes:
            action_desc = "/".join(actions)
            if not confirm_action(
                f"Clear {action_desc} schedule '{schedule_name}'",
                "instance",
                instance_name_resolved,
            ):
                print_warning("Cancelled")
                return

        deleted_count = 0
        for action in actions:
            if delete_schedule(instance_id, action, name=schedule_name):  # type: ignore[arg-type]
                deleted_count += 1

        if deleted_count:
            print_success(
                f"Cleared {deleted_count} schedule(s) named '{schedule_name}' "
                f"for {instance_name_resolved}"
            )
        else:
            print_warning("No schedules were deleted")
        return

    if wake_only or sleep_only:
        # Clear all wake or all sleep schedules (named + unnamed)
        action_filter = "wake" if wake_only else "sleep"
        schedules = get_schedules_for_instance(instance_id)
        matching = [s for s in schedules if s.get("action") == action_filter]

        if not matching:
            print_warning(f"No {action_filter} schedules for {instance_name_resolved}")
            return

        if not yes:
            if not confirm_action(
                f"Clear all {action_filter} schedules ({len(matching)})",
                "instance",
                instance_name_resolved,
            ):
                print_warning("Cancelled")
                return

        deleted_count = 0
        for sched in matching:
            parsed_name = sched.get("parsed_name")
            if delete_schedule(instance_id, action_filter, name=parsed_name):  # type: ignore[arg-type]
                deleted_count += 1

        if deleted_count:
            print_success(
                f"Cleared {deleted_count} {action_filter} schedule(s) for {instance_name_resolved}"
            )
        else:
            print_warning("No schedules were deleted")
        return

    # Clear all schedules
    schedules = get_schedules_for_instance(instance_id)
    if not schedules:
        print_warning(f"No schedules configured for {instance_name_resolved}")
        return

    if not yes:
        if not confirm_action(
            f"Clear all schedules ({len(schedules)})", "instance", instance_name_resolved
        ):
            print_warning("Cancelled")
            return

    count = delete_all_schedules_for_instance(instance_id)

    if count:
        print_success(f"Cleared {count} schedule(s) for {instance_name_resolved}")
    else:
        print_warning("No schedules were deleted")


@app.command("list")
@handle_cli_errors
def list_cmd() -> None:
    """List all remotepy schedules."""
    from .scheduler import _get_schedule_by_name
    from .utils import get_instance_names_by_ids

    schedules = list_schedules()

    if not schedules:
        print_warning("No schedules found")
        return

    # First pass: collect all instance IDs and parse names
    parsed_schedules: list[
        tuple[str, str | None, str, str]
    ] = []  # (action, name, instance_id, state)
    all_instance_ids: set[str] = set()

    for sched in schedules:
        sched_name = sched.get("Name", "")
        state = sched.get("State", "UNKNOWN")

        parsed = parse_schedule_name(sched_name)
        if not parsed:
            continue

        action = parsed["action"]
        name = parsed["name"]
        instance_id = parsed["instance_id"]
        parsed_schedules.append((action, name, instance_id, state))  # type: ignore[arg-type]
        all_instance_ids.add(instance_id)  # type: ignore[arg-type]

    # Batch lookup instance names
    instance_names = get_instance_names_by_ids(list(all_instance_ids)) if all_instance_ids else {}

    columns = [
        {"name": "Instance", "style": "cyan"},
        {"name": "Action", "style": "green"},
        {"name": "Name"},
        {"name": "Schedule"},
        {"name": "Timezone"},
        {"name": "State"},
    ]

    rows: list[list[str]] = []
    for action, name, instance_id, state in parsed_schedules:
        # Get full schedule details for expression and timezone
        full_sched_name = (
            f"remotepy-{action}-{name}-{instance_id}"
            if name
            else f"remotepy-{action}-{instance_id}"
        )
        full_sched = _get_schedule_by_name(full_sched_name)
        if full_sched:
            expr = full_sched.get("ScheduleExpression", "")
            tz = full_sched.get("ScheduleExpressionTimezone", "UTC")
            display_expr = _format_cron_for_display(expr) if expr.startswith("cron(") else expr
        else:
            display_expr = "?"
            tz = "?"

        # Show instance name if available, fall back to ID
        instance_display = instance_names.get(instance_id, instance_id)

        rows.append([instance_display, action, name or "-", display_expr, tz, state])

    console.print(create_table("Schedules", columns, rows))


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
