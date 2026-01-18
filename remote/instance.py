import random
import string
import subprocess
import time
from typing import Annotated, Any

import typer
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from remote.config import config_manager
from remote.exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    ResourceNotFoundError,
    ValidationError,
)
from remote.pricing import (
    format_price,
    get_instance_price_with_fallback,
)
from remote.utils import (
    format_duration,
    get_ec2_client,
    get_instance_dns,
    get_instance_id,
    get_instance_ids,
    get_instance_info,
    get_instance_name,
    get_instance_status,
    get_instance_type,
    get_instances,
    get_launch_template_id,
    get_launch_templates,
    is_instance_running,
    parse_duration_to_minutes,
)
from remote.validation import safe_get_array_item, safe_get_nested_value, validate_array_index

app = typer.Typer()
console = Console(force_terminal=True, width=200)


def _get_status_style(status: str) -> str:
    """Get the rich style for a status value."""
    status_lower = status.lower()
    if status_lower == "running":
        return "green"
    elif status_lower == "stopped":
        return "red"
    elif status_lower in ("pending", "stopping", "shutting-down"):
        return "yellow"
    return "white"


def _get_raw_launch_times(instances: list[dict[str, Any]]) -> list[Any]:
    """Extract raw launch time datetime objects from instances.

    Args:
        instances: List of reservation dictionaries from describe_instances()

    Returns:
        List of launch time datetime objects (or None for stopped instances)
    """
    from datetime import timezone

    launch_times = []

    for reservation in instances:
        reservation_instances = reservation.get("Instances", [])
        for instance in reservation_instances:
            # Check if instance has a Name tag (same filtering as get_instance_info)
            tags = {k["Key"]: k["Value"] for k in instance.get("Tags", [])}
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
def list_instances(
    cost: bool = typer.Option(
        False, "--cost", "-c", help="Show cost columns (uptime, hourly rate, estimated cost)"
    ),
) -> None:
    """
    List all EC2 instances with summary info.

    Shows a summary table of all instances. Use 'instance status' for detailed
    health information about a specific instance.

    Columns: Name, ID, DNS, Status, Type, Launch Time
    With --cost: adds Uptime, Hourly Rate, Estimated Cost

    Examples:
        remote instance ls              # List all instances
        remote instance ls --cost       # Include cost information
    """
    instances = get_instances()
    ids = get_instance_ids(instances)

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    # Get raw launch times for uptime calculation if cost is requested
    raw_launch_times = _get_raw_launch_times(instances) if cost else []

    # Format table using rich
    table = Table(title="EC2 Instances")
    table.add_column("Name", style="cyan")
    table.add_column("InstanceId", style="green")
    table.add_column("PublicDnsName")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Launch Time")

    if cost:
        table.add_column("Uptime", justify="right")
        table.add_column("$/hr", justify="right")
        table.add_column("Est. Cost", justify="right")

    for i, (name, instance_id, dns, status, it, lt) in enumerate(
        zip(names, ids, public_dnss, statuses, instance_types, launch_times, strict=False)
    ):
        status_style = _get_status_style(status)

        row_data = [
            name or "",
            instance_id or "",
            dns or "",
            f"[{status_style}]{status}[/{status_style}]",
            it or "",
            lt or "",
        ]

        if cost:
            # Calculate uptime
            uptime_str = "-"
            estimated_cost = None
            hourly_price = None

            if i < len(raw_launch_times) and raw_launch_times[i] is not None:
                from datetime import datetime, timezone

                now = datetime.now(timezone.utc)
                launch_time_dt = raw_launch_times[i]
                if launch_time_dt.tzinfo is None:
                    launch_time_dt = launch_time_dt.replace(tzinfo=timezone.utc)
                uptime_seconds = (now - launch_time_dt).total_seconds()
                uptime_str = _format_uptime(uptime_seconds)

                # Get pricing and calculate cost
                if it:
                    hourly_price, _ = get_instance_price_with_fallback(it)
                    if hourly_price is not None and uptime_seconds > 0:
                        uptime_hours = uptime_seconds / 3600
                        estimated_cost = hourly_price * uptime_hours

            row_data.append(uptime_str)
            row_data.append(format_price(hourly_price))
            row_data.append(format_price(estimated_cost))

        table.add_row(*row_data)

    console.print(table)


def _build_status_table(instance_name: str, instance_id: str) -> Panel | str:
    """Build a Rich Panel with detailed instance status information.

    Returns a Panel on success, or an error message string if there's an error.
    Shows both health status and instance details.
    """
    try:
        # Get instance health status
        status = get_instance_status(instance_id)
        instance_statuses = status.get("InstanceStatuses", [])

        # Get detailed instance info
        ec2 = get_ec2_client()
        instance_info = ec2.describe_instances(InstanceIds=[instance_id])
        reservations = instance_info.get("Reservations", [])

        if not reservations:
            return f"Instance {instance_name} not found"

        reservation = safe_get_array_item(reservations, 0, "instance reservations")
        instances = reservation.get("Instances", [])
        if not instances:
            return f"Instance {instance_name} not found"

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
        tags = instance.get("Tags", [])
        tag_dict = {t["Key"]: t["Value"] for t in tags}
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
            instance_status_str = safe_get_nested_value(
                first_status, ["InstanceStatus", "Status"], "-"
            )
            details = safe_get_nested_value(first_status, ["InstanceStatus", "Details"], [])
            if details:
                first_detail = safe_get_array_item(details, 0, "status details", {"Status": "-"})
                reachability = first_detail.get("Status", "-")

        # Build output lines
        state_style = _get_status_style(state_name)
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

        panel = Panel(
            "\n".join(lines),
            title="[bold]Instance Details[/bold]",
            border_style="blue",
        )
        return panel

    except (InstanceNotFoundError, ResourceNotFoundError) as e:
        return f"Error: {e}"
    except AWSServiceError as e:
        return f"AWS Error: {e}"
    except ValidationError as e:
        return f"Validation Error: {e}"


def _watch_status(instance_name: str, instance_id: str, interval: int) -> None:
    """Watch instance status with live updates."""
    watch_console = Console()

    try:
        with Live(console=watch_console, refresh_per_second=1, screen=True) as live:
            while True:
                result = _build_status_table(instance_name, instance_id)
                live.update(result)
                time.sleep(interval)
    except KeyboardInterrupt:
        watch_console.print("\nWatch mode stopped.")


@app.command()
def status(
    instance_name: Annotated[str | None, typer.Argument(help="Instance name")] = None,
    watch: Annotated[
        bool, typer.Option("--watch", "-w", help="Watch mode - refresh continuously")
    ] = False,
    interval: Annotated[
        int, typer.Option("--interval", "-i", help="Refresh interval in seconds")
    ] = 2,
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
        typer.secho("Error: Interval must be at least 1 second", fg=typer.colors.RED)
        raise typer.Exit(1)

    try:
        if not instance_name:
            instance_name = get_instance_name()
        instance_id = get_instance_id(instance_name)

        if watch:
            _watch_status(instance_name, instance_id, interval)
        else:
            result = _build_status_table(instance_name, instance_id)
            if isinstance(result, Panel):
                console.print(result)
            else:
                typer.secho(result, fg=typer.colors.RED)

    except (InstanceNotFoundError, ResourceNotFoundError) as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    except AWSServiceError as e:
        typer.secho(f"AWS Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)
    except ValidationError as e:
        typer.secho(f"Validation Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
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
    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    # Parse stop_in duration early to fail fast on invalid input
    stop_in_minutes: int | None = None
    if stop_in:
        try:
            stop_in_minutes = parse_duration_to_minutes(stop_in)
        except ValidationError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)

    if is_instance_running(instance_id):
        typer.secho(f"Instance {instance_name} is already running", fg=typer.colors.YELLOW)
        # If stop_in was requested and instance is already running, still schedule shutdown
        if stop_in_minutes:
            typer.secho("Scheduling automatic shutdown...", fg=typer.colors.YELLOW)
            _schedule_shutdown(instance_name, instance_id, stop_in_minutes)
        return

    try:
        get_ec2_client().start_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} started", fg=typer.colors.GREEN)

        # If stop_in was requested, wait for instance and schedule shutdown
        if stop_in_minutes:
            typer.secho(
                "Waiting for instance to be ready before scheduling shutdown...",
                fg=typer.colors.YELLOW,
            )
            # Wait for instance to be running and reachable
            max_wait = 60  # seconds
            wait_interval = 5
            waited = 0
            while waited < max_wait:
                time.sleep(wait_interval)
                waited += wait_interval
                if is_instance_running(instance_id):
                    # Check if DNS is available
                    dns = get_instance_dns(instance_id)
                    if dns:
                        break
                typer.secho(f"  Waiting for instance... ({waited}s)", fg=typer.colors.YELLOW)

            if waited >= max_wait:
                typer.secho(
                    "Warning: Instance may not be ready. Attempting to schedule shutdown anyway.",
                    fg=typer.colors.YELLOW,
                )

            # Give a bit more time for SSH to be ready
            typer.secho("Waiting for SSH to be ready...", fg=typer.colors.YELLOW)
            time.sleep(10)

            _schedule_shutdown(instance_name, instance_id, stop_in_minutes)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        typer.secho(
            f"AWS Error starting instance {instance_name}: {error_message} ({error_code})",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    except NoCredentialsError:
        typer.secho("Error: AWS credentials not found or invalid", fg=typer.colors.RED)
        raise typer.Exit(1)


def _schedule_shutdown(instance_name: str, instance_id: str, minutes: int) -> None:
    """Schedule instance shutdown via SSH using the Linux shutdown command.

    Args:
        instance_name: Name of the instance for display
        instance_id: AWS instance ID
        minutes: Number of minutes until shutdown
    """
    from datetime import datetime, timedelta, timezone

    # Get instance DNS for SSH
    dns = get_instance_dns(instance_id)
    if not dns:
        typer.secho(
            f"Cannot schedule shutdown: Instance {instance_name} has no public DNS",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Get SSH config
    user = config_manager.get_value("ssh_user") or "ubuntu"
    key = config_manager.get_value("ssh_key_path")

    # Build SSH command to run shutdown
    ssh_args = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
    ]

    if key:
        ssh_args.extend(["-i", key])

    ssh_args.append(f"{user}@{dns}")
    ssh_args.append(f"sudo shutdown -h +{minutes}")

    typer.secho(f"Scheduling shutdown for {instance_name}...", fg=typer.colors.YELLOW)

    try:
        result = subprocess.run(ssh_args, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else "Unknown SSH error"
            typer.secho(f"Failed to schedule shutdown: {error_msg}", fg=typer.colors.RED)
            raise typer.Exit(1)

        # Calculate and display shutdown time
        shutdown_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        formatted_time = shutdown_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        duration_str = format_duration(minutes)

        typer.secho(
            f"Instance '{instance_name}' will shut down in {duration_str} (at {formatted_time})",
            fg=typer.colors.GREEN,
        )
    except subprocess.TimeoutExpired:
        typer.secho("SSH connection timed out", fg=typer.colors.RED)
        raise typer.Exit(1)
    except FileNotFoundError:
        typer.secho("SSH client not found. Please install OpenSSH.", fg=typer.colors.RED)
        raise typer.Exit(1)
    except OSError as e:
        typer.secho(f"SSH connection error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


def _cancel_scheduled_shutdown(instance_name: str, instance_id: str) -> None:
    """Cancel a scheduled shutdown via SSH.

    Args:
        instance_name: Name of the instance for display
        instance_id: AWS instance ID
    """
    # Get instance DNS for SSH
    dns = get_instance_dns(instance_id)
    if not dns:
        typer.secho(
            f"Cannot cancel shutdown: Instance {instance_name} has no public DNS",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Get SSH config
    user = config_manager.get_value("ssh_user") or "ubuntu"
    key = config_manager.get_value("ssh_key_path")

    # Build SSH command to cancel shutdown
    ssh_args = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
    ]

    if key:
        ssh_args.extend(["-i", key])

    ssh_args.append(f"{user}@{dns}")
    ssh_args.append("sudo shutdown -c")

    typer.secho(f"Cancelling scheduled shutdown for {instance_name}...", fg=typer.colors.YELLOW)

    try:
        result = subprocess.run(ssh_args, capture_output=True, text=True, timeout=30)
        # shutdown -c returns non-zero if no shutdown is scheduled, which is fine
        if result.returncode == 0:
            typer.secho(
                f"Cancelled scheduled shutdown for '{instance_name}'", fg=typer.colors.GREEN
            )
        else:
            # Check if error is because no shutdown was scheduled
            stderr = result.stderr.strip() if result.stderr else ""
            if "No scheduled shutdown" in stderr or result.returncode == 1:
                typer.secho(
                    f"No scheduled shutdown to cancel for '{instance_name}'",
                    fg=typer.colors.YELLOW,
                )
            else:
                typer.secho(f"Failed to cancel shutdown: {stderr}", fg=typer.colors.RED)
                raise typer.Exit(1)
    except subprocess.TimeoutExpired:
        typer.secho("SSH connection timed out", fg=typer.colors.RED)
        raise typer.Exit(1)
    except FileNotFoundError:
        typer.secho("SSH client not found. Please install OpenSSH.", fg=typer.colors.RED)
        raise typer.Exit(1)
    except OSError as e:
        typer.secho(f"SSH connection error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def stop(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    stop_in: str | None = typer.Option(
        None,
        "--in",
        help="Schedule stop after duration (e.g., 3h, 30m, 1h30m). Uses SSH to run 'shutdown -h'.",
    ),
    cancel: bool = typer.Option(
        False,
        "--cancel",
        help="Cancel a scheduled shutdown",
    ),
) -> None:
    """
    Stop an EC2 instance.

    Prompts for confirmation before stopping.
    Uses the default instance from config if no name is provided.

    Examples:
        remote instance stop                    # Stop instance immediately
        remote instance stop --in 3h            # Schedule stop in 3 hours
        remote instance stop --in 30m           # Schedule stop in 30 minutes
        remote instance stop --in 1h30m         # Schedule stop in 1 hour 30 minutes
        remote instance stop --cancel           # Cancel scheduled shutdown
    """
    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    # Handle cancel option
    if cancel:
        if not is_instance_running(instance_id):
            typer.secho(
                f"Instance {instance_name} is not running - cannot cancel shutdown",
                fg=typer.colors.YELLOW,
            )
            return
        _cancel_scheduled_shutdown(instance_name, instance_id)
        return

    # Handle scheduled shutdown
    if stop_in:
        if not is_instance_running(instance_id):
            typer.secho(
                f"Instance {instance_name} is not running - cannot schedule shutdown",
                fg=typer.colors.YELLOW,
            )
            return
        try:
            minutes = parse_duration_to_minutes(stop_in)
            _schedule_shutdown(instance_name, instance_id, minutes)
        except ValidationError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
        return

    # Immediate stop
    if not is_instance_running(instance_id):
        typer.secho(f"Instance {instance_name} is already stopped", fg=typer.colors.YELLOW)
        return

    try:
        confirm = typer.confirm(
            f"Are you sure you want to stop instance {instance_name}?",
            default=True,
        )

        if confirm:
            get_ec2_client().stop_instances(InstanceIds=[instance_id])
            typer.secho(f"Instance {instance_name} is stopping", fg=typer.colors.GREEN)
        else:
            typer.secho(f"Instance {instance_name} is still running", fg=typer.colors.YELLOW)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        typer.secho(
            f"AWS Error stopping instance {instance_name}: {error_message} ({error_code})",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    except NoCredentialsError:
        typer.secho("Error: AWS credentials not found or invalid", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def connect(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    port_forward: str | None = typer.Option(
        None,
        "--port-forward",
        "-p",
        help="Port forwarding configuration (local:remote)",
    ),
    user: str = typer.Option("ubuntu", "--user", "-u", help="User to be used for ssh connection."),
    key: str | None = typer.Option(
        None, "--key", "-k", help="Path to SSH private key file. Falls back to config ssh_key_path."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose mode"),
    no_strict_host_key: bool = typer.Option(
        False,
        "--no-strict-host-key",
        help="Disable strict host key checking (less secure, use StrictHostKeyChecking=no)",
    ),
) -> None:
    """
    Connect to an EC2 instance via SSH.

    If the instance is not running, prompts to start it first.
    Uses the default instance from config if no name is provided.

    Examples:
        remote connect                           # Connect to default instance
        remote connect my-server                 # Connect to specific instance
        remote connect -u ec2-user               # Connect as ec2-user
        remote connect -p 8080:80                # With port forwarding
        remote connect -k ~/.ssh/my-key.pem     # With specific SSH key
    """

    if not instance_name:
        instance_name = get_instance_name()
    max_attempts = 5
    sleep_duration = 20
    instance_id = get_instance_id(instance_name)

    # Check whether the instance is up, and if not prompt the user on whether
    # to start it.

    if not is_instance_running(instance_id):
        typer.secho(f"Instance {instance_name} is not running", fg=typer.colors.RED)
        start_instance = typer.confirm(
            "Do you want to start it?",
            default=True,
            abort=True,
        )

        if start_instance:
            # Try to start the instance, and exit if it fails

            while not is_instance_running(instance_id) and max_attempts > 0:
                typer.secho(
                    f"Instance {instance_name} is not running, trying to starting it...",
                    fg=typer.colors.YELLOW,
                )
                start(instance_name)
                max_attempts -= 1

                if max_attempts == 0:
                    typer.secho(
                        f"Instance {instance_name} could not be started",
                        fg=typer.colors.RED,
                    )
                    raise typer.Exit(1)

                time.sleep(10)

        # Wait a few seconds to give the instance time to initialize

        typer.secho(
            f"Waiting {sleep_duration} seconds to allow instance to initialize",
            fg="yellow",
        )

        time.sleep(sleep_duration)

    # Now connect to the instance

    typer.secho(
        f"Connecting to instance {instance_name}",
        fg="yellow",
    )

    # Use accept-new by default (secure: accepts new keys, rejects changed keys)
    # Use no if --no-strict-host-key flag is set (legacy behavior, less secure)
    strict_host_key_value = "no" if no_strict_host_key else "accept-new"
    arguments = [
        "-o",
        f"StrictHostKeyChecking={strict_host_key_value}",
    ]

    # Check for default key from config if not provided
    if not key:
        key = config_manager.get_value("ssh_key_path")

    # If SSH key is specified (from option or config), add the -i option
    if key:
        arguments.extend(["-i", key])

    # If portforwarding is enabled, add the -L option to ssh
    if port_forward:
        arguments.extend(["-L", port_forward])

    if verbose:
        arguments.extend(["-v"])

    # Connect via SSH

    dns = get_instance_dns(instance_id)
    ssh_command = ["ssh"] + arguments + [f"{user}@{dns}"]

    try:
        result = subprocess.run(ssh_command)
        if result.returncode != 0:
            typer.secho(
                f"SSH connection failed with exit code {result.returncode}", fg=typer.colors.RED
            )
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        typer.secho("SSH client not found. Please install OpenSSH.", fg=typer.colors.RED)
        raise typer.Exit(1)
    except OSError as e:
        typer.secho(f"SSH connection error: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command("type")
def instance_type(
    new_type: str | None = typer.Argument(
        None,
        help="Type of instance to convert to. If none, will print the current instance type.",
    ),
    instance_name: str | None = typer.Argument(None, help="Instance name"),
) -> None:
    """
    View or change an instance's type.

    Without TYPE argument, displays the current instance type.
    With TYPE argument, changes the instance type (instance must be stopped).

    Examples:
        remote type                    # Show default instance type
        remote type my-server          # Show specific instance type
        remote type t3.large           # Change default instance to t3.large
        remote type t3.large my-server # Change specific instance type
    """
    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)
    current_type = get_instance_type(instance_id)

    if new_type:
        # If the current instance type is the same as the requested type,
        # exit.

        if current_type == new_type:
            typer.secho(
                f"Instance {instance_name} is already of type {new_type}",
                fg=typer.colors.YELLOW,
            )

            return

        else:
            # If the instance is running prompt whether to stop it. If no,
            # then exit.

            if is_instance_running(instance_id):
                typer.secho(
                    "You can only change the type of a stopped instances",
                    fg=typer.colors.RED,
                )

                raise typer.Exit(1)

            # Change instance type

            try:
                get_ec2_client().modify_instance_attribute(
                    InstanceId=instance_id,
                    InstanceType={
                        "Value": new_type,
                    },
                )
                typer.secho(
                    f"Changing {instance_name} to {new_type}",
                    fg=typer.colors.YELLOW,
                )

                wait = 5

                with console.status("Confirming type change..."):
                    while wait > 0:
                        time.sleep(5)
                        wait -= 1

                        if get_instance_type(instance_id) == new_type:
                            typer.secho(
                                "Done",
                                fg=typer.colors.YELLOW,
                            )
                            typer.secho(
                                f"Instance {instance_name} is now of type {new_type}",
                                fg=typer.colors.GREEN,
                            )

                            break
                        else:
                            typer.secho(
                                f"Instance {instance_name} is still of type {current_type}",
                                fg=typer.colors.YELLOW,
                            )
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]
                typer.secho(
                    f"AWS Error changing instance {instance_name} to {new_type}: {error_message} ({error_code})",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)
            except NoCredentialsError:
                typer.secho("Error: AWS credentials not found or invalid", fg=typer.colors.RED)
                raise typer.Exit(1)

    else:
        current_instance_type = get_instance_type(instance_id)

        typer.secho(
            f"Instance {instance_name} is currently of type {current_instance_type}",
            fg=typer.colors.YELLOW,
        )


@app.command()
def launch(
    name: str | None = typer.Option(None, help="Name of the instance to be launched"),
    launch_template: str | None = typer.Option(None, help="Launch template name"),
    version: str = typer.Option("$Latest", help="Launch template version"),
) -> None:
    """
    Launch a new EC2 instance from a launch template.

    Uses default template from config if not specified.
    If no launch template is configured, lists available templates for selection.
    If no name is provided, suggests a name based on the template name.

    Examples:
        remote launch                                    # Use default or interactive
        remote launch --launch-template my-template      # Use specific template
        remote launch --name my-server --launch-template my-template
    """

    # Variables to track launch template details
    launch_template_name: str = ""
    launch_template_id: str = ""

    # Check for default template from config if not specified
    if not launch_template:
        default_template = config_manager.get_value("default_launch_template")
        if default_template:
            typer.secho(f"Using default template: {default_template}", fg=typer.colors.YELLOW)
            launch_template = default_template

    # if no launch template is specified, list all the launch templates
    if not launch_template:
        typer.secho("Please specify a launch template", fg=typer.colors.RED)
        typer.secho("Available launch templates:", fg=typer.colors.YELLOW)
        templates = get_launch_templates()

        if not templates:
            typer.secho("No launch templates found", fg=typer.colors.RED)
            raise typer.Exit(1)

        # Display templates
        table = Table(title="Launch Templates")
        table.add_column("Number", justify="right")
        table.add_column("LaunchTemplateId", style="green")
        table.add_column("LaunchTemplateName", style="cyan")
        table.add_column("Version", justify="right")

        for i, template in enumerate(templates, 1):
            table.add_row(
                str(i),
                template["LaunchTemplateId"],
                template["LaunchTemplateName"],
                str(template["LatestVersionNumber"]),
            )

        console.print(table)

        typer.secho("Select a launch template by number", fg=typer.colors.YELLOW)
        launch_template_number = typer.prompt("Launch template", type=str)
        # Validate user input and safely access array
        try:
            template_index = validate_array_index(
                launch_template_number, len(templates), "launch templates"
            )
            selected_template = templates[template_index]
        except ValidationError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
        launch_template_name = str(selected_template["LaunchTemplateName"])
        launch_template_id = str(selected_template["LaunchTemplateId"])

        typer.secho(f"Launch template {launch_template_name} selected", fg=typer.colors.YELLOW)
        typer.secho(
            f"Defaulting to latest version: {selected_template['LatestVersionNumber']}",
            fg=typer.colors.YELLOW,
        )
        typer.secho(f"Launching instance based on launch template {launch_template_name}")
    else:
        # launch_template was provided as a string
        launch_template_name = launch_template
        launch_template_id = get_launch_template_id(launch_template)

    # if no name is specified, ask the user for the name

    if not name:
        random_string = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        name_suggestion = launch_template_name + "-" + random_string
        name = typer.prompt(
            "Please enter a name for the instance", type=str, default=name_suggestion
        )

    # Launch the instance with the specified launch template, version, and name
    instance = get_ec2_client().run_instances(
        LaunchTemplate={"LaunchTemplateId": launch_template_id, "Version": version},
        MaxCount=1,
        MinCount=1,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": name},
                ],
            },
        ],
    )

    # Safely access the launched instance ID
    try:
        instances = instance.get("Instances", [])
        if not instances:
            typer.secho(
                "Warning: No instance information returned from launch", fg=typer.colors.YELLOW
            )
            return

        launched_instance = safe_get_array_item(instances, 0, "launched instances")
        instance_id = launched_instance.get("InstanceId", "unknown")
        instance_type = launched_instance.get("InstanceType", "unknown")

        # Display launch summary as Rich panel
        summary_lines = [
            f"[cyan]Instance ID:[/cyan] {instance_id}",
            f"[cyan]Name:[/cyan]        {name}",
            f"[cyan]Template:[/cyan]    {launch_template_name}",
            f"[cyan]Type:[/cyan]        {instance_type}",
        ]
        panel = Panel(
            "\n".join(summary_lines),
            title="[green]Instance Launched[/green]",
            border_style="green",
        )
        console.print(panel)
    except ValidationError as e:
        typer.secho(f"Error accessing launch result: {e}", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def terminate(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    Terminate an EC2 instance.

    WARNING: This permanently deletes the instance and all associated data.
    Requires confirmation by re-entering the instance name.
    Uses the default instance from config if no name is provided.
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    # Check if instance is managed by Terraform
    instance_info = get_ec2_client().describe_instances(InstanceIds=[instance_id])
    # Safely access instance information
    tags: list[dict[str, str]] = []
    try:
        reservations = instance_info.get("Reservations", [])
        if not reservations:
            typer.secho("Warning: No instance information found", fg=typer.colors.YELLOW)
        else:
            reservation = safe_get_array_item(reservations, 0, "instance reservations")
            instances = reservation.get("Instances", [])
            if not instances:
                typer.secho("Warning: No instance details found", fg=typer.colors.YELLOW)
            else:
                instance = safe_get_array_item(instances, 0, "instances")
                tags = instance.get("Tags", [])
    except ValidationError as e:
        typer.secho(f"Error accessing instance information: {e}", fg=typer.colors.RED)
        # Continue with empty tags

    # If the instance is managed by Terraform, warn user

    # Confirmation step
    typer.secho(
        f"WARNING: You are about to terminate instance {instance_name}. "
        f"All volumes and data associated with this instance will be deleted permanently.",
        fg=typer.colors.RED,
    )
    typer.secho(
        "To create a snapshot or an image of the instance before termination, use the relevant AWS commands.",
        fg=typer.colors.YELLOW,
    )

    confirm_name = typer.prompt("To confirm, please re-enter the instance name", type=str)

    if confirm_name != instance_name:
        typer.secho("Instance names did not match. Aborting termination.", fg=typer.colors.RED)

        return

    terraform_managed = any("terraform" in tag["Value"].lower() for tag in tags)

    if terraform_managed:
        typer.secho(
            "WARNING: This instance appears to be managed by Terraform. "
            "It is recommended to destroy it using Terraform to ensure proper cleanup of associated resources.",
            fg=typer.colors.RED,
        )

    confirm = typer.confirm(
        f"Are you sure you want to terminate instance {instance_name}?",
        default=False,
    )

    if confirm:
        get_ec2_client().terminate_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} is being terminated", fg=typer.colors.GREEN)
    else:
        typer.secho(
            f"Termination of instance {instance_name} has been cancelled",
            fg=typer.colors.YELLOW,
        )


def _format_uptime(seconds: float | None) -> str:
    """Format uptime in seconds to human-readable string.

    Args:
        seconds: Uptime in seconds, or None

    Returns:
        Human-readable string like '2h 45m' or '3d 5h 30m'
    """
    if seconds is None or seconds < 0:
        return "-"

    total_minutes = int(seconds // 60)
    days = total_minutes // (24 * 60)
    remaining = total_minutes % (24 * 60)
    hours = remaining // 60
    minutes = remaining % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")

    return " ".join(parts)


if __name__ == "__main__":
    app()
