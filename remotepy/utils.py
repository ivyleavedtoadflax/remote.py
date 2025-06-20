import sys
from configparser import ConfigParser
from datetime import datetime

import boto3
import typer
import wasabi

msg = wasabi.Printer()

app = typer.Typer()

ec2_client = boto3.client("ec2")


def get_account_id():
    """Returns the caller id, this is the AWS account id not the AWS user id"""

    return boto3.client("sts").get_caller_identity()["Account"]


def get_instance_id(instance_name):
    """Returns the id of the instance"""

    instances = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [instance_name]},
            {
                "Name": "instance-state-name",
                "Values": ["pending", "stopping", "stopped", "running"],
            },
        ]
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


def get_instances(exclude_terminated: bool = False):
    """
    Get all instances, optionally excluding those in a 'terminated' state.
    """

    return ec2_client.describe_instances()["Reservations"]


def get_instance_dns(instance_id):
    """Returns the public IP address of the instance"""

    return ec2_client.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][
        0
    ]["PublicDnsName"]


def get_instance_name(cfg: ConfigParser):
    """Returns the name of the instance as defined in the config file"""

    if instance_name := cfg["DEFAULT"].get("instance_name"):
        return instance_name
    else:
        typer.secho("Instance name not found in config file", fg=typer.colors.RED)
        typer.secho("Run `remotepy config add` to add it", fg=typer.colors.RED)
        sys.exit(1)


def get_instance_info(instances: list, name_filter: str = None, drop_nameless: bool = False):
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
    launch_times = []

    for i in instances:
        for instance in i["Instances"]:
            # Check whether there is a Name tag, and break out of the loop
            # if there is not. This is to avoid fetching information about
            # instances that are part of kubernetes clusters, etc.

            tags = {k["Key"]: k["Value"] for k in instance.get("Tags", [])}

            if not tags or "Name" not in tags:
                break
            else:
                names.append(tags["Name"])
                public_dnss.append(instance["PublicDnsName"])

                if (status := instance["State"]["Name"]) == "running":
                    launch_time = instance["LaunchTime"].timestamp()
                    launch_time = datetime.utcfromtimestamp(launch_time)
                    launch_time = launch_time.strftime("%Y-%m-%d %H:%M:%S UTC")

                else:
                    launch_time = None
                launch_times.append(launch_time)
                statuses.append(status)
                instance_types.append(instance["InstanceType"])

    return names, public_dnss, statuses, instance_types, launch_times


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


def is_instance_stopped(instance_id):
    """Returns True if the instance is stopped"""

    status = get_instance_status(instance_id)

    if status["InstanceStatuses"]:
        if status["InstanceStatuses"][0]["InstanceState"]["Name"] == "stopped":
            return True
        else:
            return False


def get_instance_type(instance_id):
    """Returns the instance type of the instance"""

    return ec2_client.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][
        0
    ]["InstanceType"]


def get_volume_ids(instance_id):
    """Returns a list of volume ids attached to the instance"""

    return [
        i["VolumeId"]
        for i in ec2_client.describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}]
        )["Volumes"]
    ]


def get_volume_name(volume_id):
    """Returns the name of the volume"""

    volume = ec2_client.describe_volumes(VolumeIds=[volume_id])["Volumes"][0]

    volume_name = ""

    for tag in volume.get("Tags", []):
        if tag["Key"] == "Name":
            volume_name = tag["Value"]

    return volume_name


def get_snapshot_status(snapshot_id):
    """Returns the status of the snapshot"""

    return ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])["Snapshots"][0]["State"]


def get_launch_template_id(launch_template_name: str):
    """
    Get the launch template ID corresponding to a given launch template name.

    This function queries AWS EC2 to get details of all launch templates with the specified name.
    It then retrieves and returns the ID of the first matching launch template.

    Args:
        launch_template_name (str): The name of the launch template.

    Returns:
        str: The ID of the launch template.

    Example usage:
        template_id = get_launch_template_id("my-template-name")
    """
    launch_templates = ec2_client.describe_launch_templates(
        Filters=[{"Name": "tag:Name", "Values": [launch_template_name]}]
    )

    launch_template_id = launch_templates["LaunchTemplates"][0]["LaunchTemplateId"]

    return launch_template_id
