"""Tests for EventBridge Scheduler functionality.

These tests cover:
- IAM role creation and management
- Schedule creation, retrieval, deletion, and listing
- Schedule name parsing
- Named schedule support
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

    def test_should_create_named_wake_schedule(self, mocker):
        """Should create a named schedule with correct name format."""
        from remote.scheduler import create_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.ensure_scheduler_role",
            return_value="arn:aws:iam::123456789012:role/remotepy-scheduler-role",
        )

        create_schedule(
            instance_id="i-0123456789abcdef0",
            action="wake",
            schedule_expression="cron(0 8 ? * MON,TUE,WED,THU,FRI *)",
            timezone="UTC",
            name="morning",
        )

        call_kwargs = mock_scheduler.return_value.create_schedule.call_args[1]
        assert call_kwargs["Name"] == "remotepy-wake-morning-i-0123456789abcdef0"

    def test_should_create_named_sleep_schedule(self, mocker):
        """Should create a named sleep schedule with correct name format."""
        from remote.scheduler import create_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.ensure_scheduler_role",
            return_value="arn:aws:iam::123456789012:role/remotepy-scheduler-role",
        )

        create_schedule(
            instance_id="i-0123456789abcdef0",
            action="sleep",
            schedule_expression="cron(0 23 ? * MON,TUE,WED,THU,FRI *)",
            timezone="UTC",
            name="evening",
        )

        call_kwargs = mock_scheduler.return_value.create_schedule.call_args[1]
        assert call_kwargs["Name"] == "remotepy-sleep-evening-i-0123456789abcdef0"


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

    def test_should_get_named_schedule(self, mocker):
        """Should get a named schedule with correct name format."""
        from remote.scheduler import get_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mock_scheduler.return_value.get_schedule.return_value = {
            "Name": "remotepy-wake-morning-i-123",
            "ScheduleExpression": "cron(0 8 ? * MON *)",
            "State": "ENABLED",
        }

        result = get_schedule("i-123", "wake", name="morning")

        assert result is not None
        mock_scheduler.return_value.get_schedule.assert_called_once_with(
            Name="remotepy-wake-morning-i-123"
        )


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

    def test_should_delete_named_schedule(self, mocker):
        """Should delete a named schedule with correct name format."""
        from remote.scheduler import delete_schedule

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")

        result = delete_schedule("i-123", "wake", name="morning")

        assert result is True
        mock_scheduler.return_value.delete_schedule.assert_called_once_with(
            Name="remotepy-wake-morning-i-123"
        )


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

    def test_should_delete_all_schedules_for_instance(self, mocker):
        """Should delete all schedules matching the instance ID."""
        from remote.scheduler import delete_all_schedules_for_instance

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.list_schedules",
            return_value=[
                {"Name": "remotepy-wake-i-123"},
                {"Name": "remotepy-sleep-i-123"},
                {"Name": "remotepy-wake-morning-i-123"},
                {"Name": "remotepy-wake-i-456"},  # different instance
            ],
        )

        result = delete_all_schedules_for_instance("i-123")

        assert result == 3
        assert mock_scheduler.return_value.delete_schedule.call_count == 3

    def test_should_return_zero_when_no_schedules(self, mocker):
        """Should return 0 when no schedules exist for instance."""
        mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch("remote.scheduler.list_schedules", return_value=[])

        from remote.scheduler import delete_all_schedules_for_instance

        result = delete_all_schedules_for_instance("i-123")

        assert result == 0

    def test_should_skip_schedules_for_other_instances(self, mocker):
        """Should not delete schedules belonging to other instances."""
        from remote.scheduler import delete_all_schedules_for_instance

        mock_scheduler = mocker.patch("remote.scheduler.get_scheduler_client")
        mocker.patch(
            "remote.scheduler.list_schedules",
            return_value=[
                {"Name": "remotepy-wake-i-456"},
                {"Name": "remotepy-sleep-i-456"},
            ],
        )

        result = delete_all_schedules_for_instance("i-123")

        assert result == 0
        mock_scheduler.return_value.delete_schedule.assert_not_called()


class TestGetSchedulesForInstance:
    """Tests for get_schedules_for_instance function."""

    def test_should_get_all_schedules_for_instance(self, mocker):
        """Should get all schedules (named and unnamed) for an instance."""
        from remote.scheduler import get_schedules_for_instance

        mocker.patch(
            "remote.scheduler.list_schedules",
            return_value=[
                {"Name": "remotepy-wake-i-123"},
                {"Name": "remotepy-sleep-i-123"},
                {"Name": "remotepy-wake-morning-i-123"},
                {"Name": "remotepy-wake-i-456"},  # different instance
            ],
        )
        mocker.patch(
            "remote.scheduler._get_schedule_by_name",
            side_effect=lambda name: {
                "Name": name,
                "ScheduleExpression": "cron(0 9 ? * MON *)",
                "State": "ENABLED",
            },
        )

        result = get_schedules_for_instance("i-123")

        assert len(result) == 3
        actions = [s["action"] for s in result]
        assert "wake" in actions
        assert "sleep" in actions

    def test_should_return_empty_list_when_no_schedules(self, mocker):
        """Should return empty list when no schedules exist."""
        from remote.scheduler import get_schedules_for_instance

        mocker.patch("remote.scheduler.list_schedules", return_value=[])

        result = get_schedules_for_instance("i-123")

        assert result == []

    def test_should_include_parsed_name_for_named_schedules(self, mocker):
        """Should include parsed_name field for named schedules."""
        from remote.scheduler import get_schedules_for_instance

        mocker.patch(
            "remote.scheduler.list_schedules",
            return_value=[
                {"Name": "remotepy-wake-morning-i-123"},
                {"Name": "remotepy-wake-i-123"},
            ],
        )
        mocker.patch(
            "remote.scheduler._get_schedule_by_name",
            side_effect=lambda name: {
                "Name": name,
                "ScheduleExpression": "cron(0 9 ? * MON *)",
                "State": "ENABLED",
            },
        )

        result = get_schedules_for_instance("i-123")

        named = [s for s in result if s["parsed_name"] is not None]
        unnamed = [s for s in result if s["parsed_name"] is None]
        assert len(named) == 1
        assert named[0]["parsed_name"] == "morning"
        assert len(unnamed) == 1


# ============================================================================
# Schedule Name Parsing Tests
# ============================================================================


class TestParseScheduleName:
    """Tests for parse_schedule_name function."""

    def test_should_parse_unnamed_wake_schedule(self):
        """Should parse unnamed wake schedule."""
        from remote.scheduler import parse_schedule_name

        result = parse_schedule_name("remotepy-wake-i-0123456789abcdef0")

        assert result is not None
        assert result["action"] == "wake"
        assert result["name"] is None
        assert result["instance_id"] == "i-0123456789abcdef0"

    def test_should_parse_unnamed_sleep_schedule(self):
        """Should parse unnamed sleep schedule."""
        from remote.scheduler import parse_schedule_name

        result = parse_schedule_name("remotepy-sleep-i-0123456789abcdef0")

        assert result is not None
        assert result["action"] == "sleep"
        assert result["name"] is None
        assert result["instance_id"] == "i-0123456789abcdef0"

    def test_should_parse_named_wake_schedule(self):
        """Should parse named wake schedule."""
        from remote.scheduler import parse_schedule_name

        result = parse_schedule_name("remotepy-wake-morning-i-0123456789abcdef0")

        assert result is not None
        assert result["action"] == "wake"
        assert result["name"] == "morning"
        assert result["instance_id"] == "i-0123456789abcdef0"

    def test_should_parse_named_sleep_schedule(self):
        """Should parse named sleep schedule."""
        from remote.scheduler import parse_schedule_name

        result = parse_schedule_name("remotepy-sleep-evening-i-0123456789abcdef0")

        assert result is not None
        assert result["action"] == "sleep"
        assert result["name"] == "evening"
        assert result["instance_id"] == "i-0123456789abcdef0"

    def test_should_parse_hyphenated_name(self):
        """Should parse schedule name with hyphens in the name part."""
        from remote.scheduler import parse_schedule_name

        result = parse_schedule_name("remotepy-wake-my-sync-i-0123456789abcdef0")

        assert result is not None
        assert result["action"] == "wake"
        assert result["name"] == "my-sync"
        assert result["instance_id"] == "i-0123456789abcdef0"

    def test_should_return_none_for_invalid_prefix(self):
        """Should return None for non-remotepy schedules."""
        from remote.scheduler import parse_schedule_name

        assert parse_schedule_name("other-wake-i-123") is None

    def test_should_return_none_for_invalid_action(self):
        """Should return None for unknown actions."""
        from remote.scheduler import parse_schedule_name

        assert parse_schedule_name("remotepy-restart-i-123") is None

    def test_should_return_none_for_empty_string(self):
        """Should return None for empty string."""
        from remote.scheduler import parse_schedule_name

        assert parse_schedule_name("") is None

    def test_should_parse_short_instance_id(self):
        """Should parse schedule with short instance ID."""
        from remote.scheduler import parse_schedule_name

        result = parse_schedule_name("remotepy-wake-i-12345678")

        assert result is not None
        assert result["instance_id"] == "i-12345678"


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

    def test_named_schedule_name_pattern(self, mocker):
        """Should follow naming pattern: remotepy-{action}-{name}-{instance_id}."""
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
            name="morning",
        )

        call_kwargs = mock_scheduler.return_value.create_schedule.call_args[1]
        assert call_kwargs["Name"] == "remotepy-wake-morning-i-0123456789abcdef0"
