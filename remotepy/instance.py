import builtins
import random
import string
import subprocess
import time
from typing import Any

import typer
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console
from rich.table import Table

from remotepy.config import config_manager
from remotepy.exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    ResourceNotFoundError,
    ValidationError,
)
from remotepy.pricing import format_price, get_instance_price, get_monthly_estimate
from remotepy.utils import (
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
)
from remotepy.validation import safe_get_array_item, safe_get_nested_value, validate_array_index

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


@app.command("ls")
@app.command("list")
def list_instances(
    no_pricing: bool = typer.Option(
        False, "--no-pricing", help="Skip pricing lookup (faster, no cost columns)"
    ),
) -> None:
    """
    List all EC2 instances.

    Displays a table with instance name, ID, public DNS, status, type, launch time,
    and pricing information (hourly and monthly estimates).

    Examples:
        remote list                # List with pricing
        remote list --no-pricing   # List without pricing (faster)
    """
    instances = get_instances()
    ids = get_instance_ids(instances)

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    # Format table using rich
    table = Table(title="EC2 Instances")
    table.add_column("Name", style="cyan")
    table.add_column("InstanceId", style="green")
    table.add_column("PublicDnsName")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Launch Time")

    if not no_pricing:
        table.add_column("$/hr", justify="right")
        table.add_column("$/month", justify="right")

    for name, instance_id, dns, status, it, lt in zip(
        names, ids, public_dnss, statuses, instance_types, launch_times, strict=False
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

        if not no_pricing:
            hourly_price = get_instance_price(it) if it else None
            monthly_price = get_monthly_estimate(hourly_price)
            row_data.append(format_price(hourly_price))
            row_data.append(format_price(monthly_price))

        table.add_row(*row_data)

    console.print(table)


@app.command()
def status(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    Get detailed status of an instance.

    Shows instance state, system status, and reachability information.
    Uses the default instance from config if no name is provided.
    """
    try:
        if not instance_name:
            instance_name = get_instance_name()
        instance_id = get_instance_id(instance_name)
        typer.secho(f"Getting status of {instance_name} ({instance_id})", fg=typer.colors.YELLOW)
        status = get_instance_status(instance_id)

        instance_statuses = status.get("InstanceStatuses", [])
        if instance_statuses:
            # Safely access the first status
            first_status = safe_get_array_item(instance_statuses, 0, "instance statuses")

            # Safely extract nested values with defaults
            instance_id_value = first_status.get("InstanceId", "unknown")
            state_name = safe_get_nested_value(first_status, ["InstanceState", "Name"], "unknown")
            system_status = safe_get_nested_value(
                first_status, ["SystemStatus", "Status"], "unknown"
            )
            instance_status = safe_get_nested_value(
                first_status, ["InstanceStatus", "Status"], "unknown"
            )

            # Safely access details array
            details = safe_get_nested_value(first_status, ["InstanceStatus", "Details"], [])
            reachability = "unknown"
            if details:
                first_detail = safe_get_array_item(
                    details, 0, "status details", {"Status": "unknown"}
                )
                reachability = first_detail.get("Status", "unknown")

            # Format table using rich
            table = Table(title="Instance Status")
            table.add_column("Name", style="cyan")
            table.add_column("InstanceId", style="green")
            table.add_column("InstanceState")
            table.add_column("SystemStatus")
            table.add_column("InstanceStatus")
            table.add_column("Reachability")

            state_style = _get_status_style(state_name)
            table.add_row(
                instance_name or "",
                instance_id_value,
                f"[{state_style}]{state_name}[/{state_style}]",
                system_status,
                instance_status,
                reachability,
            )

            console.print(table)
        else:
            typer.secho(f"{instance_name} is not in running state", fg=typer.colors.RED)

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
def start(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    Start an EC2 instance.

    Uses the default instance from config if no name is provided.
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    if is_instance_running(instance_id):
        typer.secho(f"Instance {instance_name} is already running", fg=typer.colors.YELLOW)

        return

    try:
        get_ec2_client().start_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} started", fg=typer.colors.GREEN)
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


@app.command()
def stop(instance_name: str | None = typer.Argument(None, help="Instance name")) -> None:
    """
    Stop an EC2 instance.

    Prompts for confirmation before stopping.
    Uses the default instance from config if no name is provided.
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

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
    key: str | None = typer.Option(None, "--key", "-k", help="Path to SSH private key file."),
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

    # If SSH key is specified, add the -i option
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


@app.command()
def type(
    type: str | None = typer.Argument(
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

    if type:
        # If the current instance type is the same as the requested type,
        # exit.

        if current_type == type:
            typer.secho(
                f"Instance {instance_name} is already of type {type}",
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
                        "Value": type,
                    },
                )
                typer.secho(
                    f"Changing {instance_name} to {type}",
                    fg=typer.colors.YELLOW,
                )

                wait = 5

                with console.status("Confirming type change..."):
                    while wait > 0:
                        time.sleep(5)
                        wait -= 1

                        if get_instance_type(instance_id) == type:
                            typer.secho(
                                "Done",
                                fg=typer.colors.YELLOW,
                            )
                            typer.secho(
                                f"Instance {instance_name} is now of type {type}",
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
                    f"AWS Error changing instance {instance_name} to {type}: {error_message} ({error_code})",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)
            except NoCredentialsError:
                typer.secho("Error: AWS credentials not found or invalid", fg=typer.colors.RED)
                raise typer.Exit(1)

    else:
        type = get_instance_type(instance_id)

        typer.secho(
            f"Instance {instance_name} is currently of type {type}",
            fg=typer.colors.YELLOW,
        )


@app.command()
def list_launch_templates() -> list[dict[str, Any]]:
    """
    List all available EC2 launch templates.

    Displays template ID, name, and latest version number.
    """
    templates = get_launch_templates()

    if not templates:
        typer.secho("No launch templates found", fg=typer.colors.YELLOW)
        return []

    # Format table using rich
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

    return templates


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

        typer.secho(
            f"Instance {instance_id} with name '{name}' launched",
            fg=typer.colors.GREEN,
        )
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
    tags: builtins.list[dict[str, str]] = []
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


if __name__ == "__main__":
    app()
