import random
import string
import subprocess
import sys
import time

import typer
import wasabi
from botocore.exceptions import ClientError, NoCredentialsError

from remotepy.exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    ResourceNotFoundError,
    ValidationError,
)
from remotepy.utils import (
    ec2_client,
    get_instance_dns,
    get_instance_id,
    get_instance_ids,
    get_instance_info,
    get_instance_name,
    get_instance_status,
    get_instance_type,
    get_instances,
    is_instance_running,
    msg,
)
from remotepy.validation import safe_get_array_item, safe_get_nested_value, validate_array_index

app = typer.Typer()


@app.command("ls")
@app.command("list")
def list():
    """
    List all instances with id, dns and status
    """
    instances = get_instances()
    ids = get_instance_ids(instances)

    names, public_dnss, statuses, instance_types, launch_times = get_instance_info(instances)

    # Format table using wasabi

    header = ["Name", "InstanceId", "PublicDnsName", "Status", "Type", "Launch Time"]
    aligns = ["l", "l", "l", "l", "l", "l"]
    data = [
        (name, id, dns, status, it, lt)
        for name, id, dns, status, it, lt in zip(
            names, ids, public_dnss, statuses, instance_types, launch_times, strict=False
        )
    ]

    # Return the status in a nicely formatted table

    formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
    typer.secho(formatted, fg=typer.colors.YELLOW)


@app.command()
def status(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Get the status of an instance
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

            # Format table using wasabi
            header = [
                "Name",
                "InstanceId",
                "InstanceState",
                "SystemStatus",
                "InstanceStatus",
                "Reachability",
            ]
            aligns = ["l", "l", "l", "l", "l", "l"]
            data = [
                [
                    instance_name,
                    instance_id_value,
                    state_name,
                    system_status,
                    instance_status,
                    reachability,
                ]
            ]

            # Return the status in a nicely formatted table
            formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
            typer.secho(formatted, fg=typer.colors.YELLOW)
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
def start(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Start the instance
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    if is_instance_running(instance_id):
        typer.secho(f"Instance {instance_name} is already running", fg=typer.colors.YELLOW)

        return

    try:
        ec2_client.start_instances(InstanceIds=[instance_id])
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
def stop(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Stop the instance
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
            ec2_client.stop_instances(InstanceIds=[instance_id])
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
    instance_name: str = typer.Argument(None, help="Instance name"),
    port_forward: str = typer.Option(
        None,
        "--port-forward",
        "-p",
        help="Port forwarding configuration (local:remote)",
    ),
    user: str = typer.Option("ubuntu", "--user", "-u", help="User to be used for ssh connection."),
    key: str = typer.Option(None, "--key", "-k", help="Path to SSH private key file."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose mode"),
    no_strict_host_key: bool = typer.Option(
        False,
        "--no-strict-host-key",
        help="Disable strict host key checking (less secure, use StrictHostKeyChecking=no)",
    ),
):
    """
    Connect to the instance with ssh
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
                    sys.exit(1)

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

    subprocess.run(["ssh"] + arguments + [f"{user}@{dns}"])


@app.command()
def type(
    type: str = typer.Argument(
        None,
        help="Type of instance to convert to. If none, will print the current instance type.",
    ),
    instance_name: str = typer.Argument(None, help="Instance name"),
):
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

                sys.exit(1)

            # Change instance type

            try:
                ec2_client.modify_instance_attribute(
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

                with msg.loading("Confirming type change..."):
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
def list_launch_templates():
    """
    List all launch templates available in the AWS EC2.

    This function queries AWS EC2 to get details of all available launch templates.
    It formats the response data into a tabular form and displays it in the console.
    The returned table includes the following columns: Number, LaunchTemplateId, LaunchTemplateName, and Version.

    Returns:
        dict: The full response from the AWS EC2 describe_launch_templates call.

    Example usage:
        python remotepy/instance.py list_launch_templates
    """
    launch_templates = ec2_client.describe_launch_templates()

    header = ["Number", "LaunchTemplateId", "LaunchTemplateName", "Version"]
    aligns = ["l"] * len(header)
    data = []

    for i, launch_template in enumerate(launch_templates["LaunchTemplates"], 1):
        data.append(
            (
                i,
                launch_template["LaunchTemplateId"],
                launch_template["LaunchTemplateName"],
                launch_template["LatestVersionNumber"],
            )
        )

    # Format table using wasabi
    formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
    typer.secho(formatted, fg=typer.colors.YELLOW)

    return launch_templates


@app.command()
def launch(
    name: str = typer.Option(None, help="Name of the instance to be launched"),
    launch_template: str = typer.Option(None, help="Launch template name"),
    version: str = typer.Option("$Latest", help="Launch template version"),
):
    """
    Launch an AWS EC2 instance based on a launch template.

    This function will launch an instance using the specified launch template and version.
    If no launch template is provided, the function will list all available launch templates and
    prompt the user to select one.

    The name of the instance can be specified with the --name option. If not provided,
    the function will prompt the user for the name and provide a suggested name based on
    the launch template name appended with a random alphanumeric string.

    Example usage:
    python remotepy/instance.py launch --launch_template my-launch-template --version 2

    Parameters:
    name: The name of the instance to be launched. This will be used as a tag for the instance.
    launch_template: The name of the launch template to use.
    version: The version of the launch template to use. Default is the latest version.
    """

    # if no launch template is specified, list all the launch templates

    if not launch_template:
        typer.secho("Please specify a launch template", fg=typer.colors.RED)
        typer.secho("Available launch templates:", fg=typer.colors.YELLOW)
        launch_templates = list_launch_templates()["LaunchTemplates"]
        typer.secho("Select a launch template by number", fg=typer.colors.YELLOW)
        launch_template_number = typer.prompt("Launch template", type=str)
        # Validate user input and safely access array
        try:
            template_index = validate_array_index(
                launch_template_number, len(launch_templates), "launch templates"
            )
            launch_template = launch_templates[template_index]
        except ValidationError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(1)
        launch_template_name = launch_template["LaunchTemplateName"]
        launch_template_id = launch_template["LaunchTemplateId"]

        typer.secho(f"Launch template {launch_template_name} selected", fg=typer.colors.YELLOW)
        typer.secho(
            f"Defaulting to latest version: {launch_template['LatestVersionNumber']}",
            fg=typer.colors.YELLOW,
        )
        typer.secho(f"Launching instance based on launch template {launch_template_name}")

    # if no name is specified, ask the user for the name

    if not name:
        random_string = "".join(random.choices(string.ascii_letters + string.digits, k=6))
        name_suggestion = launch_template_name + "-" + random_string
        name = typer.prompt(
            "Please enter a name for the instance", type=str, default=name_suggestion
        )

    # Launch the instance with the specified launch template, version, and name
    instance = ec2_client.run_instances(
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
def terminate(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Terminate the instance
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    # Check if instance is managed by Terraform
    instance_info = ec2_client.describe_instances(InstanceIds=[instance_id])
    # Safely access instance information
    try:
        reservations = instance_info.get("Reservations", [])
        if not reservations:
            typer.secho("Warning: No instance information found", fg=typer.colors.YELLOW)
            tags = []
        else:
            reservation = safe_get_array_item(reservations, 0, "instance reservations")
            instances = reservation.get("Instances", [])
            if not instances:
                typer.secho("Warning: No instance details found", fg=typer.colors.YELLOW)
                tags = []
            else:
                instance = safe_get_array_item(instances, 0, "instances")
                tags = instance.get("Tags", [])
    except ValidationError as e:
        typer.secho(f"Error accessing instance information: {e}", fg=typer.colors.RED)
        tags = []  # Continue with empty tags

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
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} is being terminated", fg=typer.colors.GREEN)
    else:
        typer.secho(
            f"Termination of instance {instance_name} has been cancelled",
            fg=typer.colors.YELLOW,
        )


if __name__ == "__main__":
    app()
