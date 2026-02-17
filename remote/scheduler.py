"""EventBridge Scheduler management for EC2 instance wake/sleep schedules.

This module provides functions for creating and managing EventBridge Scheduler
schedules to automatically start and stop EC2 instances on a recurring basis.
"""

import json
import re
from typing import Any, Literal, cast

from botocore.exceptions import ClientError, NoCredentialsError

from .exceptions import AWSServiceError
from .utils import get_iam_client, get_scheduler_client

# Constants
SCHEDULER_ROLE_NAME = "remotepy-scheduler-role"
SCHEDULER_POLICY_NAME = "remotepy-scheduler-ec2-policy"
SCHEDULE_NAME_PREFIX = "remotepy-"


def _build_trust_policy() -> str:
    """Build the trust policy document for the scheduler role."""
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "scheduler.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    return json.dumps(trust_policy)


def _build_ec2_policy() -> str:
    """Build the EC2 permissions policy for start/stop instances."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["ec2:StartInstances", "ec2:StopInstances"],
                "Resource": "*",
            }
        ],
    }
    return json.dumps(policy)


def ensure_scheduler_role() -> str:
    """Ensure the scheduler IAM role exists, creating it if necessary.

    Returns:
        The ARN of the scheduler role

    Raises:
        AWSServiceError: If IAM operations fail
    """
    iam = get_iam_client()

    try:
        response = iam.get_role(RoleName=SCHEDULER_ROLE_NAME)
        return response["Role"]["Arn"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise AWSServiceError(
                service="IAM",
                operation="get_role",
                aws_error_code=e.response["Error"]["Code"],
                message=e.response["Error"]["Message"],
            )
    except NoCredentialsError:
        raise AWSServiceError(
            service="IAM",
            operation="get_role",
            aws_error_code="NoCredentials",
            message="No AWS credentials found",
        )

    # Role doesn't exist, create it
    try:
        response = iam.create_role(
            RoleName=SCHEDULER_ROLE_NAME,
            AssumeRolePolicyDocument=_build_trust_policy(),
            Description="Role for RemotePy EventBridge Scheduler to start/stop EC2 instances",
        )
        role_arn = response["Role"]["Arn"]

        # Add inline policy for EC2 permissions
        iam.put_role_policy(
            RoleName=SCHEDULER_ROLE_NAME,
            PolicyName=SCHEDULER_POLICY_NAME,
            PolicyDocument=_build_ec2_policy(),
        )

        return role_arn
    except ClientError as e:
        raise AWSServiceError(
            service="IAM",
            operation="create_role",
            aws_error_code=e.response["Error"]["Code"],
            message=e.response["Error"]["Message"],
        )
    except NoCredentialsError:
        raise AWSServiceError(
            service="IAM",
            operation="create_role",
            aws_error_code="NoCredentials",
            message="No AWS credentials found",
        )


def delete_scheduler_role() -> bool:
    """Delete the scheduler IAM role if it exists.

    Returns:
        True if role was deleted, False if it didn't exist
    """
    iam = get_iam_client()

    try:
        iam.get_role(RoleName=SCHEDULER_ROLE_NAME)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            return False
        raise AWSServiceError(
            service="IAM",
            operation="get_role",
            aws_error_code=e.response["Error"]["Code"],
            message=e.response["Error"]["Message"],
        )

    # Delete inline policy first (may not exist)
    try:
        iam.delete_role_policy(
            RoleName=SCHEDULER_ROLE_NAME,
            PolicyName=SCHEDULER_POLICY_NAME,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise AWSServiceError(
                service="IAM",
                operation="delete_role_policy",
                aws_error_code=e.response["Error"]["Code"],
                message=e.response["Error"]["Message"],
            )

    # Delete the role
    try:
        iam.delete_role(RoleName=SCHEDULER_ROLE_NAME)
        return True
    except ClientError as e:
        raise AWSServiceError(
            service="IAM",
            operation="delete_role",
            aws_error_code=e.response["Error"]["Code"],
            message=e.response["Error"]["Message"],
        )


def _get_schedule_name(
    instance_id: str, action: Literal["wake", "sleep"], name: str | None = None
) -> str:
    """Build the schedule name for an instance and action.

    Args:
        instance_id: EC2 instance ID
        action: "wake" or "sleep"
        name: Optional schedule name for multiple schedules per instance
    """
    if name:
        return f"{SCHEDULE_NAME_PREFIX}{action}-{name}-{instance_id}"
    return f"{SCHEDULE_NAME_PREFIX}{action}-{instance_id}"


def parse_schedule_name(schedule_name: str) -> dict[str, str | None] | None:
    """Parse schedule name into components.

    Handles both named and unnamed formats:
    - Named: "remotepy-wake-morning-i-0123456789abcdef0"
    - Unnamed: "remotepy-wake-i-0123456789abcdef0"

    Args:
        schedule_name: The full schedule name

    Returns:
        Dict with "action", "name" (or None), and "instance_id" keys,
        or None if the name doesn't match expected patterns.
    """
    # Try named format first: remotepy-{action}-{name}-{instance_id}
    named_match = re.match(r"^remotepy-(wake|sleep)-(.+)-(i-[0-9a-f]+)$", schedule_name)
    if named_match:
        return {
            "action": named_match.group(1),
            "name": named_match.group(2),
            "instance_id": named_match.group(3),
        }

    # Try unnamed format: remotepy-{action}-{instance_id}
    unnamed_match = re.match(r"^remotepy-(wake|sleep)-(i-[0-9a-f]+)$", schedule_name)
    if unnamed_match:
        return {
            "action": unnamed_match.group(1),
            "name": None,
            "instance_id": unnamed_match.group(2),
        }

    return None


def create_schedule(
    instance_id: str,
    action: Literal["wake", "sleep"],
    schedule_expression: str,
    timezone: str | None = None,
    name: str | None = None,
) -> None:
    """Create or update an EventBridge schedule for an instance.

    Args:
        instance_id: EC2 instance ID
        action: "wake" to start or "sleep" to stop the instance
        schedule_expression: EventBridge schedule expression - either:
            - cron() for recurring schedules (e.g., "cron(0 9 ? * MON-FRI *)")
            - at() for one-time schedules (e.g., "at(2026-02-15T09:00:00)")
        timezone: IANA timezone (defaults to UTC). Only used for cron() expressions;
            at() expressions include their own timestamp.
        name: Optional schedule name for multiple schedules per instance

    Raises:
        AWSServiceError: If scheduler operations fail
    """
    scheduler = get_scheduler_client()
    role_arn = ensure_scheduler_role()

    schedule_name = _get_schedule_name(instance_id, action, name)

    # Determine the EC2 API action (camelCase required for SDK target)
    ec2_action = "startInstances" if action == "wake" else "stopInstances"
    target_arn = f"arn:aws:scheduler:::aws-sdk:ec2:{ec2_action}"

    # Build schedule params - timezone only applies to cron expressions
    is_one_time = schedule_expression.startswith("at(")
    schedule_params: dict[str, Any] = {
        "Name": schedule_name,
        "ScheduleExpression": schedule_expression,
        "FlexibleTimeWindow": {"Mode": "OFF"},
        "Target": {
            "Arn": target_arn,
            "RoleArn": role_arn,
            "Input": json.dumps({"InstanceIds": [instance_id]}),
        },
        "State": "ENABLED",
        "Description": f"RemotePy {action} schedule for instance {instance_id}",
    }

    # Add timezone for recurring schedules only
    if not is_one_time:
        schedule_params["ScheduleExpressionTimezone"] = timezone or "UTC"

    try:
        scheduler.create_schedule(**schedule_params)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            # Schedule already exists, update it instead
            try:
                scheduler.update_schedule(**schedule_params)
            except ClientError as update_error:
                raise AWSServiceError(
                    service="EventBridge Scheduler",
                    operation="update_schedule",
                    aws_error_code=update_error.response["Error"]["Code"],
                    message=update_error.response["Error"]["Message"],
                )
        else:
            raise AWSServiceError(
                service="EventBridge Scheduler",
                operation="create_schedule",
                aws_error_code=e.response["Error"]["Code"],
                message=e.response["Error"]["Message"],
            )
    except NoCredentialsError:
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="create_schedule",
            aws_error_code="NoCredentials",
            message="No AWS credentials found",
        )


def get_schedule(
    instance_id: str, action: Literal["wake", "sleep"], name: str | None = None
) -> dict[str, Any] | None:
    """Get a schedule for an instance if it exists.

    Args:
        instance_id: EC2 instance ID
        action: "wake" or "sleep"
        name: Optional schedule name for named schedules

    Returns:
        Schedule details dict or None if not found
    """
    scheduler = get_scheduler_client()
    schedule_name = _get_schedule_name(instance_id, action, name)

    try:
        return cast(dict[str, Any], scheduler.get_schedule(Name=schedule_name))
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return None
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="get_schedule",
            aws_error_code=e.response["Error"]["Code"],
            message=e.response["Error"]["Message"],
        )
    except NoCredentialsError:
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="get_schedule",
            aws_error_code="NoCredentials",
            message="No AWS credentials found",
        )


def delete_schedule(
    instance_id: str, action: Literal["wake", "sleep"], name: str | None = None
) -> bool:
    """Delete a schedule for an instance.

    Args:
        instance_id: EC2 instance ID
        action: "wake" or "sleep"
        name: Optional schedule name for named schedules

    Returns:
        True if schedule was deleted, False if it didn't exist
    """
    scheduler = get_scheduler_client()
    schedule_name = _get_schedule_name(instance_id, action, name)

    try:
        scheduler.delete_schedule(Name=schedule_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="delete_schedule",
            aws_error_code=e.response["Error"]["Code"],
            message=e.response["Error"]["Message"],
        )
    except NoCredentialsError:
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="delete_schedule",
            aws_error_code="NoCredentials",
            message="No AWS credentials found",
        )


def list_schedules() -> list[dict[str, Any]]:
    """List all remotepy schedules.

    Returns:
        List of schedule summary dicts
    """
    scheduler = get_scheduler_client()

    try:
        response = scheduler.list_schedules(NamePrefix=SCHEDULE_NAME_PREFIX)
        return cast(list[dict[str, Any]], response.get("Schedules", []))
    except ClientError as e:
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="list_schedules",
            aws_error_code=e.response["Error"]["Code"],
            message=e.response["Error"]["Message"],
        )
    except NoCredentialsError:
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="list_schedules",
            aws_error_code="NoCredentials",
            message="No AWS credentials found",
        )


def _get_schedule_by_name(schedule_name: str) -> dict[str, Any] | None:
    """Get a schedule by its exact name.

    Args:
        schedule_name: The full schedule name

    Returns:
        Schedule details dict or None if not found
    """
    scheduler = get_scheduler_client()

    try:
        return cast(dict[str, Any], scheduler.get_schedule(Name=schedule_name))
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return None
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="get_schedule",
            aws_error_code=e.response["Error"]["Code"],
            message=e.response["Error"]["Message"],
        )
    except NoCredentialsError:
        raise AWSServiceError(
            service="EventBridge Scheduler",
            operation="get_schedule",
            aws_error_code="NoCredentials",
            message="No AWS credentials found",
        )


def get_schedules_for_instance(instance_id: str) -> list[dict[str, Any]]:
    """Get all schedules for an instance (named and unnamed).

    Uses list_schedules() with prefix filter, then fetches full details
    for each matching schedule.

    Args:
        instance_id: EC2 instance ID

    Returns:
        List of schedule dicts, each with full details plus parsed
        "schedule_name", "action", and "name" keys.
    """
    all_schedules = list_schedules()

    results: list[dict[str, Any]] = []
    for sched in all_schedules:
        sched_name = sched.get("Name", "")
        parsed = parse_schedule_name(sched_name)
        if not parsed or parsed["instance_id"] != instance_id:
            continue

        # Fetch full details
        full = _get_schedule_by_name(sched_name)
        if full:
            full["schedule_name"] = sched_name
            full["action"] = parsed["action"]
            full["parsed_name"] = parsed["name"]
            results.append(full)

    return results


def delete_all_schedules_for_instance(instance_id: str) -> int:
    """Delete all schedules for an instance (named and unnamed).

    Discovers schedules via list_schedules() + filter, then deletes each.

    Args:
        instance_id: EC2 instance ID

    Returns:
        Count of deleted schedules
    """
    scheduler = get_scheduler_client()
    all_schedules = list_schedules()

    deleted = 0
    for sched in all_schedules:
        sched_name = sched.get("Name", "")
        parsed = parse_schedule_name(sched_name)
        if not parsed or parsed["instance_id"] != instance_id:
            continue

        try:
            scheduler.delete_schedule(Name=sched_name)
            deleted += 1
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                raise AWSServiceError(
                    service="EventBridge Scheduler",
                    operation="delete_schedule",
                    aws_error_code=e.response["Error"]["Code"],
                    message=e.response["Error"]["Message"],
                )

    return deleted
