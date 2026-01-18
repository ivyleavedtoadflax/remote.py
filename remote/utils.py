import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

import boto3
import typer
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console

from .exceptions import (
    AWSServiceError,
    InstanceNotFoundError,
    MultipleInstancesFoundError,
    ResourceNotFoundError,
    ValidationError,
)
from .validation import (
    ensure_non_empty_array,
    safe_get_array_item,
    validate_aws_response_structure,
    validate_instance_id,
    validate_instance_name,
    validate_snapshot_id,
    validate_volume_id,
)

if TYPE_CHECKING:
    from mypy_boto3_ec2.client import EC2Client
    from mypy_boto3_sts.client import STSClient

console = Console(force_terminal=True, width=200)


@lru_cache
def get_ec2_client() -> "EC2Client":
    """Get or create the EC2 client.

    Uses lazy initialization and caches the client for reuse.

    Returns:
        boto3 EC2 client instance
    """
    return boto3.client("ec2")


@lru_cache
def get_sts_client() -> "STSClient":
    """Get or create the STS client.

    Uses lazy initialization and caches the client for reuse.

    Returns:
        boto3 STS client instance
    """
    return boto3.client("sts")


def get_account_id() -> str:
    """Returns the caller id, this is the AWS account id not the AWS user id.

    Returns:
        The AWS account ID

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        response = get_sts_client().get_caller_identity()

        # Validate response structure
        validate_aws_response_structure(response, ["Account"], "get_caller_identity")

        return response["Account"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("STS", "get_caller_identity", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "STS", "get_caller_identity", "NoCredentials", "AWS credentials not found or invalid"
        )


def get_instance_id(instance_name: str) -> str:
    """Returns the id of the instance.

    Args:
        instance_name: The name of the instance to find

    Returns:
        The instance ID

    Raises:
        InstanceNotFoundError: If no instance found with the given name
        MultipleInstancesFoundError: If multiple instances found with the same name
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_name = validate_instance_name(instance_name)

    try:
        response = get_ec2_client().describe_instances(
            Filters=[
                {"Name": "tag:Name", "Values": [instance_name]},
                {
                    "Name": "instance-state-name",
                    "Values": ["pending", "stopping", "stopped", "running"],
                },
            ]
        )

        # Validate response structure
        validate_aws_response_structure(response, ["Reservations"], "describe_instances")

        reservations = response["Reservations"]
        if not reservations:
            raise InstanceNotFoundError(instance_name)

        if len(reservations) > 1:
            raise MultipleInstancesFoundError(instance_name, len(reservations))

        # Safely access the instance ID
        instances = reservations[0].get("Instances", [])
        if not instances:
            raise InstanceNotFoundError(
                instance_name, "Instance reservation found but no instances in reservation"
            )

        return instances[0]["InstanceId"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_instances", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "EC2", "describe_instances", "NoCredentials", "AWS credentials not found or invalid"
        )


def get_instance_status(instance_id: str | None = None) -> dict[str, Any]:
    """Returns the status of the instance.

    Args:
        instance_id: Optional instance ID to get status for. If None, gets all instance statuses

    Returns:
        The instance status response from AWS

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        if instance_id:
            # Validate input if provided
            instance_id = validate_instance_id(instance_id)
            response = get_ec2_client().describe_instance_status(InstanceIds=[instance_id])
        else:
            response = get_ec2_client().describe_instance_status()
        return dict(response)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_instance_status", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "EC2",
            "describe_instance_status",
            "NoCredentials",
            "AWS credentials not found or invalid",
        )


def get_instances(exclude_terminated: bool = False) -> list[dict[str, Any]]:
    """
    Get all instances, optionally excluding those in a 'terminated' state.

    Uses pagination to handle large numbers of instances (>100).

    Args:
        exclude_terminated: Whether to exclude terminated instances

    Returns:
        List of reservation dictionaries

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        filters: list[dict[str, Any]] = []
        if exclude_terminated:
            filters.append(
                {
                    "Name": "instance-state-name",
                    "Values": ["pending", "running", "shutting-down", "stopping", "stopped"],
                }
            )

        # Use paginator to handle >100 instances
        paginator = get_ec2_client().get_paginator("describe_instances")
        reservations: list[dict[str, Any]] = []

        if filters:
            page_iterator = paginator.paginate(Filters=filters)  # type: ignore[arg-type]
        else:
            page_iterator = paginator.paginate()

        for page in page_iterator:
            reservations.extend(cast(list[dict[str, Any]], page.get("Reservations", [])))

        return reservations

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_instances", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "EC2", "describe_instances", "NoCredentials", "AWS credentials not found or invalid"
        )


def get_instance_dns(instance_id: str) -> str:
    """Returns the public DNS name of the instance.

    Args:
        instance_id: The instance ID to get DNS for

    Returns:
        The public DNS name of the instance

    Raises:
        ResourceNotFoundError: If instance not found
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        response = get_ec2_client().describe_instances(InstanceIds=[instance_id])

        # Validate response structure
        validate_aws_response_structure(response, ["Reservations"], "describe_instances")

        reservations = ensure_non_empty_array(
            list(response["Reservations"]), "instance reservations"
        )
        instances = ensure_non_empty_array(list(reservations[0].get("Instances", [])), "instances")

        return str(instances[0].get("PublicDnsName", ""))

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "InvalidInstanceID.NotFound":
            raise ResourceNotFoundError("Instance", instance_id)

        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_instances", error_code, error_message)


def get_instance_name() -> str:
    """Returns the name of the instance as defined in the config file.

    Returns:
        str: Instance name if found

    Raises:
        typer.Exit: If no instance name is configured
    """
    from remote.config import config_manager

    instance_name = config_manager.get_instance_name()

    if instance_name:
        return instance_name
    else:
        typer.secho("No default instance configured.", fg=typer.colors.RED)
        typer.secho("Run `remote config add` to set up your default instance.", fg=typer.colors.RED)
        raise typer.Exit(1)


def get_instance_info(
    instances: list[dict[str, Any]], name_filter: str | None = None
) -> tuple[list[str], list[str], list[str], list[str], list[str | None]]:
    """
    Get all instance names for the given account from aws cli.

    Args:
        instances: List of instances returned by get_instances()
        name_filter: Filter to apply to the instance names. If not found in the
            instance name, it will be excluded from the list.

    Returns:
        Tuple of (names, public_dnss, statuses, instance_types, launch_times)

    Note:
        Instances without a Name tag are automatically excluded.

    Raises:
        ValidationError: If instances data is malformed
    """
    names = []
    public_dnss = []
    statuses = []
    instance_types = []
    launch_times = []

    for reservation in instances:
        # Safely access Instances array
        reservation_instances = reservation.get("Instances", [])

        for instance in reservation_instances:
            try:
                # Check whether there is a Name tag
                tags = {k["Key"]: k["Value"] for k in instance.get("Tags", [])}

                if not tags or "Name" not in tags:
                    # Skip instances without a Name tag and continue to next instance
                    continue

                instance_name = tags["Name"]

                # Apply name filter if provided
                if name_filter and name_filter not in instance_name:
                    continue

                names.append(instance_name)
                public_dnss.append(instance.get("PublicDnsName", ""))

                # Safely access state information
                state_info = instance.get("State", {})
                status = state_info.get("Name", "unknown")
                statuses.append(status)

                # Handle launch time for running instances
                if status == "running" and "LaunchTime" in instance:
                    try:
                        launch_time = instance["LaunchTime"].timestamp()
                        launch_time = datetime.fromtimestamp(launch_time, tz=timezone.utc)
                        launch_time = launch_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                    except (AttributeError, ValueError):
                        launch_time = None
                else:
                    launch_time = None

                launch_times.append(launch_time)
                instance_types.append(instance.get("InstanceType", "unknown"))

            except (KeyError, TypeError) as e:
                # Skip malformed instance data but continue processing others
                console.print(f"[yellow]Warning: Skipping malformed instance data: {e}[/yellow]")
                continue

    return names, public_dnss, statuses, instance_types, launch_times


def get_instance_ids(instances: list[dict[str, Any]]) -> list[str]:
    """Returns a list of instance ids extracted from the output of get_instances().

    Args:
        instances: List of reservation dictionaries from describe_instances()

    Returns:
        List of instance IDs

    Raises:
        ValidationError: If any reservation has no instances
    """
    instance_ids = []

    for reservation in instances:
        instances_list = reservation.get("Instances", [])
        if not instances_list:
            # Skip reservations with no instances instead of crashing
            continue

        instance_ids.append(instances_list[0]["InstanceId"])

    return instance_ids


def is_instance_running(instance_id: str) -> bool | None:
    """Returns True if the instance is running, False if not, None if unknown.

    Args:
        instance_id: The instance ID to check

    Returns:
        True if running, False if not running, None if status unknown

    Raises:
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        status = get_instance_status(instance_id)

        # Handle case where InstanceStatuses is empty (instance not running)
        instance_statuses = status.get("InstanceStatuses", [])
        if not instance_statuses:
            return False

        # Safely access the state information
        first_status = safe_get_array_item(instance_statuses, 0, "instance statuses")
        instance_state = first_status.get("InstanceState", {})
        state_name = instance_state.get("Name", "unknown")

        return bool(state_name == "running")

    except (AWSServiceError, ResourceNotFoundError, ValidationError):
        # Re-raise specific errors
        raise
    except (KeyError, TypeError, AttributeError) as e:
        # For data structure errors, log and return None
        console.print(f"[yellow]Warning: Unexpected instance status structure: {e}[/yellow]")
        return None


def is_instance_stopped(instance_id: str) -> bool | None:
    """Returns True if the instance is stopped, False if not, None if unknown.

    Args:
        instance_id: The instance ID to check

    Returns:
        True if stopped, False if not stopped, None if status unknown

    Raises:
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        status = get_instance_status(instance_id)

        # Handle case where InstanceStatuses is empty
        instance_statuses = status.get("InstanceStatuses", [])
        if not instance_statuses:
            return None  # Status unknown

        # Safely access the state information
        first_status = safe_get_array_item(instance_statuses, 0, "instance statuses")
        instance_state = first_status.get("InstanceState", {})
        state_name = instance_state.get("Name", "unknown")

        return bool(state_name == "stopped")

    except (AWSServiceError, ResourceNotFoundError, ValidationError):
        # Re-raise specific errors
        raise
    except (KeyError, TypeError, AttributeError) as e:
        # For data structure errors, log and return None
        console.print(f"[yellow]Warning: Unexpected instance status structure: {e}[/yellow]")
        return None


def get_instance_type(instance_id: str) -> str:
    """Returns the instance type of the instance.

    Args:
        instance_id: The instance ID to get type for

    Returns:
        The instance type (e.g., 't2.micro')

    Raises:
        ResourceNotFoundError: If instance not found
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        response = get_ec2_client().describe_instances(InstanceIds=[instance_id])

        # Validate response structure
        validate_aws_response_structure(response, ["Reservations"], "describe_instances")

        reservations = ensure_non_empty_array(
            list(response["Reservations"]), "instance reservations"
        )
        instances = ensure_non_empty_array(list(reservations[0].get("Instances", [])), "instances")

        return str(instances[0]["InstanceType"])

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "InvalidInstanceID.NotFound":
            raise ResourceNotFoundError("Instance", instance_id)

        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_instances", error_code, error_message)


def get_volume_ids(instance_id: str) -> list[str]:
    """Returns a list of volume ids attached to the instance.

    Args:
        instance_id: The instance ID to get volumes for

    Returns:
        List of volume IDs attached to the instance

    Raises:
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    instance_id = validate_instance_id(instance_id)

    try:
        response = get_ec2_client().describe_volumes(
            Filters=[{"Name": "attachment.instance-id", "Values": [instance_id]}]
        )

        # Validate response structure
        validate_aws_response_structure(response, ["Volumes"], "describe_volumes")

        # Safely extract volume IDs
        volume_ids = []
        for volume in response["Volumes"]:
            if "VolumeId" in volume:
                volume_ids.append(volume["VolumeId"])

        return volume_ids

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_volumes", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "EC2", "describe_volumes", "NoCredentials", "AWS credentials not found or invalid"
        )


def get_volume_name(volume_id: str) -> str:
    """Returns the name of the volume.

    Args:
        volume_id: The volume ID to get name for

    Returns:
        The volume name from tags, or empty string if no name tag

    Raises:
        ResourceNotFoundError: If volume not found
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    volume_id = validate_volume_id(volume_id)

    try:
        response = get_ec2_client().describe_volumes(VolumeIds=[volume_id])

        # Validate response structure
        validate_aws_response_structure(response, ["Volumes"], "describe_volumes")

        volumes = ensure_non_empty_array(list(response["Volumes"]), "volumes")
        volume = volumes[0]

        # Look for Name tag
        for tag in volume.get("Tags", []):
            if tag["Key"] == "Name":
                return str(tag["Value"])

        return ""  # No name tag found

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "InvalidVolumeID.NotFound":
            raise ResourceNotFoundError("Volume", volume_id)

        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_volumes", error_code, error_message)


def get_snapshot_status(snapshot_id: str) -> str:
    """Returns the status of the snapshot.

    Args:
        snapshot_id: The snapshot ID to get status for

    Returns:
        The snapshot status (e.g., 'pending', 'completed', 'error')

    Raises:
        ResourceNotFoundError: If snapshot not found
        AWSServiceError: If AWS API call fails
    """
    # Validate input
    snapshot_id = validate_snapshot_id(snapshot_id)

    try:
        response = get_ec2_client().describe_snapshots(SnapshotIds=[snapshot_id])

        # Validate response structure
        validate_aws_response_structure(response, ["Snapshots"], "describe_snapshots")

        snapshots = ensure_non_empty_array(list(response["Snapshots"]), "snapshots")

        return str(snapshots[0]["State"])

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "InvalidSnapshotID.NotFound":
            raise ResourceNotFoundError("Snapshot", snapshot_id)

        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_snapshots", error_code, error_message)


def get_launch_templates(name_filter: str | None = None) -> list[dict[str, Any]]:
    """Get launch templates, optionally filtered by name pattern.

    Args:
        name_filter: Optional string to filter templates by name (case-insensitive)

    Returns:
        List of launch template dictionaries

    Raises:
        AWSServiceError: If AWS API call fails
    """
    try:
        response = get_ec2_client().describe_launch_templates()
        validate_aws_response_structure(response, ["LaunchTemplates"], "describe_launch_templates")

        templates = response["LaunchTemplates"]

        if name_filter:
            templates = [
                t for t in templates if name_filter.lower() in t["LaunchTemplateName"].lower()
            ]

        return cast(list[dict[str, Any]], templates)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_launch_templates", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "EC2",
            "describe_launch_templates",
            "NoCredentials",
            "AWS credentials not found or invalid",
        )


def get_launch_template_versions(template_name: str) -> list[dict[str, Any]]:
    """Get all versions of a launch template.

    Args:
        template_name: Name of the launch template

    Returns:
        List of launch template version dictionaries

    Raises:
        ResourceNotFoundError: If template not found
        AWSServiceError: If AWS API call fails
    """
    try:
        response = get_ec2_client().describe_launch_template_versions(
            LaunchTemplateName=template_name
        )
        validate_aws_response_structure(
            response, ["LaunchTemplateVersions"], "describe_launch_template_versions"
        )
        return cast(list[dict[str, Any]], response["LaunchTemplateVersions"])

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "InvalidLaunchTemplateName.NotFoundException":
            raise ResourceNotFoundError("Launch Template", template_name)
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_launch_template_versions", error_code, error_message)
    except NoCredentialsError:
        raise AWSServiceError(
            "EC2",
            "describe_launch_template_versions",
            "NoCredentials",
            "AWS credentials not found or invalid",
        )


def get_launch_template_id(launch_template_name: str) -> str:
    """Get the launch template ID corresponding to a given launch template name.

    This function queries AWS EC2 to get details of all launch templates with the specified name.
    It then retrieves and returns the ID of the first matching launch template.

    Args:
        launch_template_name: The name of the launch template

    Returns:
        The ID of the launch template

    Raises:
        ResourceNotFoundError: If no launch template found with the given name
        AWSServiceError: If AWS API call fails

    Example usage:
        template_id = get_launch_template_id("my-template-name")
    """
    # Validate input
    if not launch_template_name or not launch_template_name.strip():
        raise ValidationError("Launch template name cannot be empty")

    try:
        response = get_ec2_client().describe_launch_templates(
            Filters=[{"Name": "tag:Name", "Values": [launch_template_name]}]
        )

        # Validate response structure
        validate_aws_response_structure(response, ["LaunchTemplates"], "describe_launch_templates")

        launch_templates = response["LaunchTemplates"]
        if not launch_templates:
            raise ResourceNotFoundError("Launch Template", launch_template_name)

        return launch_templates[0]["LaunchTemplateId"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise AWSServiceError("EC2", "describe_launch_templates", error_code, error_message)


def parse_duration_to_minutes(duration_str: str) -> int:
    """Parse duration string like '3h', '30m', '1h30m' into minutes.

    Args:
        duration_str: A duration string in format like '3h', '30m', '1h30m', '2h15m'

    Returns:
        Total duration in minutes

    Raises:
        ValidationError: If the duration format is invalid or results in 0 minutes
    """
    if not duration_str or not duration_str.strip():
        raise ValidationError("Duration cannot be empty")

    duration_str = duration_str.strip().lower()

    # Pattern matches: optional hours (Nh) followed by optional minutes (Nm)
    pattern = r"^(?:(\d+)h)?(?:(\d+)m)?$"
    match = re.fullmatch(pattern, duration_str)

    if not match or not any(match.groups()):
        raise ValidationError(
            f"Invalid duration format: '{duration_str}'. Use formats like '3h', '30m', or '1h30m'"
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)

    total_minutes = hours * 60 + minutes

    if total_minutes <= 0:
        raise ValidationError("Duration must be greater than 0 minutes")

    return total_minutes


def format_duration(minutes: int) -> str:
    """Format minutes into a human-readable duration string.

    Args:
        minutes: Total duration in minutes

    Returns:
        Human-readable string like '2h 30m' or '45m'
    """
    if minutes <= 0:
        return "0m"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours > 0 and remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{remaining_minutes}m"
