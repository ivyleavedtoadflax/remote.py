"""Tests for EventBridge Scheduler functionality.

These tests cover:
- IAM role creation and management
- Schedule creation, retrieval, deletion, and listing
"""

import json

import pytest
from botocore.exceptions import ClientError

from remote.exceptions import AWSServiceError

# ============================================================================
# IAM Role Management Tests
# ============================================================================


class TestEnsureSchedulerRole:
    """Tests for ensure_scheduler_role function."""

    def test_should_return_existing_role_arn(self, mocker):
        """Should return existing role ARN if role already exists."""
        from remote.scheduler import ensure_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.return_value = {
            "Role": {
                "RoleName": "remotepy-scheduler-role",
                "Arn": "arn:aws:iam::123456789012:role/remotepy-scheduler-role",
            }
        }

        result = ensure_scheduler_role()

        assert result == "arn:aws:iam::123456789012:role/remotepy-scheduler-role"
        mock_iam.return_value.get_role.assert_called_once_with(RoleName="remotepy-scheduler-role")
        # Should not attempt to create
        mock_iam.return_value.create_role.assert_not_called()

    def test_should_create_role_if_not_exists(self, mocker):
        """Should create role if it doesn't exist."""
        from remote.scheduler import ensure_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole",
        )
        mock_iam.return_value.create_role.return_value = {
            "Role": {
                "RoleName": "remotepy-scheduler-role",
                "Arn": "arn:aws:iam::123456789012:role/remotepy-scheduler-role",
            }
        }

        result = ensure_scheduler_role()

        assert result == "arn:aws:iam::123456789012:role/remotepy-scheduler-role"
        mock_iam.return_value.create_role.assert_called_once()
        mock_iam.return_value.put_role_policy.assert_called_once()

    def test_should_create_role_with_correct_trust_policy(self, mocker):
        """Should create role with correct trust policy for EventBridge Scheduler."""
        from remote.scheduler import ensure_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole",
        )
        mock_iam.return_value.create_role.return_value = {
            "Role": {
                "RoleName": "remotepy-scheduler-role",
                "Arn": "arn:aws:iam::123456789012:role/remotepy-scheduler-role",
            }
        }

        ensure_scheduler_role()

        create_call = mock_iam.return_value.create_role.call_args
        trust_policy = json.loads(create_call[1]["AssumeRolePolicyDocument"])

        assert trust_policy["Version"] == "2012-10-17"
        assert len(trust_policy["Statement"]) == 1
        assert trust_policy["Statement"][0]["Effect"] == "Allow"
        assert trust_policy["Statement"][0]["Principal"]["Service"] == "scheduler.amazonaws.com"
        assert trust_policy["Statement"][0]["Action"] == "sts:AssumeRole"

    def test_should_create_role_with_ec2_permissions(self, mocker):
        """Should create inline policy allowing EC2 start/stop."""
        from remote.scheduler import ensure_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole",
        )
        mock_iam.return_value.create_role.return_value = {
            "Role": {
                "RoleName": "remotepy-scheduler-role",
                "Arn": "arn:aws:iam::123456789012:role/remotepy-scheduler-role",
            }
        }

        ensure_scheduler_role()

        policy_call = mock_iam.return_value.put_role_policy.call_args
        policy_doc = json.loads(policy_call[1]["PolicyDocument"])

        assert "ec2:StartInstances" in policy_doc["Statement"][0]["Action"]
        assert "ec2:StopInstances" in policy_doc["Statement"][0]["Action"]

    def test_should_reraise_aws_errors_other_than_not_found(self, mocker):
        """Should re-raise AWS errors other than NoSuchEntity."""
        from remote.scheduler import ensure_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetRole",
        )

        with pytest.raises(AWSServiceError) as exc_info:
            ensure_scheduler_role()

        assert exc_info.value.aws_error_code == "AccessDenied"


class TestDeleteSchedulerRole:
    """Tests for delete_scheduler_role function."""

    def test_should_delete_role_if_exists(self, mocker):
        """Should delete role and its inline policy."""
        from remote.scheduler import delete_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.return_value = {
            "Role": {"RoleName": "remotepy-scheduler-role"}
        }

        result = delete_scheduler_role()

        assert result is True
        mock_iam.return_value.delete_role_policy.assert_called_once_with(
            RoleName="remotepy-scheduler-role",
            PolicyName="remotepy-scheduler-ec2-policy",
        )
        mock_iam.return_value.delete_role.assert_called_once_with(
            RoleName="remotepy-scheduler-role"
        )

    def test_should_return_false_if_role_not_exists(self, mocker):
        """Should return False if role doesn't exist."""
        from remote.scheduler import delete_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole",
        )

        result = delete_scheduler_role()

        assert result is False
        mock_iam.return_value.delete_role.assert_not_called()

    def test_should_handle_missing_policy_gracefully(self, mocker):
        """Should handle case where inline policy doesn't exist."""
        from remote.scheduler import delete_scheduler_role

        mock_iam = mocker.patch("remote.scheduler.get_iam_client")
        mock_iam.return_value.get_role.return_value = {
            "Role": {"RoleName": "remotepy-scheduler-role"}
        }
        mock_iam.return_value.delete_role_policy.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Policy not found"}},
            "DeleteRolePolicy",
        )

        result = delete_scheduler_role()

        assert result is True
        mock_iam.return_value.delete_role.assert_called_once()


# ============================================================================
# Schedule CRUD Tests
# ============================================================================


class TestCreateSchedule:
    """Tests for create_schedule function."""

    def test_should_create_wake_schedule(self, mocker):
        """Should create a schedule to start an instance."""
        from remote.scheduler import create_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.ensure_scheduler_role",
            return_value="arn:aws:iam::123456789012:role/remotepy-scheduler-role",
        )

        create_schedule(
            instance_id="i-0123456789abcdef0",
            action="wake",
            schedule_expression="cron(0 9 ? * MON,TUE,WED,THU,FRI *)",
            timezone="America/New_York",
        )

        mock_scheduler.return_value.create_schedule.assert_called_once()
        call_kwargs = mock_scheduler.return_value.create_schedule.call_args[1]

        assert call_kwargs["Name"] == "remotepy-wake-i-0123456789abcdef0"
        assert call_kwargs["ScheduleExpression"] == "cron(0 9 ? * MON,TUE,WED,THU,FRI *)"
        assert call_kwargs["ScheduleExpressionTimezone"] == "America/New_York"
        assert "startinstances" in call_kwargs["Target"]["Arn"].lower()

    def test_should_create_sleep_schedule(self, mocker):
        """Should create a schedule to stop an instance."""
        from remote.scheduler import create_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.ensure_scheduler_role",
            return_value="arn:aws:iam::123456789012:role/remotepy-scheduler-role",
        )

        create_schedule(
            instance_id="i-0123456789abcdef0",
            action="sleep",
            schedule_expression="cron(0 18 ? * MON,TUE,WED,THU,FRI *)",
            timezone="UTC",
        )

        call_kwargs = mock_scheduler.return_value.create_schedule.call_args[1]

        assert call_kwargs["Name"] == "remotepy-sleep-i-0123456789abcdef0"
        assert "stopinstances" in call_kwargs["Target"]["Arn"].lower()

    def test_should_use_utc_as_default_timezone(self, mocker):
        """Should use UTC when no timezone is specified."""
        from remote.scheduler import create_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.ensure_scheduler_role",
            return_value="arn:aws:iam::123456789012:role/remotepy-scheduler-role",
        )

        create_schedule(
            instance_id="i-0123456789abcdef0",
            action="wake",
            schedule_expression="cron(0 9 ? * MON *)",
        )

        call_kwargs = mock_scheduler.return_value.create_schedule.call_args[1]
        assert call_kwargs["ScheduleExpressionTimezone"] == "UTC"

    def test_should_update_existing_schedule(self, mocker):
        """Should use update_schedule when schedule already exists."""
        from remote.scheduler import create_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mock_scheduler.return_value.create_schedule.side_effect = ClientError(
            {"Error": {"Code": "ConflictException", "Message": "Schedule exists"}},
            "CreateSchedule",
        )
        mocker.patch(
            "remote.scheduler.ensure_scheduler_role",
            return_value="arn:aws:iam::123456789012:role/remotepy-scheduler-role",
        )

        create_schedule(
            instance_id="i-0123456789abcdef0",
            action="wake",
            schedule_expression="cron(0 9 ? * MON *)",
        )

        mock_scheduler.return_value.update_schedule.assert_called_once()


class TestGetSchedule:
    """Tests for get_schedule function."""

    def test_should_return_schedule_if_exists(self, mocker):
        """Should return schedule details when schedule exists."""
        from remote.scheduler import get_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mock_scheduler.return_value.get_schedule.return_value = {
            "Name": "remotepy-wake-i-123",
            "ScheduleExpression": "cron(0 9 ? * MON *)",
            "ScheduleExpressionTimezone": "UTC",
            "State": "ENABLED",
        }

        result = get_schedule("i-123", "wake")

        assert result is not None
        assert result["Name"] == "remotepy-wake-i-123"
        mock_scheduler.return_value.get_schedule.assert_called_once_with(Name="remotepy-wake-i-123")

    def test_should_return_none_if_not_exists(self, mocker):
        """Should return None when schedule doesn't exist."""
        from remote.scheduler import get_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mock_scheduler.return_value.get_schedule.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetSchedule",
        )

        result = get_schedule("i-123", "wake")

        assert result is None


class TestDeleteSchedule:
    """Tests for delete_schedule function."""

    def test_should_delete_existing_schedule(self, mocker):
        """Should delete schedule and return True."""
        from remote.scheduler import delete_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")

        result = delete_schedule("i-123", "wake")

        assert result is True
        mock_scheduler.return_value.delete_schedule.assert_called_once_with(
            Name="remotepy-wake-i-123"
        )

    def test_should_return_false_if_not_exists(self, mocker):
        """Should return False if schedule doesn't exist."""
        from remote.scheduler import delete_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mock_scheduler.return_value.delete_schedule.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DeleteSchedule",
        )

        result = delete_schedule("i-123", "wake")

        assert result is False


class TestListSchedules:
    """Tests for list_schedules function."""

    def test_should_list_all_remotepy_schedules(self, mocker):
        """Should list all schedules with remotepy- prefix."""
        from remote.scheduler import list_schedules

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mock_scheduler.return_value.list_schedules.return_value = {
            "Schedules": [
                {"Name": "remotepy-wake-i-123", "State": "ENABLED"},
                {"Name": "remotepy-sleep-i-123", "State": "ENABLED"},
                {"Name": "remotepy-wake-i-456", "State": "DISABLED"},
            ]
        }

        result = list_schedules()

        assert len(result) == 3
        mock_scheduler.return_value.list_schedules.assert_called_once_with(NamePrefix="remotepy-")

    def test_should_return_empty_list_if_none_exist(self, mocker):
        """Should return empty list when no schedules exist."""
        from remote.scheduler import list_schedules

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mock_scheduler.return_value.list_schedules.return_value = {"Schedules": []}

        result = list_schedules()

        assert result == []


class TestDeleteAllSchedulesForInstance:
    """Tests for delete_all_schedules_for_instance function."""

    def test_should_delete_both_wake_and_sleep_schedules(self, mocker):
        """Should delete both wake and sleep schedules for an instance."""
        from remote.scheduler import delete_all_schedules_for_instance

        mock_delete = mocker.patch("remote.scheduler.delete_schedule", return_value=True)

        result = delete_all_schedules_for_instance("i-123")

        assert result == {"wake": True, "sleep": True}
        assert mock_delete.call_count == 2
        mock_delete.assert_any_call("i-123", "wake")
        mock_delete.assert_any_call("i-123", "sleep")

    def test_should_report_deletion_results(self, mocker):
        """Should report which schedules were deleted."""
        from remote.scheduler import delete_all_schedules_for_instance

        mock_delete = mocker.patch("remote.scheduler.delete_schedule")
        mock_delete.side_effect = [True, False]  # wake deleted, sleep didn't exist

        result = delete_all_schedules_for_instance("i-123")

        assert result == {"wake": True, "sleep": False}


class TestGetSchedulesForInstance:
    """Tests for get_schedules_for_instance function."""

    def test_should_get_both_schedules(self, mocker):
        """Should get both wake and sleep schedules for an instance."""
        from remote.scheduler import get_schedules_for_instance

        mock_get = mocker.patch("remote.scheduler.get_schedule")
        mock_get.side_effect = [
            {"Name": "remotepy-wake-i-123", "State": "ENABLED"},
            {"Name": "remotepy-sleep-i-123", "State": "ENABLED"},
        ]

        result = get_schedules_for_instance("i-123")

        assert "wake" in result
        assert "sleep" in result
        assert result["wake"]["Name"] == "remotepy-wake-i-123"

    def test_should_handle_missing_schedules(self, mocker):
        """Should return None for schedules that don't exist."""
        from remote.scheduler import get_schedules_for_instance

        mock_get = mocker.patch("remote.scheduler.get_schedule")
        mock_get.side_effect = [
            {"Name": "remotepy-wake-i-123", "State": "ENABLED"},
            None,  # No sleep schedule
        ]

        result = get_schedules_for_instance("i-123")

        assert result["wake"] is not None
        assert result["sleep"] is None


class TestScheduleNaming:
    """Tests for schedule naming conventions."""

    def test_schedule_name_pattern(self, mocker):
        """Should follow naming pattern: remotepy-{action}-{instance_id}."""
        from remote.scheduler import create_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.ensure_scheduler_role",
            return_value="arn:aws:iam::123456789012:role/remotepy-scheduler-role",
        )

        create_schedule(
            instance_id="i-0123456789abcdef0",
            action="wake",
            schedule_expression="cron(0 9 ? * MON *)",
        )

        call_kwargs = mock_scheduler.return_value.create_schedule.call_args[1]
        # Name should be: remotepy-wake-i-0123456789abcdef0
        assert call_kwargs["Name"].startswith("remotepy-")
        assert "wake" in call_kwargs["Name"]
        assert "i-0123456789abcdef0" in call_kwargs["Name"]
