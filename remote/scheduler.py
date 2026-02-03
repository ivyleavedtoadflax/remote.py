"""EventBridge Scheduler management for EC2 instance wake/sleep schedules.

This module provides functions for creating and managing EventBridge Scheduler
schedules to automatically start and stop EC2 instances on a recurring basis.
"""

import json
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


def _get_schedule_name(instance_id: str, action: Literal["wake", "sleep"]) -> str:
    """Build the schedule name for an instance and action."""
    return f"{SCHEDULE_NAME_PREFIX}{action}-{instance_id}"


def create_schedule(
    instance_id: str,
    action: Literal["wake", "sleep"],
    schedule_expression: str,
    timezone: str | None = None,
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

    Raises:
        AWSServiceError: If scheduler operations fail
    """
    scheduler = get_scheduler_client()
    role_arn = ensure_scheduler_role()

    schedule_name = _get_schedule_name(instance_id, action)

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


def get_schedule(instance_id: str, action: Literal["wake", "sleep"]) -> dict[str, Any] | None:
    """Get a schedule for an instance if it exists.

    Args:
        instance_id: EC2 instance ID
        action: "wake" or "sleep"

    Returns:
        Schedule details dict or None if not found
    """
    scheduler = get_scheduler_client()
    schedule_name = _get_schedule_name(instance_id, action)

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


def delete_schedule(instance_id: str, action: Literal["wake", "sleep"]) -> bool:
    """Delete a schedule for an instance.

    Args:
        instance_id: EC2 instance ID
        action: "wake" or "sleep"

    Returns:
        True if schedule was deleted, False if it didn't exist
    """
    scheduler = get_scheduler_client()
    schedule_name = _get_schedule_name(instance_id, action)

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


def get_schedules_for_instance(
    instance_id: str,
) -> dict[str, dict[str, Any] | None]:
    """Get both wake and sleep schedules for an instance.

    Args:
        instance_id: EC2 instance ID

    Returns:
        Dict with "wake" and "sleep" keys, each containing schedule dict or None
    """
    return {
        "wake": get_schedule(instance_id, "wake"),
        "sleep": get_schedule(instance_id, "sleep"),
    }


def delete_all_schedules_for_instance(instance_id: str) -> dict[str, bool]:
    """Delete both wake and sleep schedules for an instance.

    Args:
        instance_id: EC2 instance ID

    Returns:
        Dict with "wake" and "sleep" keys, each True if deleted, False if didn't exist
    """
    return {
        "wake": delete_schedule(instance_id, "wake"),
        "sleep": delete_schedule(instance_id, "sleep"),
    }
