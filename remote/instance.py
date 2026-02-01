import contextlib
import subprocess
import sys
import time
import webbrowser
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import typer
from rich.live import Live
from rich.panel import Panel

from remote.autoshutdown import app as autoshutdown_app
from remote.config import config_manager
from remote.exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    InvalidInputError,
    MultipleInstancesFoundError,
    ResourceNotFoundError,
    ValidationError,
)
from remote.instance_resolver import (
    get_instance_name,
    launch_instance_from_template,
    resolve_instance_or_exit,
)
from remote.pricing import (
    format_price,
    get_instance_price_with_fallback,
)
from remote.settings import (
    CONNECTION_RETRY_SLEEP_SECONDS,
    DEFAULT_EXEC_TIMEOUT_SECONDS,
    DEFAULT_SSH_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_SSH_USER,
    MAX_CONNECTION_ATTEMPTS,
    MAX_STARTUP_WAIT_SECONDS,
    SECONDS_PER_HOUR,
    SSH_OPERATION_TIMEOUT_SECONDS,
    SSH_READINESS_WAIT_SECONDS,
    SSH_SERVER_ALIVE_COUNT_MAX,
    SSH_SERVER_ALIVE_INTERVAL,
    STARTUP_POLL_INTERVAL_SECONDS,
    TYPE_CHANGE_MAX_POLL_ATTEMPTS,
    TYPE_CHANGE_POLL_INTERVAL_SECONDS,
)
from remote.tracking import tracking_manager
from remote.utils import (
    confirm_action,
    console,
    create_table,
    extract_tags_dict,
    format_duration,
    get_ec2_client,
    get_instance_dns,
    get_instance_id,
    get_instance_ids,
    get_instance_info,
    get_instance_status,
    get_instance_type,
    get_instances,
    get_status_style,
    handle_aws_errors,
    handle_cli_errors,
    is_instance_running,
    parse_duration_to_minutes,
    print_error,
    print_success,
    print_warning,
    styled_column,
)
from remote.validation import (
    safe_get_array_item,
    safe_get_nested_value,
    sanitize_input,
    validate_instance_type,
    validate_ssh_key_path,
)

app = typer.Typer()


def _validate_no_start_flag(ctx: typer.Context, value: bool) -> bool:
    """Validate that --no-start is not used with --start.

    This callback runs at parse time to catch mutually exclusive flags early.

    Args:
        ctx: Typer context containing parsed parameters
        value: The value of the --no-start flag

    Returns:
        The validated value

    Raises:
        typer.BadParameter: If both --start and --no-start are specified
    """
    if value and ctx.params.get("auto_start"):
        raise typer.BadParameter("Cannot use both --start and --no-start")
    return value


@contextlib.contextmanager
def handle_ssh_errors(operation: str = "SSH operation") -> Generator[None, None, None]:
    """Context manager for consistent SSH subprocess error handling.

    Catches common SSH subprocess exceptions and converts them to user-friendly
    error messages with consistent formatting.

    Args:
        operation: Description of the SSH operation for error messages

    Yields:
        None

    Raises:
        typer.Exit: When an SSH-related error is caught
    """
    try:
        yield
    except subprocess.TimeoutExpired:
        print_error(f"{operation} timed out")
        raise typer.Exit(1)
    except FileNotFoundError:
        print_error("SSH client not found. Please install OpenSSH.")
        raise typer.Exit(1)
    except OSError as e:
        print_error(f"SSH connection error: {e}")
        raise typer.Exit(1)


def _get_raw_launch_times(instances: list[dict[str, Any]]) -> list[Any]:
    """Extract raw launch time datetime objects from instances.

    Args:
        instances: List of reservation dictionaries from describe_instances()

    Returns:
        List of launch time datetime objects (or None for stopped instances)
    """
    launch_times = []

    for reservation in instances:
        reservation_instances = reservation.get("Instances", [])
        for instance in reservation_instances:
            # Check if instance has a Name tag (same filtering as get_instance_info)
            tags = extract_tags_dict(instance.get("Tags"))
            if not tags or "Name" not in tags:
                continue

            state_info = instance.get("State", {})
            status = state_info.get("Name", "unknown")

            # Only include launch time for running instances
            if status == "running" and "LaunchTime" in instance:
                launch_time = instance["LaunchTime"]
                # Ensure timezone awareness
                if hasattr(launch_time, "tzinfo") and launch_time.tzinfo is None:
                    launch_time = launch_time.replace(tzinfo=timezone.utc)
                launch_times.append(launch_time)
            else:
                launch_times.append(None)

    return launch_times


@app.command("ls")
@app.command("list")
@handle_cli_errors
def list_instances(
    cost: bool = typer.Option(
        False, "--cost", "-c", help="Show cost columns (uptime, hourly rate, estimated cost)"
    ),
    lifetime: bool = typer.Option(
        False,
        "--lifetime",
        "-L",
        help="Show lifetime cumulative costs instead of current session (requires --cost)",
    ),
    all_instances: bool = typer.Option(False, "--all", "-a", help="Include terminated instances"),
) -> None:
    """
    List all EC2 instances with summary info.

    Shows a summary table of all instances. Use 'instance status' for detailed
    health information about a specific instance. Terminated instances are
    excluded by default; use --all to include them.

    Columns: Name, ID, DNS, Status, Type, Launch Time
    With --cost: adds Uptime, Hourly Rate, Estimated Cost
    With --cost --lifetime: shows cumulative lifetime costs tracked across sessions

    Examples:
        remote instance ls              # List all instances (excluding terminated)
        remote instance ls --all        # Include terminated instances
        remote instance ls --cost       # Include cost information
        remote instance ls --cost --lifetime  # Show lifetime cumulative costs
    """
    instances = get_instances(exclude_terminated=not all_instances)
    ids = get_instance_ids(instances)

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    # Get raw launch times for uptime calculation if cost is requested
    raw_launch_times = _get_raw_launch_times(instances) if cost else []

    # Build column definitions
    columns: list[dict[str, Any]] = [
        styled_column("Name", "name"),
        styled_column("InstanceId", "id"),
        styled_column("PublicDnsName"),
        styled_column("Status"),
        styled_column("Type"),
        styled_column("Launch Time"),
    ]

    if cost:
        if lifetime:
            columns.extend(
                [
                    styled_column("Total Hours", "numeric", justify="right"),
                    styled_column("$/hr", "numeric", justify="right"),
                    styled_column("Lifetime Cost", "numeric", justify="right"),
                ]
            )
        else:
            columns.extend(
                [
                    styled_column("Uptime", "numeric", justify="right"),
                    styled_column("$/hr", "numeric", justify="right"),
                    styled_column("Est. Cost", "numeric", justify="right"),
                ]
            )

    rows: list[list[str]] = []
    any_fallback_used = False
    for i, (name, instance_id, dns, status, it, lt) in enumerate(
        zip(names, ids, public_dnss, statuses, instance_types, launch_times, strict=True)
    ):
        status_style = get_status_style(status)

        row_data = [
            name or "",
            instance_id or "",
            dns or "",
            f"[{status_style}]{status}[/{status_style}]",
            it or "",
            lt or "",
        ]

        if cost:
            hourly_price = None
            used_fallback = False

            # Get hourly price for this instance type
            if it:
                hourly_price, used_fallback = get_instance_price_with_fallback(it)
                if used_fallback:
                    any_fallback_used = True

            if lifetime:
                # Show lifetime cumulative costs from tracking
                lifetime_stats = tracking_manager.get_lifetime_stats(instance_id)
                if lifetime_stats:
                    total_hours, total_cost, _ = lifetime_stats
                    uptime_str = format_duration(seconds=total_hours * SECONDS_PER_HOUR)
                    estimated_cost = total_cost if total_cost > 0 else None
                else:
                    uptime_str = "-"
                    estimated_cost = None
            else:
                # Show current session costs
                uptime_str = "-"
                estimated_cost = None

                if i < len(raw_launch_times) and raw_launch_times[i] is not None:
                    now = datetime.now(timezone.utc)
                    launch_time_dt = raw_launch_times[i]
                    if launch_time_dt.tzinfo is None:
                        launch_time_dt = launch_time_dt.replace(tzinfo=timezone.utc)
                    uptime_seconds = (now - launch_time_dt).total_seconds()
                    uptime_str = format_duration(seconds=uptime_seconds)

                    if hourly_price is not None and uptime_seconds > 0:
                        uptime_hours = uptime_seconds / SECONDS_PER_HOUR
                        estimated_cost = hourly_price * uptime_hours

            row_data.append(uptime_str)
            # Add asterisk indicator if fallback pricing was used
            price_suffix = "*" if used_fallback and hourly_price is not None else ""
            row_data.append(format_price(hourly_price) + price_suffix)
            row_data.append(format_price(estimated_cost) + price_suffix)

        rows.append(row_data)

    console.print(create_table("EC2 Instances", columns, rows))
    if cost and any_fallback_used:
        console.print("[dim]* Estimated price (region pricing unavailable)[/dim]")
    if cost and lifetime:
        console.print("[dim]Lifetime costs tracked from CLI start/stop operations[/dim]")


def _build_status_table(instance_name: str, instance_id: str) -> Panel:
    """Build a Rich Panel with detailed instance status information.

    Shows both health status and instance details.

    Raises:
        InstanceNotFoundError: If the instance is not found
        AWSServiceError: If there's an error calling AWS APIs
        ResourceNotFoundError: If required resources are missing
    """
    # Get instance health status
    status = get_instance_status(instance_id)
    instance_statuses = status.get("InstanceStatuses", [])

    # Get detailed instance info
    ec2 = get_ec2_client()
    instance_info = ec2.describe_instances(InstanceIds=[instance_id])
    reservations = instance_info.get("Reservations", [])

    if not reservations:
        raise InstanceNotFoundError(instance_name)

    reservation = safe_get_array_item(reservations, 0, "instance reservations")
    instances = reservation.get("Instances", [])
    if not instances:
        raise InstanceNotFoundError(instance_name)

    instance = safe_get_array_item(instances, 0, "instances")

    # Extract instance details
    state_info = instance.get("State", {})
    state_name = state_info.get("Name", "unknown")
    instance_type = instance.get("InstanceType", "unknown")
    public_ip = instance.get("PublicIpAddress", "-")
    private_ip = instance.get("PrivateIpAddress", "-")
    public_dns = instance.get("PublicDnsName", "-") or "-"
    key_name = instance.get("KeyName", "-")
    launch_time = instance.get("LaunchTime")
    az = instance.get("Placement", {}).get("AvailabilityZone", "-")

    # Get security groups
    security_groups = instance.get("SecurityGroups", [])
    sg_names = [sg.get("GroupName", "") for sg in security_groups]
    sg_display = ", ".join(sg_names) if sg_names else "-"

    # Get tags (excluding Name)
    tag_dict = extract_tags_dict(instance.get("Tags"))
    other_tags = {k: v for k, v in tag_dict.items() if k != "Name"}

    # Format launch time
    launch_time_str = "-"
    if launch_time:
        launch_time_str = launch_time.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Get health status if running
    system_status = "-"
    instance_status_str = "-"
    reachability = "-"

    if instance_statuses:
        first_status = safe_get_array_item(instance_statuses, 0, "instance statuses")
        system_status = safe_get_nested_value(first_status, ["SystemStatus", "Status"], "-")
        instance_status_str = safe_get_nested_value(first_status, ["InstanceStatus", "Status"], "-")
        details = safe_get_nested_value(first_status, ["InstanceStatus", "Details"], [])
        if details:
            first_detail = safe_get_array_item(details, 0, "status details", {"Status": "-"})
            reachability = first_detail.get("Status", "-")

    # Build output lines
    state_style = get_status_style(state_name)
    lines = [
        f"[cyan]Instance ID:[/cyan]    {instance_id}",
        f"[cyan]Name:[/cyan]           {instance_name}",
        f"[cyan]State:[/cyan]          [{state_style}]{state_name}[/{state_style}]",
        f"[cyan]Type:[/cyan]           {instance_type}",
        f"[cyan]AZ:[/cyan]             {az}",
        "",
        "[bold]Network[/bold]",
        f"[cyan]Public IP:[/cyan]      {public_ip}",
        f"[cyan]Private IP:[/cyan]     {private_ip}",
        f"[cyan]Public DNS:[/cyan]     {public_dns}",
        "",
        "[bold]Configuration[/bold]",
        f"[cyan]Key Pair:[/cyan]       {key_name}",
        f"[cyan]Security Groups:[/cyan] {sg_display}",
        f"[cyan]Launch Time:[/cyan]    {launch_time_str}",
    ]

    # Add health section if instance is running
    if state_name == "running":
        lines.extend(
            [
                "",
                "[bold]Health Status[/bold]",
                f"[cyan]System Status:[/cyan]   {system_status}",
                f"[cyan]Instance Status:[/cyan] {instance_status_str}",
                f"[cyan]Reachability:[/cyan]   {reachability}",
            ]
        )

    # Add tags if present
    if other_tags:
        lines.extend(["", "[bold]Tags[/bold]"])
        for key, value in other_tags.items():
            lines.append(f"[cyan]{key}:[/cyan] {value}")

    return Panel(
        "\n".join(lines),
        title="[bold]Instance Details[/bold]",
        border_style="blue",
        expand=False,
    )


def _watch_status(instance_name: str, instance_id: str, interval: int) -> None:
    """Watch instance status with live updates.

    Handles errors gracefully by displaying error messages in the live view
    and re-raising the exception to be handled by the CLI error handler.
    """
    try:
        with Live(console=console, refresh_per_second=1, screen=True) as live:
            while True:
                try:
                    result = _build_status_table(instance_name, instance_id)
                    live.update(result)
                except (
                    InstanceNotFoundError,
                    MultipleInstancesFoundError,
                    ResourceNotFoundError,
                    AWSServiceError,
                    ValidationError,
                ) as e:
                    # Display error in live view, then re-raise to exit watch mode
                    error_panel = Panel(
                        f"[red]{e}[/red]",
                        title="[bold red]Error[/bold red]",
                        border_style="red",
                        expand=False,
                    )
                    live.update(error_panel)
                    raise
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\nWatch mode stopped.")


@app.command()
@handle_cli_errors
def status(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch mode - refresh continuously"),
    interval: int = typer.Option(2, "--interval", "-i", help="Refresh interval in seconds"),
) -> None:
    """
    Show detailed information about a specific instance.

    Displays comprehensive instance details including network configuration,
    security groups, key pair, tags, and health status. Use 'instance ls'
    for a summary of all instances.

    Examples:
        remote instance status                  # Show default instance details
        remote instance status my-server        # Show specific instance details
        remote instance status --watch          # Watch status continuously
        remote instance status -w -i 5          # Watch with 5 second interval
    """
    # Validate interval
    if interval < 1:
        print_error("Error: Interval must be at least 1 second")
        raise typer.Exit(1)

    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    if watch:
        _watch_status(instance_name, instance_id, interval)
    else:
        console.print(_build_status_table(instance_name, instance_id))


def _start_instance(instance_name: str, stop_in_minutes: int | None = None) -> None:
    """Internal function to start an instance.

    Args:
        instance_name: Name of the instance to start
        stop_in_minutes: Optional number of minutes after which to schedule shutdown
    """
    instance_id = get_instance_id(instance_name)

    if is_instance_running(instance_id):
        print_warning(f"Instance {instance_name} is already running")
        # If stop_in was requested and instance is already running, still schedule shutdown
        if stop_in_minutes:
            print_warning("Scheduling automatic shutdown...")
            _schedule_shutdown(instance_name, instance_id, stop_in_minutes)
        return

    with handle_aws_errors("EC2", "start_instances"):
        get_ec2_client().start_instances(InstanceIds=[instance_id])

    # Record start event for tracking
    tracking_manager.record_start(instance_id, instance_name)

    print_success(f"Instance {instance_name} started")

    # If stop_in was requested, wait for instance and schedule shutdown
    if stop_in_minutes:
        print_warning("Waiting for instance to be ready before scheduling shutdown...")
        # Wait for instance to be running and reachable
        max_wait = MAX_STARTUP_WAIT_SECONDS
        wait_interval = STARTUP_POLL_INTERVAL_SECONDS
        waited = 0
        while waited < max_wait:
            time.sleep(wait_interval)
            waited += wait_interval
            if is_instance_running(instance_id):
                # Check if DNS is available
                dns = get_instance_dns(instance_id)
                if dns:
                    break
            print_warning(f"  Waiting for instance... ({waited}s)")

        if waited >= max_wait:
            print_warning(
                "Warning: Instance may not be ready. Attempting to schedule shutdown anyway."
            )

        # Give a bit more time for SSH to be ready
        print_warning("Waiting for SSH to be ready...")
        time.sleep(SSH_READINESS_WAIT_SECONDS)

        _schedule_shutdown(instance_name, instance_id, stop_in_minutes)


@app.command()
@handle_cli_errors
def start(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    stop_in: str | None = typer.Option(
        None,
        "--stop-in",
        help="Automatically stop instance after duration (e.g., 2h, 30m). Schedules shutdown via SSH.",
    ),
) -> None:
    """
    Start an EC2 instance.

    Uses the default instance from config if no name is provided.

    Examples:
        remote instance start                   # Start instance
        remote instance start --stop-in 2h      # Start and auto-stop in 2 hours
        remote instance start --stop-in 30m     # Start and auto-stop in 30 minutes
    """
    # Resolve instance name using consistent pattern with other commands
    instance_name, _ = resolve_instance_or_exit(instance_name)

    # Parse stop_in duration early to fail fast on invalid input
    stop_in_minutes: int | None = None
    if stop_in:
        stop_in_minutes = parse_duration_to_minutes(stop_in)

    _start_instance(instance_name, stop_in_minutes)


@dataclass(frozen=True)
class SSHConfig:
    """Configuration for SSH connections.

    Holds the SSH user and key path, retrieved from the config file.
    This dataclass is immutable (frozen) to ensure consistent values
    throughout a session.
    """

    user: str
    key_path: str | None


# Module-level cached SSH config
_ssh_config: SSHConfig | None = None


def get_ssh_config() -> SSHConfig:
    """Get cached SSH configuration from config file.

    Retrieves SSH user and key path from config, caching the result
    for subsequent calls to avoid repeated config file access.

    Returns:
        SSHConfig with user (defaults to "ubuntu") and key_path (may be None)
    """
    global _ssh_config
    if _ssh_config is None:
        user = config_manager.get_value("ssh_user") or DEFAULT_SSH_USER
        key = config_manager.get_value("ssh_key_path")
        _ssh_config = SSHConfig(user=user, key_path=key)
    return _ssh_config


def reset_ssh_config_cache() -> None:
    """Reset the cached SSH configuration.

    This is primarily useful for testing, where the config manager may be
    mocked with different values between tests. In production code, the
    cache is typically not reset during a session.
    """
    global _ssh_config
    _ssh_config = None


def _ensure_ssh_key(key: str | None) -> str | None:
    """Ensure SSH key is available, falling back to config if not provided.

    Args:
        key: SSH key path provided by user, or None

    Returns:
        The provided key if set, otherwise the key from config (which may also be None)
    """
    if not key:
        return get_ssh_config().key_path
    return key


def parse_port_specification(port_spec: str) -> tuple[int, int]:
    """Parse a port specification string into local and remote ports.

    Args:
        port_spec: Port specification in format "port" or "local:remote"

    Returns:
        Tuple of (local_port, remote_port)

    Raises:
        ValueError: If the port specification is invalid
    """
    parts = port_spec.split(":")

    if len(parts) == 1:
        # Single port: use same for local and remote
        try:
            port = int(parts[0])
        except ValueError:
            raise ValueError(f"Invalid port: {parts[0]}")

        if port <= 0 or port > 65535:
            raise ValueError(f"Invalid port: {port} (must be 1-65535)")

        return port, port

    elif len(parts) == 2:
        # local:remote format
        try:
            local_port = int(parts[0])
            remote_port = int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid port specification: {port_spec}")

        if local_port <= 0 or local_port > 65535:
            raise ValueError(f"Invalid port: {local_port} (must be 1-65535)")
        if remote_port <= 0 or remote_port > 65535:
            raise ValueError(f"Invalid port: {remote_port} (must be 1-65535)")

        return local_port, remote_port

    else:
        raise ValueError(
            f"Invalid port specification: {port_spec} (expected 'port' or 'local:remote')"
        )


def _build_ssh_command(
    dns: str,
    key: str | None = None,
    user: str = DEFAULT_SSH_USER,
    no_strict_host_key: bool = False,
    verbose: bool = False,
    interactive: bool = False,
    port_forward: str | None = None,
) -> list[str]:
    """Build base SSH command arguments with standard options.

    Args:
        dns: The DNS hostname or IP address to connect to
        key: Optional path to SSH private key
        user: SSH username (default: ubuntu)
        no_strict_host_key: If True, use StrictHostKeyChecking=no (less secure)
        verbose: If True, enable SSH verbose mode
        interactive: If True, omit BatchMode and ConnectTimeout for interactive sessions
        port_forward: Optional port forwarding specification (e.g., "8080:localhost:80")

    Returns:
        List of SSH command arguments ready for subprocess
    """
    strict_host_key_value = "no" if no_strict_host_key else "accept-new"
    ssh_args = [
        "ssh",
        "-o",
        f"StrictHostKeyChecking={strict_host_key_value}",
    ]

    # Non-interactive sessions use BatchMode and timeout
    if not interactive:
        ssh_args.extend(["-o", "BatchMode=yes"])
        ssh_args.extend(["-o", "ConnectTimeout=10"])
    else:
        # Interactive sessions use keepalive to detect dead connections
        # instead of a subprocess timeout which would kill active sessions
        ssh_args.extend(["-o", f"ServerAliveInterval={SSH_SERVER_ALIVE_INTERVAL}"])
        ssh_args.extend(["-o", f"ServerAliveCountMax={SSH_SERVER_ALIVE_COUNT_MAX}"])

    if key:
        ssh_args.extend(["-i", key])

    if verbose:
        ssh_args.append("-v")

    if port_forward:
        ssh_args.extend(["-L", port_forward])

    ssh_args.append(f"{user}@{dns}")
    return ssh_args


def _cancel_existing_shutdown_silently(dns: str, ssh_config: SSHConfig, instance_name: str) -> bool:
    """Cancel any existing scheduled shutdown silently.

    This is used internally by _schedule_shutdown to ensure only one shutdown
    is scheduled at a time. It does not print output unless there was an
    existing shutdown that was cancelled.

    Args:
        dns: The DNS hostname or IP address of the instance
        ssh_config: SSH configuration with user and key_path
        instance_name: Name of the instance for display

    Returns:
        True if an existing shutdown was cancelled, False otherwise
    """
    ssh_args = _build_ssh_command(dns, ssh_config.key_path, ssh_config.user)
    ssh_args.append("sudo shutdown -c 2>/dev/null || true")

    with handle_ssh_errors("Shutdown check"):
        result = subprocess.run(
            ssh_args, capture_output=True, text=True, timeout=SSH_OPERATION_TIMEOUT_SECONDS
        )
        # If the command succeeded and there was output indicating cancellation
        if (
            result.returncode == 0
            and result.stdout
            and "shutdown cancelled" in result.stdout.lower()
        ):
            print_warning(f"Cancelled existing scheduled shutdown for {instance_name}")
            return True
    return False


def _schedule_shutdown(instance_name: str, instance_id: str, minutes: int) -> None:
    """Schedule instance shutdown via SSH using the Linux shutdown command.

    If a shutdown is already scheduled, it will be cancelled first to prevent
    overlapping shutdowns.

    Args:
        instance_name: Name of the instance for display
        instance_id: AWS instance ID
        minutes: Number of minutes until shutdown
    """
    # Get instance DNS for SSH
    dns = get_instance_dns(instance_id)
    if not dns:
        print_error(f"Cannot schedule shutdown: Instance {instance_name} has no public DNS")
        raise typer.Exit(1)

    # Get SSH config
    ssh_config = get_ssh_config()

    # Cancel any existing scheduled shutdown first to prevent overlapping shutdowns
    _cancel_existing_shutdown_silently(dns, ssh_config, instance_name)

    # Build SSH command to run shutdown
    ssh_args = _build_ssh_command(dns, ssh_config.key_path, ssh_config.user)
    ssh_args.append(f"sudo shutdown -h +{minutes}")

    print_warning(f"Scheduling shutdown for {instance_name}...")

    with handle_ssh_errors("Shutdown scheduling"):
        result = subprocess.run(
            ssh_args, capture_output=True, text=True, timeout=SSH_OPERATION_TIMEOUT_SECONDS
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown SSH error"
            print_error(f"Failed to schedule shutdown: {error_msg}")
            raise typer.Exit(1)

        # Calculate and display shutdown time
        shutdown_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        formatted_time = shutdown_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        duration_str = format_duration(minutes)

        print_success(
            f"Instance '{instance_name}' will shut down in {duration_str} (at {formatted_time})"
        )


def _cancel_scheduled_shutdown(instance_name: str, instance_id: str) -> None:
    """Cancel a scheduled shutdown via SSH.

    Args:
        instance_name: Name of the instance for display
        instance_id: AWS instance ID
    """
    # Get instance DNS for SSH
    dns = get_instance_dns(instance_id)
    if not dns:
        print_error(f"Cannot cancel shutdown: Instance {instance_name} has no public DNS")
        raise typer.Exit(1)

    # Get SSH config
    ssh_config = get_ssh_config()

    # Build SSH command to cancel shutdown
    ssh_args = _build_ssh_command(dns, ssh_config.key_path, ssh_config.user)
    ssh_args.append("sudo shutdown -c")

    print_warning(f"Cancelling scheduled shutdown for {instance_name}...")

    with handle_ssh_errors("Shutdown cancellation"):
        result = subprocess.run(
            ssh_args, capture_output=True, text=True, timeout=SSH_OPERATION_TIMEOUT_SECONDS
        )
        # shutdown -c returns non-zero if no shutdown is scheduled, which is fine
        if result.returncode == 0:
            print_success(f"Cancelled scheduled shutdown for '{instance_name}'")
        else:
            # Check if error is because no shutdown was scheduled
            stderr = result.stderr.strip() if result.stderr else ""
            if "No scheduled shutdown" in stderr or result.returncode == 1:
                print_warning(f"No scheduled shutdown to cancel for '{instance_name}'")
            else:
                print_error(f"Failed to cancel shutdown: {stderr}")
                raise typer.Exit(1)


@app.command()
@handle_cli_errors
def stop(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    stop_in: str | None = typer.Option(
        None,
        "--stop-in",
        help="Schedule stop after duration (e.g., 3h, 30m, 1h30m). Uses SSH to run 'shutdown -h'.",
    ),
    cancel: bool = typer.Option(
        False,
        "--cancel",
        help="Cancel a scheduled shutdown",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt (for scripting)",
    ),
) -> None:
    """
    Stop an EC2 instance.

    Prompts for confirmation before stopping.
    Uses the default instance from config if no name is provided.

    Examples:
        remote instance stop                    # Stop instance immediately
        remote instance stop --stop-in 3h       # Schedule stop in 3 hours
        remote instance stop --stop-in 30m      # Schedule stop in 30 minutes
        remote instance stop --stop-in 1h30m    # Schedule stop in 1 hour 30 minutes
        remote instance stop --cancel           # Cancel scheduled shutdown
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Handle cancel option
    if cancel:
        if not is_instance_running(instance_id):
            print_warning(f"Instance {instance_name} is not running - cannot cancel shutdown")
            return
        _cancel_scheduled_shutdown(instance_name, instance_id)
        return

    # Handle scheduled shutdown
    if stop_in:
        if not is_instance_running(instance_id):
            print_warning(f"Instance {instance_name} is not running - cannot schedule shutdown")
            return
        minutes = parse_duration_to_minutes(stop_in)
        _schedule_shutdown(instance_name, instance_id, minutes)
        return

    # Immediate stop
    if not is_instance_running(instance_id):
        print_warning(f"Instance {instance_name} is already stopped")
        return

    if not yes:
        if not confirm_action("stop", "instance", instance_name):
            print_warning(f"Instance {instance_name} is still running")
            return

    # Get instance type for cost calculation before stopping
    instance_type = get_instance_type(instance_id)
    hourly_price = None
    if instance_type:
        hourly_price, _ = get_instance_price_with_fallback(instance_type)

    with handle_aws_errors("EC2", "stop_instances"):
        get_ec2_client().stop_instances(InstanceIds=[instance_id])

    # Record stop event for tracking
    tracking_manager.record_stop(instance_id, hourly_price, instance_name)

    print_success(f"Instance {instance_name} is stopping")


def _ensure_instance_running(
    instance_name: str,
    instance_id: str,
    auto_start: bool,
    no_start: bool,
    allow_interactive: bool = True,
    quiet: bool = False,
) -> None:
    """Ensure instance is running, starting it if necessary.

    Handles the logic for checking instance state and optionally starting it
    based on flags and interactivity.

    Args:
        instance_name: Name of the instance for display
        instance_id: AWS instance ID
        auto_start: If True, automatically start without prompting
        no_start: If True, fail immediately if not running
        allow_interactive: If True, prompt user when running in TTY
        quiet: If True, suppress status messages

    Raises:
        typer.Exit: If instance cannot be started or user declines
    """
    # Note: Validation of mutually exclusive --start/--no-start flags
    # is now done at parse time via _validate_no_start_flag callback

    if is_instance_running(instance_id):
        return

    print_error(f"Instance {instance_name} is not running")

    # Determine whether to start the instance
    should_start = False

    if no_start:
        # --no-start: fail immediately
        print_warning("Use --start to automatically start the instance, or start it manually.")
        raise typer.Exit(1)
    elif auto_start:
        # --start: auto-start without prompting
        should_start = True
    elif allow_interactive and sys.stdin.isatty():
        # Interactive: prompt user
        try:
            should_start = confirm_action("start", "instance", instance_name, default=True)
            if not should_start:
                print_warning("Cancelled.")
                raise typer.Exit(1)
        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+C or EOF gracefully
            print_warning("\nAborted.")
            raise typer.Exit(1)
    else:
        # Non-interactive mode without flags
        print_warning("Use --start to automatically start the instance, or start it manually.")
        raise typer.Exit(1)

    if should_start:
        # Try to start the instance with retry logic
        max_attempts = MAX_CONNECTION_ATTEMPTS
        while not is_instance_running(instance_id) and max_attempts > 0:
            if not quiet:
                print_warning(f"Instance {instance_name} is not running, trying to start it...")
            _start_instance(instance_name)
            max_attempts -= 1

            if max_attempts == 0:
                print_error(f"Instance {instance_name} could not be started")
                raise typer.Exit(1)

            time.sleep(SSH_READINESS_WAIT_SECONDS)

        # Wait for instance to initialize
        if not quiet:
            print_warning(
                f"Waiting {CONNECTION_RETRY_SLEEP_SECONDS} seconds to allow instance to initialize"
            )
        time.sleep(CONNECTION_RETRY_SLEEP_SECONDS)


@app.command()
@handle_cli_errors
def connect(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    port_forward: str | None = typer.Option(
        None,
        "--port-forward",
        "-p",
        help="Port forwarding configuration (local:remote)",
    ),
    user: str = typer.Option(DEFAULT_SSH_USER, "--user", "-u", help="SSH username"),
    key: str | None = typer.Option(
        None,
        "--key",
        "-k",
        callback=validate_ssh_key_path,
        help="Path to SSH private key file. Falls back to config ssh_key_path.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable SSH verbose mode"),
    no_strict_host_key: bool = typer.Option(
        False,
        "--no-strict-host-key",
        "-S",
        help="Disable strict host key checking (less secure, use StrictHostKeyChecking=no)",
    ),
    auto_start: bool = typer.Option(
        False,
        "--start",
        help="Automatically start the instance if stopped (no prompt)",
    ),
    no_start: bool = typer.Option(
        False,
        "--no-start",
        help="Fail immediately if instance is not running (no prompt)",
        callback=_validate_no_start_flag,
    ),
    timeout: int = typer.Option(
        DEFAULT_SSH_CONNECT_TIMEOUT_SECONDS,
        "--timeout",
        "-t",
        help="Session timeout in seconds (default: 0 = no timeout). Set to limit max session duration.",
    ),
    whitelist_ip: bool = typer.Option(
        False,
        "--whitelist-ip",
        "-w",
        help="Add your current public IP to the instance's security group before connecting",
    ),
    exclusive: bool = typer.Option(
        False,
        "--exclusive",
        "-e",
        help="Used with --whitelist-ip: remove all other IPs from the security group first",
    ),
) -> None:
    """
    Connect to an EC2 instance via SSH.

    If the instance is not running, prompts to start it first.
    Uses the default instance from config if no name is provided.

    Use --start to automatically start a stopped instance without prompting.
    Use --no-start to fail immediately if the instance is not running.
    Use --whitelist-ip to automatically add your current IP to the security group.
    Use --exclusive with --whitelist-ip to remove all other IPs first.

    Examples:
        remote instance connect                           # Connect to default instance
        remote instance connect my-server                 # Connect to specific instance
        remote instance connect -u ec2-user               # Connect as ec2-user
        remote instance connect -p 8080:80                # With port forwarding
        remote instance connect -k ~/.ssh/my-key.pem      # With specific SSH key
        remote instance connect --start                   # Auto-start if stopped
        remote instance connect --no-start                # Fail if not running
        remote instance connect --timeout 3600            # Limit session to 1 hour
        remote instance connect --whitelist-ip            # Add your IP before connecting
        remote instance connect -w --exclusive            # Add your IP, remove others
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Validate --exclusive requires --whitelist-ip
    if exclusive and not whitelist_ip:
        print_error("--exclusive can only be used with --whitelist-ip")
        raise typer.Exit(1)

    # Ensure instance is running (may start it if needed)
    _ensure_instance_running(
        instance_name, instance_id, auto_start, no_start, allow_interactive=True
    )

    # Handle IP whitelisting before connecting
    if whitelist_ip:
        from remote.sg import whitelist_ip_for_instance

        print_warning("Adding your IP to security group...")
        try:
            ip, modified_groups = whitelist_ip_for_instance(
                instance_id, ip_address=None, exclusive=exclusive
            )
            if modified_groups:
                print_success(f"Whitelisted IP {ip} in {len(modified_groups)} security group(s)")
            else:
                print_warning(f"IP {ip} was already whitelisted")
        except Exception as e:
            print_error(f"Failed to whitelist IP: {e}")
            print_warning("Continuing with connection attempt...")

    # Now connect to the instance

    print_warning(f"Connecting to instance {instance_name}")

    # Ensure SSH key is available (falls back to config)
    key = _ensure_ssh_key(key)

    # Get instance DNS and build SSH command
    dns = get_instance_dns(instance_id)
    if not dns:
        print_error(f"Error: Instance {instance_name} has no public DNS")
        raise typer.Exit(1)

    ssh_command = _build_ssh_command(
        dns,
        key=key,
        user=user,
        no_strict_host_key=no_strict_host_key,
        verbose=verbose,
        interactive=True,
        port_forward=port_forward,
    )

    with handle_ssh_errors("SSH connection"):
        # Use timeout if specified (0 means no timeout)
        timeout_value = timeout if timeout > 0 else None
        result = subprocess.run(ssh_command, timeout=timeout_value)
        if result.returncode != 0:
            print_error(f"SSH connection failed with exit code {result.returncode}")
            raise typer.Exit(result.returncode)


@app.command("forward")
@handle_cli_errors
def forward(
    port_spec: str = typer.Argument(..., help="Port specification: 'port' or 'local:remote'"),
    instance_name: str | None = typer.Argument(
        None, help="Instance name (uses default if not provided)"
    ),
    user: str = typer.Option(DEFAULT_SSH_USER, "--user", "-u", help="SSH username"),
    key: str | None = typer.Option(
        None,
        "--key",
        "-k",
        callback=validate_ssh_key_path,
        help="Path to SSH private key file. Falls back to config ssh_key_path.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable SSH verbose mode"),
    no_strict_host_key: bool = typer.Option(
        False,
        "--no-strict-host-key",
        "-S",
        help="Disable strict host key checking (less secure, use StrictHostKeyChecking=no)",
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        "-n",
        help="Don't automatically open the browser",
    ),
    auto_start: bool = typer.Option(
        False,
        "--start",
        help="Automatically start the instance if stopped (no prompt)",
    ),
    no_start: bool = typer.Option(
        False,
        "--no-start",
        help="Fail immediately if instance is not running (no prompt)",
        callback=_validate_no_start_flag,
    ),
) -> None:
    """
    Forward a port from a remote EC2 instance to localhost.

    Opens an SSH tunnel to forward a remote port to your local machine,
    optionally opening a browser to the forwarded port.

    Port specification:
      - Single port (e.g., '8000'): Forward remote port 8000 to local port 8000
      - local:remote (e.g., '8000:3000'): Forward remote port 3000 to local port 8000

    Examples:
        remote instance forward 8000              # Forward port 8000 (same local/remote)
        remote instance forward 8000:3000         # Forward remote 3000 to local 8000
        remote instance forward 8000 my-server    # Forward from specific instance
        remote instance forward 8000 --no-browser # Don't open browser
        remote instance forward 8000 --start      # Auto-start if stopped
    """
    # Parse port specification
    try:
        local_port, remote_port = parse_port_specification(port_spec)
    except ValueError as e:
        print_error(str(e))
        raise typer.Exit(1)

    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Ensure instance is running (may start it if needed)
    _ensure_instance_running(
        instance_name, instance_id, auto_start, no_start, allow_interactive=True
    )

    print_warning(f"Forwarding port {remote_port} from {instance_name} to localhost:{local_port}")

    # Ensure SSH key is available (falls back to config)
    key = _ensure_ssh_key(key)

    # Get instance DNS and build SSH command
    dns = get_instance_dns(instance_id)
    if not dns:
        print_error(f"Error: Instance {instance_name} has no public DNS")
        raise typer.Exit(1)

    # Build port forwarding specification for SSH -L option
    # Format: local_port:localhost:remote_port
    port_forward_spec = f"{local_port}:localhost:{remote_port}"

    ssh_command = _build_ssh_command(
        dns,
        key=key,
        user=user,
        no_strict_host_key=no_strict_host_key,
        verbose=verbose,
        interactive=True,
        port_forward=port_forward_spec,
    )

    # Add -N flag to not execute a remote command (just forward ports)
    ssh_command.insert(1, "-N")

    # Open browser if requested
    if not no_browser:
        url = f"http://localhost:{local_port}"
        print_success(f"Opening browser to {url}")
        webbrowser.open(url)

    print_warning("Press Ctrl+C to stop port forwarding")

    with handle_ssh_errors("SSH port forwarding"):
        result = subprocess.run(ssh_command)
        if result.returncode != 0:
            print_error(f"SSH port forwarding failed with exit code {result.returncode}")
            raise typer.Exit(result.returncode)


@app.command(
    "exec",
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
)
@handle_cli_errors
def exec_command(
    ctx: typer.Context,
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    user: str = typer.Option(DEFAULT_SSH_USER, "--user", "-u", help="SSH username"),
    key: str | None = typer.Option(
        None,
        "--key",
        "-k",
        callback=validate_ssh_key_path,
        help="Path to SSH private key file. Falls back to config ssh_key_path.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable SSH verbose mode"),
    no_strict_host_key: bool = typer.Option(
        False,
        "--no-strict-host-key",
        "-S",
        help="Disable strict host key checking (less secure, use StrictHostKeyChecking=no)",
    ),
    auto_start: bool = typer.Option(
        False,
        "--start",
        help="Automatically start the instance if stopped (no prompt)",
    ),
    no_start: bool = typer.Option(
        False,
        "--no-start",
        help="Fail immediately if instance is not running (no prompt)",
        callback=_validate_no_start_flag,
    ),
    timeout: int = typer.Option(
        DEFAULT_EXEC_TIMEOUT_SECONDS,
        "--timeout",
        "-t",
        help="Command timeout in seconds",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress status messages, output only command result",
    ),
) -> None:
    """
    Execute a command on a remote EC2 instance via SSH.

    Runs a single command on the instance and returns the output.
    Unlike 'connect' which opens an interactive session, 'exec' runs
    a command and exits.

    If only one argument is provided and it doesn't match a known instance,
    it will be treated as a command to run on the default instance.

    Examples:
        remote instance exec my-instance ls -la
        remote instance exec my-instance -- ps aux | grep python
        remote instance exec --start my-instance uptime
        remote instance exec -u ec2-user my-instance hostname
        remote instance exec --timeout 60 my-instance "long-running-script"
        remote instance exec --quiet my-instance cat /etc/hostname
        remote instance exec -v my-instance hostname    # Verbose SSH output
        remote instance exec ls    # Run 'ls' on default instance
    """
    # Get command from extra args
    command = list(ctx.args)

    # Resolve instance name and command
    # Handle the case where user runs "exec ls" meaning "use default instance, run ls"
    if instance_name and not command:
        # First arg provided with no additional args - could be instance name OR a command
        try:
            instance_id = get_instance_id(instance_name)
        except (InstanceNotFoundError, InvalidInputError):
            # instance_name doesn't resolve or is invalid format - treat it as command,
            # use default instance
            original_arg = instance_name
            command = [instance_name]
            instance_name = get_instance_name()
            instance_id = get_instance_id(instance_name)
            if not quiet:
                print_warning(
                    f"'{original_arg}' not found as instance, "
                    f"treating as command for default instance '{instance_name}'"
                )
    else:
        # Standard case: resolve instance (uses default if instance_name is None)
        if not instance_name:
            instance_name = get_instance_name()
        instance_id = get_instance_id(instance_name)

    # Check if command is provided
    if not command:
        print_error("Error: No command specified")
        raise typer.Exit(1)

    # Ensure instance is running (may start it if needed)
    # exec doesn't support interactive prompts, so allow_interactive=False
    _ensure_instance_running(
        instance_name, instance_id, auto_start, no_start, allow_interactive=False, quiet=quiet
    )

    # Ensure SSH key is available (falls back to config)
    key = _ensure_ssh_key(key)

    # Get instance DNS
    dns = get_instance_dns(instance_id)
    if not dns:
        print_error(f"Error: Instance {instance_name} has no public DNS")
        raise typer.Exit(1)

    # Build SSH command
    ssh_args = _build_ssh_command(
        dns, key, user, no_strict_host_key=no_strict_host_key, verbose=verbose
    )

    # Append the remote command
    ssh_args.extend(command)

    if not quiet:
        print_warning(f"Executing on {instance_name}: {' '.join(command)}")

    with handle_ssh_errors("Remote command execution"):
        result = subprocess.run(ssh_args, capture_output=True, text=True, timeout=timeout)

        # Print stdout
        if result.stdout:
            typer.echo(result.stdout, nl=False)

        # Print stderr to stderr
        if result.stderr:
            typer.echo(result.stderr, nl=False, err=True)

        if result.returncode != 0:
            raise typer.Exit(result.returncode)


@app.command("type")
@handle_cli_errors
def instance_type(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    new_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="New instance type to change to (e.g., t3.large). Instance must be stopped.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt (for scripting)",
    ),
) -> None:
    """
    View or change an instance's type.

    Without --type option, displays the current instance type.
    With --type option, changes the instance type (instance must be stopped).
    Prompts for confirmation before changing.

    Examples:
        remote instance type                              # Show default instance type
        remote instance type my-server                    # Show specific instance type
        remote instance type --type t3.large              # Change default instance to t3.large
        remote instance type my-server --type t3.large    # Change specific instance type
        remote instance type --type t3.large --yes        # Change without confirmation
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    current_type = get_instance_type(instance_id)

    if new_type:
        # Validate instance type format before making any AWS API calls
        new_type = validate_instance_type(new_type)

        # If the current instance type is the same as the requested type,
        # exit.

        if current_type == new_type:
            print_warning(f"Instance {instance_name} is already of type {new_type}")

            return

        else:
            # If the instance is running prompt whether to stop it. If no,
            # then exit.

            if is_instance_running(instance_id):
                print_error("You can only change the type of a stopped instance")

                raise typer.Exit(1)

            # Confirm type change
            if not yes:
                if not confirm_action(
                    "change type of",
                    "instance",
                    instance_name,
                    details=f"from {current_type} to {new_type}",
                ):
                    print_warning("Type change cancelled")
                    return

            # Change instance type

            with handle_aws_errors("EC2", "modify_instance_attribute"):
                get_ec2_client().modify_instance_attribute(
                    InstanceId=instance_id,
                    InstanceType={
                        "Value": new_type,
                    },
                )

            print_warning(f"Changing {instance_name} to {new_type}")

            wait = TYPE_CHANGE_MAX_POLL_ATTEMPTS

            with console.status("Confirming type change..."):
                while wait > 0:
                    time.sleep(TYPE_CHANGE_POLL_INTERVAL_SECONDS)
                    wait -= 1

                    if get_instance_type(instance_id) == new_type:
                        print_warning("Done")
                        print_success(f"Instance {instance_name} is now of type {new_type}")

                        break
                    else:
                        print_warning(f"Instance {instance_name} is still of type {current_type}")
                else:
                    # Polling timed out without confirming the type change
                    print_warning(
                        "Warning: Timed out waiting for type change to complete. "
                        "The change may still be in progress."
                    )
                    print_warning(
                        f"Please verify the instance type with: remote type {instance_name}"
                    )

    else:
        print_warning(f"Instance {instance_name} is currently of type {current_type}")


@app.command()
@handle_cli_errors
def launch(
    name: str | None = typer.Option(None, help="Name of the instance to be launched"),
    launch_template: str | None = typer.Option(None, help="Launch template name"),
    version: str = typer.Option("$Latest", help="Launch template version"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt (for scripting)",
    ),
) -> None:
    """
    Launch a new EC2 instance from a launch template.

    Uses default template from config if not specified.
    If no launch template is configured, lists available templates for selection.
    If no name is provided, suggests a name based on the template name.

    Examples:
        remote instance launch                                    # Use default or interactive
        remote instance launch --launch-template my-template      # Use specific template
        remote instance launch --name my-server --launch-template my-template
        remote instance launch --name my-server --launch-template my-template --yes
    """
    launch_instance_from_template(
        name=name, launch_template=launch_template, version=version, yes=yes
    )


@app.command()
@handle_cli_errors
def terminate(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt (for scripting)",
    ),
) -> None:
    """
    Terminate an EC2 instance.

    WARNING: This permanently deletes the instance and all associated data.
    Requires confirmation by re-entering the instance name.
    Uses the default instance from config if no name is provided.
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    # Check if instance is managed by Terraform
    with handle_aws_errors("EC2", "describe_instances"):
        instance_info = get_ec2_client().describe_instances(InstanceIds=[instance_id])

    # Safely access instance information
    tags: list[dict[str, str]] = []
    reservations = instance_info.get("Reservations", [])
    if not reservations:
        print_warning("Warning: No instance information found")
    else:
        reservation = safe_get_array_item(reservations, 0, "instance reservations")
        instances = reservation.get("Instances", [])
        if not instances:
            print_warning("Warning: No instance details found")
        else:
            instance = safe_get_array_item(instances, 0, "instances")
            tags = instance.get("Tags", [])

    # If the instance is managed by Terraform, warn user (even with --yes)
    terraform_managed = any("terraform" in tag["Value"].lower() for tag in tags)

    if terraform_managed:
        print_error(
            "WARNING: This instance appears to be managed by Terraform. "
            "It is recommended to destroy it using Terraform to ensure proper cleanup of associated resources."
        )

    # Confirmation step (skip if --yes)
    if not yes:
        print_error(
            f"WARNING: You are about to terminate instance {instance_name}. "
            f"All volumes and data associated with this instance will be deleted permanently."
        )
        print_warning(
            "To create a snapshot or an image of the instance before termination, use the relevant AWS commands."
        )

        confirm_name = typer.prompt("To confirm, please re-enter the instance name", type=str)

        # Sanitize and compare both values for proper whitespace handling
        if sanitize_input(confirm_name) != sanitize_input(instance_name):
            print_error("Instance names did not match. Aborting termination.")
            return

        if not confirm_action("terminate", "instance", instance_name):
            print_warning(f"Termination of instance {instance_name} has been cancelled")
            return

    with handle_aws_errors("EC2", "terminate_instances"):
        get_ec2_client().terminate_instances(InstanceIds=[instance_id])
    print_success(f"Instance {instance_name} is being terminated")


def _parse_remote_path(path: str) -> tuple[str | None, str]:
    """Parse a path that may include an instance name prefix.

    Paths can be in two formats:
    - Local path: /local/path or ./relative/path
    - Remote path: instance-name:/remote/path

    Args:
        path: The path to parse

    Returns:
        Tuple of (instance_name or None, path)
        For local paths, instance_name is None.
        For remote paths, instance_name is the prefix before the colon.
    """
    # Check for remote path format (instance-name:/path)
    # The colon must be followed by a / to distinguish from Windows-style paths
    if ":" in path and not path.startswith("/"):
        parts = path.split(":", 1)
        if len(parts) == 2 and parts[1].startswith("/"):
            return parts[0], parts[1]
    return None, path


def _build_rsync_command(
    source: str,
    destination: str,
    ssh_key: str | None,
    ssh_user: str,
    delete: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
    exclude: list[str] | None = None,
) -> list[str]:
    """Build rsync command with appropriate SSH options.

    Args:
        source: Source path (local or remote)
        destination: Destination path (local or remote)
        ssh_key: Path to SSH private key
        ssh_user: SSH username
        delete: If True, delete extraneous files from destination
        dry_run: If True, perform a trial run with no changes made
        verbose: If True, increase verbosity
        exclude: List of patterns to exclude

    Returns:
        List of rsync command arguments
    """
    # Build SSH command for rsync
    ssh_cmd = "ssh -o StrictHostKeyChecking=accept-new"
    if ssh_key:
        ssh_cmd += f" -i {ssh_key}"

    rsync_args = [
        "rsync",
        "-avz",  # Archive mode, verbose, compress
        "-e",
        ssh_cmd,
    ]

    if delete:
        rsync_args.append("--delete")

    if dry_run:
        rsync_args.append("--dry-run")

    if verbose:
        rsync_args.append("--progress")

    if exclude:
        for pattern in exclude:
            rsync_args.extend(["--exclude", pattern])

    rsync_args.extend([source, destination])
    return rsync_args


def _resolve_transfer_paths(source: str, destination: str) -> tuple[str, str, str, bool]:
    """Resolve source and destination paths for file transfer.

    Determines the instance name and direction of transfer based on path formats.

    Args:
        source: Source path (may include instance name prefix)
        destination: Destination path (may include instance name prefix)

    Returns:
        Tuple of (instance_name, resolved_source, resolved_destination, is_upload)
        - instance_name: The EC2 instance name
        - resolved_source: The resolved source path for rsync
        - resolved_destination: The resolved destination path for rsync
        - is_upload: True if uploading to remote, False if downloading

    Raises:
        typer.Exit: If both paths are remote or both are local
    """
    src_instance, src_path = _parse_remote_path(source)
    dst_instance, dst_path = _parse_remote_path(destination)

    if src_instance and dst_instance:
        print_error("Error: Cannot copy between two remote instances. Use local as intermediate.")
        raise typer.Exit(1)

    if not src_instance and not dst_instance:
        print_error("Error: At least one path must be a remote path (instance-name:/path)")
        raise typer.Exit(1)

    if src_instance:
        # Download: remote -> local
        return src_instance, src_path, dst_path, False
    else:
        # Upload: local -> remote
        return dst_instance, src_path, dst_path, True  # type: ignore[return-value]


@app.command()
@handle_cli_errors
def copy(
    source: str = typer.Argument(..., help="Source path (local or instance-name:/remote/path)"),
    destination: str = typer.Argument(
        ..., help="Destination path (local or instance-name:/remote/path)"
    ),
    user: str = typer.Option(DEFAULT_SSH_USER, "--user", "-u", help="SSH username"),
    key: str | None = typer.Option(
        None,
        "--key",
        "-k",
        callback=validate_ssh_key_path,
        help="Path to SSH private key file. Falls back to config ssh_key_path.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Perform a trial run with no changes made",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show progress during transfer"),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Exclude files matching pattern (can be specified multiple times)",
    ),
    auto_start: bool = typer.Option(
        False,
        "--start",
        help="Automatically start the instance if stopped (no prompt)",
    ),
    no_start: bool = typer.Option(
        False,
        "--no-start",
        help="Fail immediately if instance is not running (no prompt)",
        callback=_validate_no_start_flag,
    ),
    timeout: int = typer.Option(
        0,
        "--timeout",
        "-t",
        help="Transfer timeout in seconds (0 for no timeout)",
    ),
) -> None:
    """
    Copy files to/from an EC2 instance using rsync.

    Transfers files between local machine and a remote EC2 instance.
    The remote path must be prefixed with the instance name followed by a colon.

    Uses rsync with archive mode (-a), compression (-z), and preserves permissions.
    SSH key is automatically retrieved from config if not specified.

    Examples:
        # Copy local files to remote
        remote instance copy ./data/ my-instance:/home/ubuntu/data/

        # Copy remote files to local
        remote instance copy my-instance:/home/ubuntu/logs/ ./logs/

        # Copy with specific SSH key
        remote instance copy -k ~/.ssh/key.pem ./src/ my-instance:/app/src/

        # Dry run to preview changes
        remote instance copy --dry-run ./data/ my-instance:/home/ubuntu/data/

        # Exclude certain files
        remote instance copy -e "*.pyc" -e "__pycache__" ./src/ my-instance:/app/
    """
    # Resolve paths and determine transfer direction
    instance_name, src_path, dst_path, is_upload = _resolve_transfer_paths(source, destination)

    # Get instance ID and ensure running
    instance_id = get_instance_id(instance_name)
    _ensure_instance_running(
        instance_name, instance_id, auto_start, no_start, allow_interactive=True
    )

    # Ensure SSH key is available
    key = _ensure_ssh_key(key)

    # Get instance DNS
    dns = get_instance_dns(instance_id)
    if not dns:
        print_error(f"Error: Instance {instance_name} has no public DNS")
        raise typer.Exit(1)

    # Build rsync paths
    if is_upload:
        rsync_source = src_path
        rsync_destination = f"{user}@{dns}:{dst_path}"
        direction = f"local -> {instance_name}"
    else:
        rsync_source = f"{user}@{dns}:{src_path}"
        rsync_destination = dst_path
        direction = f"{instance_name} -> local"

    # Build and execute rsync command
    rsync_cmd = _build_rsync_command(
        rsync_source,
        rsync_destination,
        key,
        user,
        delete=False,
        dry_run=dry_run,
        verbose=verbose,
        exclude=exclude,
    )

    action = "Would copy" if dry_run else "Copying"
    print_warning(f"{action} files ({direction})")

    with handle_ssh_errors("File transfer"):
        timeout_value = timeout if timeout > 0 else None
        result = subprocess.run(rsync_cmd, timeout=timeout_value)
        if result.returncode != 0:
            print_error(f"rsync failed with exit code {result.returncode}")
            raise typer.Exit(result.returncode)

    if not dry_run:
        print_success("File transfer complete")


@app.command()
@handle_cli_errors
def sync(
    source: str = typer.Argument(..., help="Source path (local or instance-name:/remote/path)"),
    destination: str = typer.Argument(
        ..., help="Destination path (local or instance-name:/remote/path)"
    ),
    user: str = typer.Option(DEFAULT_SSH_USER, "--user", "-u", help="SSH username"),
    key: str | None = typer.Option(
        None,
        "--key",
        "-k",
        callback=validate_ssh_key_path,
        help="Path to SSH private key file. Falls back to config ssh_key_path.",
    ),
    delete: bool = typer.Option(
        False,
        "--delete",
        "-d",
        help="Delete extraneous files from destination",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Perform a trial run with no changes made",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show progress during transfer"),
    exclude: list[str] | None = typer.Option(
        None,
        "--exclude",
        "-e",
        help="Exclude files matching pattern (can be specified multiple times)",
    ),
    auto_start: bool = typer.Option(
        False,
        "--start",
        help="Automatically start the instance if stopped (no prompt)",
    ),
    no_start: bool = typer.Option(
        False,
        "--no-start",
        help="Fail immediately if instance is not running (no prompt)",
        callback=_validate_no_start_flag,
    ),
    timeout: int = typer.Option(
        0,
        "--timeout",
        "-t",
        help="Transfer timeout in seconds (0 for no timeout)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt for --delete",
    ),
) -> None:
    """
    Sync files to/from an EC2 instance using rsync.

    Similar to 'copy' but supports the --delete flag to remove extraneous files
    from the destination that don't exist in the source. This makes the
    destination an exact mirror of the source.

    Uses rsync with archive mode (-a), compression (-z), and preserves permissions.
    SSH key is automatically retrieved from config if not specified.

    WARNING: The --delete flag will permanently remove files from the destination
    that don't exist in the source. Use --dry-run first to preview changes.

    Examples:
        # Sync local directory to remote
        remote instance sync ./src/ my-instance:/app/src/

        # Sync with delete (mirror mode)
        remote instance sync --delete ./src/ my-instance:/app/src/

        # Dry run to preview what would be deleted
        remote instance sync --delete --dry-run ./src/ my-instance:/app/src/

        # Sync from remote to local
        remote instance sync my-instance:/app/logs/ ./logs/

        # Exclude patterns
        remote instance sync -e "*.log" -e "tmp/" ./data/ my-instance:/data/
    """
    # Resolve paths and determine transfer direction
    instance_name, src_path, dst_path, is_upload = _resolve_transfer_paths(source, destination)

    # Get instance ID and ensure running
    instance_id = get_instance_id(instance_name)
    _ensure_instance_running(
        instance_name, instance_id, auto_start, no_start, allow_interactive=True
    )

    # Confirm delete operation if not dry-run
    if delete and not dry_run and not yes:
        print_warning(
            "WARNING: --delete will remove files from the destination that don't exist in source"
        )
        if not confirm_action("sync with delete to", "path", dst_path):
            print_warning("Sync cancelled")
            return

    # Ensure SSH key is available
    key = _ensure_ssh_key(key)

    # Get instance DNS
    dns = get_instance_dns(instance_id)
    if not dns:
        print_error(f"Error: Instance {instance_name} has no public DNS")
        raise typer.Exit(1)

    # Build rsync paths
    if is_upload:
        rsync_source = src_path
        rsync_destination = f"{user}@{dns}:{dst_path}"
        direction = f"local -> {instance_name}"
    else:
        rsync_source = f"{user}@{dns}:{src_path}"
        rsync_destination = dst_path
        direction = f"{instance_name} -> local"

    # Build and execute rsync command
    rsync_cmd = _build_rsync_command(
        rsync_source,
        rsync_destination,
        key,
        user,
        delete=delete,
        dry_run=dry_run,
        verbose=verbose,
        exclude=exclude,
    )

    action = "Would sync" if dry_run else "Syncing"
    delete_msg = " (with delete)" if delete else ""
    print_warning(f"{action} files ({direction}){delete_msg}")

    with handle_ssh_errors("File sync"):
        timeout_value = timeout if timeout > 0 else None
        result = subprocess.run(rsync_cmd, timeout=timeout_value)
        if result.returncode != 0:
            print_error(f"rsync failed with exit code {result.returncode}")
            raise typer.Exit(result.returncode)

    if not dry_run:
        print_success("File sync complete")


@app.command()
@handle_cli_errors
def stats(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """
    Show cumulative usage statistics for an instance.

    Displays lifetime usage tracked from CLI start/stop operations, including:
    - Total hours of usage across all sessions
    - Total estimated cost
    - Session history with individual costs

    Note: Only tracks usage initiated via the CLI. Operations performed
    through the AWS Console are not tracked.

    Examples:
        remote instance stats                   # Show stats for default instance
        remote instance stats my-server         # Show stats for specific instance
    """
    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    tracking = tracking_manager.get_instance_tracking(instance_id)

    if not tracking:
        print_warning(f"No tracking data found for instance '{instance_name}'")
        print_warning("Usage is tracked automatically when using 'remote instance start/stop'")
        return

    # Get current hourly price for display
    instance_type = get_instance_type(instance_id)
    hourly_price = None
    if instance_type:
        hourly_price, _ = get_instance_price_with_fallback(instance_type)

    # Build output panel
    lines = [
        f"[cyan]Instance ID:[/cyan]      {instance_id}",
        f"[cyan]Name:[/cyan]             {tracking.name or instance_name}",
        f"[cyan]Instance Type:[/cyan]    {instance_type or 'unknown'}",
        f"[cyan]Hourly Rate:[/cyan]      {format_price(hourly_price)}",
        "",
        "[bold]Lifetime Usage[/bold]",
        f"[cyan]Total Hours:[/cyan]      {tracking.total_hours:.2f}",
        f"[cyan]Total Cost:[/cyan]       {format_price(tracking.total_cost)}",
        f"[cyan]Total Sessions:[/cyan]   {len(tracking.sessions)}",
    ]

    if tracking.last_updated:
        lines.append(f"[cyan]Last Updated:[/cyan]    {tracking.last_updated}")

    # Show recent sessions (last 5)
    if tracking.sessions:
        lines.extend(["", "[bold]Recent Sessions[/bold]"])
        recent_sessions = tracking.sessions[-5:]
        for session in reversed(recent_sessions):
            start_str = session.start[:19] if session.start else "-"
            stop_str = session.stop[:19] if session.stop else "running"
            cost_str = format_price(session.cost) if session.cost > 0 else "-"
            hours_str = f"{session.hours:.2f}h" if session.hours > 0 else "-"
            lines.append(f"  {start_str} → {stop_str}  ({hours_str}, {cost_str})")

        if len(tracking.sessions) > 5:
            lines.append(f"  [dim]... and {len(tracking.sessions) - 5} more sessions[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="[bold]Instance Usage Statistics[/bold]",
        border_style="blue",
        expand=False,
    )
    console.print(panel)


@app.command("tracking-reset")
@handle_cli_errors
def tracking_reset(
    instance_name: str | None = typer.Argument(None, help="Instance name (omit to reset all)"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
    all_tracking: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Reset tracking for all instances",
    ),
) -> None:
    """
    Reset usage tracking data.

    Clears cumulative usage statistics for an instance or all instances.
    This cannot be undone.

    Examples:
        remote instance tracking-reset my-server     # Reset for specific instance
        remote instance tracking-reset --all         # Reset all tracking data
        remote instance tracking-reset --all --yes   # Reset all without confirmation
    """
    if all_tracking:
        if not yes:
            if not confirm_action("reset all", "tracking data", "all instances"):
                print_warning("Reset cancelled")
                return

        count = tracking_manager.clear_all_tracking()
        if count > 0:
            print_success(f"Reset tracking data for {count} instance(s)")
        else:
            print_warning("No tracking data to reset")
        return

    if instance_name is None:
        print_error("Error: Specify an instance name or use --all to reset all tracking")
        raise typer.Exit(1)

    instance_name, instance_id = resolve_instance_or_exit(instance_name)

    if not yes:
        if not confirm_action("reset tracking for", "instance", instance_name):
            print_warning("Reset cancelled")
            return

    if tracking_manager.clear_instance_tracking(instance_id):
        print_success(f"Reset tracking data for instance '{instance_name}'")
    else:
        print_warning(f"No tracking data found for instance '{instance_name}'")


# Register auto-shutdown sub-commands
app.add_typer(
    autoshutdown_app,
    name="auto-shutdown",
    help="Manage automatic shutdown based on CPU idle",
)
