import configparser
import subprocess
import sys
import time

import boto3
import typer
import wasabi
from remotepy.config import CONFIG_PATH
from remotepy.utils import get_column_widths

cfg = configparser.ConfigParser()
cfg.read(CONFIG_PATH)

app = typer.Typer()

ec2_client = boto3.client("ec2")


def get_instance_id(instance_name):
    """Returns the id of the instance"""

    instances = ec2_client.describe_instances(
        Filters=[{"Name": "tag:Name", "Values": [instance_name]}]
    )

    if instances["Reservations"]:
        if len(instances["Reservations"]) == 1:
            return instances["Reservations"][0]["Instances"][0]["InstanceId"]
        else:
            typer.secho(
                f"Multiple instances found with name {instance_name}",
                fg=typer.colors.RED,
            )
            sys.exit(1)
    else:
        typer.secho(f"Instance {instance_name} not found", fg=typer.colors.RED)
        sys.exit(1)


def get_instance_status(instance_id: str = None):
    """Returns the status of the instance"""

    if instance_id:
        return ec2_client.describe_instance_status(InstanceIds=[instance_id])
    else:
        return ec2_client.describe_instance_status()


def get_instances():
    """Returns information about all instances"""

    return ec2_client.describe_instances()["Reservations"]


def get_instance_dns(instance_id):
    """Returns the public IP address of the instance"""

    return ec2_client.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
        "Instances"
    ][0]["PublicDnsName"]


def get_instance_name():
    """Returns the name of the instance as defined in the config file"""

    if instance_name := cfg["DEFAULT"].get("instance_name"):
        return instance_name
    else:
        typer.secho("Instance name not found in config file", fg=typer.colors.RED)
        typer.secho("Run `remotepy config add` to add it", fg=typer.colors.RED)
        sys.exit(1)


def get_instance_info(
    instances: list, name_filter: str = None, drop_nameless: bool = False
):
    """
    Get all instance names for the given account from aws cli

    Args:
        instances: List of instances returned by get_instances()
        name_filter: Filter to apply to the instance names. If not found in the
            instance name, it will be excluded from the list.
    """
    names = []
    public_dnss = []
    statuses = []
    instance_types = []

    for i in instances:
        for j in i["Instances"]:

            # Check whether there is a Name tag, and break out of the loop
            # if there is not. This is to avoid fetching information about
            # instances that are part of kubernetes clusters, etc.

            tags = {k["Key"]: k["Value"] for k in j["Tags"]}

            if "Name" not in tags:
                break
            else:
                names.append(tags["Name"])
                public_dnss.append(j["PublicDnsName"])
                statuses.append(j["State"]["Name"])
                instance_types.append(j["InstanceType"])

    return names, public_dnss, statuses, instance_types


def get_instance_ids(instances):
    """
    Returns a list of instance ids extract from the output of get_instances()
    """

    return [i["Instances"][0]["InstanceId"] for i in instances]


def is_instance_running(instance_id):
    """Returns True if the instance is running"""

    status = get_instance_status(instance_id)

    if status["InstanceStatuses"]:
        if status["InstanceStatuses"][0]["InstanceState"]["Name"] == "running":
            return True
        else:
            return False


@app.command("ls")
@app.command("list")
def list():
    """
    List all instances with id, dns and status
    """

    instances = get_instances()
    ids = get_instance_ids(instances)

    names, public_dnss, statuses, instance_types = get_instance_info(instances)

    widths = get_column_widths([names, ids, public_dnss, statuses, instance_types])

    # Format table using wasabi

    header = ["Name", "InstanceId", "PublicDnsName", "Status", "Type"]
    aligns = ["l", "l", "l", "l", "l"]
    data = [
        (name, id, dns, status, it)
        for name, id, dns, status, it in zip(
            names, ids, public_dnss, statuses, instance_types
        )
    ]

    # Return the status in a nicely formatted table

    formatted = wasabi.table(
        data, header=header, divider=True, aligns=aligns, widths=widths
    )
    typer.secho(formatted, fg=typer.colors.YELLOW)


@app.command()
def status(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Get the status of an instance
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)
    typer.secho(
        f"Getting status of {instance_name} ({instance_id})", fg=typer.colors.YELLOW
    )
    status = get_instance_status(instance_id)

    if status["InstanceStatuses"]:

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
                status["InstanceStatuses"][0]["InstanceId"],
                status["InstanceStatuses"][0]["InstanceState"]["Name"],
                status["InstanceStatuses"][0]["SystemStatus"]["Status"],
                status["InstanceStatuses"][0]["InstanceStatus"]["Status"],
                status["InstanceStatuses"][0]["InstanceStatus"]["Details"][0]["Status"],
            ]
        ]

        # Return the status in a nicely formatted table

        formatted = wasabi.table(data, header=header, divider=True, aligns=aligns)
        typer.secho(formatted, fg=typer.colors.YELLOW)
    else:
        typer.secho(f"{instance_name} is not in running state", fg=typer.colors.RED)


@app.command()
def start(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Start the instance
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    if is_instance_running(instance_id):
        typer.secho(
            f"Instance {instance_name} is already running", fg=typer.colors.YELLOW
        )

        return

    try:
        ec2_client.start_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} started", fg=typer.colors.GREEN)
    except Exception as e:
        typer.echo(f"Error starting instance {instance_name}: {e}")


@app.command()
def stop(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Stop the instance
    """

    if not instance_name:
        instance_name = get_instance_name()
    instance_id = get_instance_id(instance_name)

    if not is_instance_running(instance_id):
        typer.secho(
            f"Instance {instance_name} is already stopped", fg=typer.colors.YELLOW
        )

        return

    try:
        ec2_client.stop_instances(InstanceIds=[instance_id])
        typer.secho(f"Instance {instance_name} is stopping", fg="green")
    except Exception as e:
        typer.secho(f"Error stopping instance: {e}", fg=typer.colors.RED)


@app.command()
def connect(
    instance_name: str = typer.Argument(None, help="Instance name"),
    port_forward: str = typer.Option(
        None,
        "--port-forward",
        "-p",
        help="Port forwarding configuration (local:remote)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose mode"),
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

    arguments = [
        "-o",
        "StrictHostKeyChecking=no",
    ]

    # If portforwarding is enabled, add the -L option to ssh

    if port_forward:
        arguments.extend(["-L", port_forward])

    if verbose:
        arguments.extend(["-v"])

    # Connect via SSH

    subprocess.run(["ssh"] + arguments + [f"ubuntu@{get_instance_dns(instance_id)}"])


if __name__ == "__main__":
    app()
