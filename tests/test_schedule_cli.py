"""Tests for schedule CLI commands (EventBridge Scheduler wake/sleep).

These tests cover the CLI interface for scheduling EC2 instance start/stop.
"""

from typer.testing import CliRunner

runner = CliRunner()


# ============================================================================
# Wake Command Tests
# ============================================================================


class TestWakeCommand:
    """Tests for the 'schedule wake' command."""

    def test_should_create_wake_schedule(self, mocker):
        """Should create a wake schedule with default days."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")

        result = runner.invoke(app, ["wake", "--time", "09:00", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["instance_id"] == "i-0123456789abcdef0"
        assert call_kwargs["action"] == "wake"
        assert "9" in call_kwargs["schedule_expression"]
        assert "Created wake schedule" in result.stdout

    def test_should_create_wake_schedule_with_custom_days(self, mocker):
        """Should create a wake schedule with custom days."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")

        result = runner.invoke(app, ["wake", "--time", "08:00", "--days", "mon,wed,fri", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert "MON" in call_kwargs["schedule_expression"]
        assert "WED" in call_kwargs["schedule_expression"]
        assert "FRI" in call_kwargs["schedule_expression"]

    def test_should_use_timezone_from_config(self, mocker):
        """Should use timezone from config when not specified."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")
        mock_config = mocker.patch("remote.schedule.config_manager")
        mock_config.get_value.return_value = "America/New_York"

        result = runner.invoke(app, ["wake", "--time", "09:00", "--yes"])

        assert result.exit_code == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["timezone"] == "America/New_York"

    def test_should_use_timezone_flag_over_config(self, mocker):
        """Should prefer --timezone flag over config."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")
        mock_config = mocker.patch("remote.schedule.config_manager")
        mock_config.get_value.return_value = "America/New_York"

        result = runner.invoke(
            app, ["wake", "--time", "09:00", "--timezone", "Europe/London", "--yes"]
        )

        assert result.exit_code == 0
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["timezone"] == "Europe/London"

    def test_should_reject_invalid_time(self, mocker):
        """Should reject invalid time format."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(app, ["wake", "--time", "25:00", "--yes"])

        assert result.exit_code == 1
        assert "Invalid" in result.stdout or "invalid" in result.stdout.lower()

    def test_should_reject_invalid_days(self, mocker):
        """Should reject invalid days format."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(app, ["wake", "--time", "09:00", "--days", "monday", "--yes"])

        assert result.exit_code == 1
        assert "Invalid" in result.stdout or "invalid" in result.stdout.lower()

    def test_should_prompt_for_confirmation_without_yes(self, mocker):
        """Should prompt for confirmation when --yes not provided."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.schedule.create_schedule")
        mock_confirm = mocker.patch("remote.schedule.confirm_action", return_value=False)

        result = runner.invoke(app, ["wake", "--time", "09:00"])

        assert result.exit_code == 0
        mock_confirm.assert_called_once()
        assert "Cancelled" in result.stdout


# ============================================================================
# Sleep Command Tests
# ============================================================================


class TestSleepCommand:
    """Tests for the 'schedule sleep' command."""

    def test_should_create_sleep_schedule(self, mocker):
        """Should create a sleep schedule."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")

        result = runner.invoke(app, ["sleep", "--time", "18:00", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["action"] == "sleep"
        assert "Created sleep schedule" in result.stdout

    def test_should_create_sleep_schedule_with_weekend_days(self, mocker):
        """Should create sleep schedule for weekends."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")

        result = runner.invoke(app, ["sleep", "--time", "22:00", "--days", "sat,sun", "--yes"])

        assert result.exit_code == 0
        call_kwargs = mock_create.call_args[1]
        assert "SAT" in call_kwargs["schedule_expression"]
        assert "SUN" in call_kwargs["schedule_expression"]


# ============================================================================
# One-Time Schedule Tests (--at option)
# ============================================================================


class TestOneTimeScheduleOption:
    """Tests for the --at option for one-time schedules."""

    def test_should_create_one_time_wake_schedule(self, mocker):
        """Should create a one-time wake schedule with --at."""
        from datetime import date

        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")
        # Mock date.today to return 2026-02-02 (Monday)
        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        result = runner.invoke(app, ["wake", "--time", "09:00", "--at", "tomorrow", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["action"] == "wake"
        assert "at(" in call_kwargs["schedule_expression"]
        assert "2026-02-03" in call_kwargs["schedule_expression"]
        assert "09:00:00" in call_kwargs["schedule_expression"]

    def test_should_create_one_time_sleep_schedule(self, mocker):
        """Should create a one-time sleep schedule with --at."""
        from datetime import date

        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")
        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        result = runner.invoke(app, ["sleep", "--time", "18:00", "--at", "tuesday", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["action"] == "sleep"
        assert "at(" in call_kwargs["schedule_expression"]
        assert "18:00:00" in call_kwargs["schedule_expression"]

    def test_should_reject_both_at_and_days(self, mocker):
        """Should reject using both --at and --days."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(
            app, ["wake", "--time", "09:00", "--at", "tomorrow", "--days", "mon-fri", "--yes"]
        )

        assert result.exit_code == 1
        assert "Cannot use both" in result.stdout or "mutually exclusive" in result.stdout.lower()

    def test_should_accept_iso_date_format(self, mocker):
        """Should accept ISO date format for --at."""
        from datetime import date

        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mock_create = mocker.patch("remote.schedule.create_schedule")
        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        result = runner.invoke(app, ["wake", "--time", "10:30", "--at", "2026-02-15", "--yes"])

        assert result.exit_code == 0
        call_kwargs = mock_create.call_args[1]
        assert "at(2026-02-15T10:30:00)" in call_kwargs["schedule_expression"]

    def test_should_show_one_time_in_confirmation_message(self, mocker):
        """Should show 'one-time' in confirmation message."""
        from datetime import date

        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.schedule.create_schedule")
        mock_date = mocker.patch("remote.validation.date")
        mock_date.today.return_value = date(2026, 2, 2)
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        result = runner.invoke(app, ["wake", "--time", "09:00", "--at", "tomorrow", "--yes"])

        assert result.exit_code == 0
        assert "one-time" in result.stdout.lower() or "2026-02-03" in result.stdout


# ============================================================================
# Status Command Tests
# ============================================================================


class TestStatusCommand:
    """Tests for the 'schedule status' command."""

    def test_should_show_schedules_when_enabled(self, mocker):
        """Should display schedule status when schedules exist."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mocker.patch(
            "remote.schedule.get_schedules_for_instance",
            return_value={
                "wake": {
                    "Name": "remotepy-wake-i-0123456789abcdef0",
                    "ScheduleExpression": "cron(0 9 ? * MON,TUE,WED,THU,FRI *)",
                    "ScheduleExpressionTimezone": "UTC",
                    "State": "ENABLED",
                },
                "sleep": {
                    "Name": "remotepy-sleep-i-0123456789abcdef0",
                    "ScheduleExpression": "cron(0 18 ? * MON,TUE,WED,THU,FRI *)",
                    "ScheduleExpressionTimezone": "UTC",
                    "State": "ENABLED",
                },
            },
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "test-instance" in result.stdout
        assert "wake" in result.stdout.lower()
        assert "sleep" in result.stdout.lower()

    def test_should_show_message_when_no_schedules(self, mocker):
        """Should show message when no schedules exist."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.schedule.get_schedules_for_instance",
            return_value={"wake": None, "sleep": None},
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "No schedules" in result.stdout or "not configured" in result.stdout


# ============================================================================
# Clear Command Tests
# ============================================================================


class TestClearCommand:
    """Tests for the 'schedule clear' command."""

    def test_should_clear_all_schedules(self, mocker):
        """Should clear both wake and sleep schedules."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.schedule.get_schedules_for_instance",
            return_value={
                "wake": {"Name": "remotepy-wake-i-123"},
                "sleep": {"Name": "remotepy-sleep-i-123"},
            },
        )
        mock_delete = mocker.patch(
            "remote.schedule.delete_all_schedules_for_instance",
            return_value={"wake": True, "sleep": True},
        )

        result = runner.invoke(app, ["clear", "--yes"])

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("i-123")
        assert "Cleared" in result.stdout or "Deleted" in result.stdout

    def test_should_clear_only_wake_schedule(self, mocker):
        """Should clear only wake schedule when --wake specified."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.schedule.get_schedule",
            return_value={"Name": "remotepy-wake-i-123"},
        )
        mock_delete = mocker.patch("remote.schedule.delete_schedule", return_value=True)

        result = runner.invoke(app, ["clear", "--wake", "--yes"])

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("i-123", "wake")

    def test_should_clear_only_sleep_schedule(self, mocker):
        """Should clear only sleep schedule when --sleep specified."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.schedule.get_schedule",
            return_value={"Name": "remotepy-sleep-i-123"},
        )
        mock_delete = mocker.patch("remote.schedule.delete_schedule", return_value=True)

        result = runner.invoke(app, ["clear", "--sleep", "--yes"])

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("i-123", "sleep")

    def test_should_warn_when_no_schedules_to_clear(self, mocker):
        """Should warn when no schedules exist to clear."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.schedule.get_schedules_for_instance",
            return_value={"wake": None, "sleep": None},
        )

        result = runner.invoke(app, ["clear", "--yes"])

        assert result.exit_code == 0
        assert "No schedules" in result.stdout or "not configured" in result.stdout


# ============================================================================
# List Command Tests
# ============================================================================


class TestListCommand:
    """Tests for the 'schedule list' command."""

    def test_should_list_all_schedules(self, mocker):
        """Should list all remotepy schedules."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.list_schedules",
            return_value=[
                {"Name": "remotepy-wake-i-111", "State": "ENABLED"},
                {"Name": "remotepy-sleep-i-111", "State": "ENABLED"},
                {"Name": "remotepy-wake-i-222", "State": "DISABLED"},
            ],
        )
        mocker.patch(
            "remote.schedule.get_schedule",
            return_value={
                "ScheduleExpression": "cron(0 9 ? * MON-FRI *)",
                "ScheduleExpressionTimezone": "UTC",
            },
        )
        mocker.patch(
            "remote.utils.get_instance_names_by_ids",
            return_value={},
        )

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "i-111" in result.stdout or "remotepy-wake" in result.stdout
        assert "i-222" in result.stdout or "remotepy-wake" in result.stdout

    def test_should_show_message_when_no_schedules(self, mocker):
        """Should show message when no schedules exist."""
        from remote.schedule import app

        mocker.patch("remote.schedule.list_schedules", return_value=[])

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No schedules" in result.stdout or "none" in result.stdout.lower()

    def test_should_show_instance_names_when_available(self, mocker):
        """Should display instance names instead of IDs when names are available."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.list_schedules",
            return_value=[
                {"Name": "remotepy-wake-i-111", "State": "ENABLED"},
                {"Name": "remotepy-sleep-i-111", "State": "ENABLED"},
            ],
        )
        mocker.patch(
            "remote.schedule.get_schedule",
            return_value={
                "ScheduleExpression": "cron(0 9 ? * MON-FRI *)",
                "ScheduleExpressionTimezone": "UTC",
            },
        )
        mocker.patch(
            "remote.utils.get_instance_names_by_ids",
            return_value={"i-111": "my-dev-server"},
        )

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "my-dev-server" in result.stdout

    def test_should_fall_back_to_instance_id_when_name_not_available(self, mocker):
        """Should fall back to instance ID when name lookup returns empty."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.list_schedules",
            return_value=[
                {"Name": "remotepy-wake-i-terminated", "State": "ENABLED"},
            ],
        )
        mocker.patch(
            "remote.schedule.get_schedule",
            return_value={
                "ScheduleExpression": "cron(0 9 ? * MON-FRI *)",
                "ScheduleExpressionTimezone": "UTC",
            },
        )
        mocker.patch(
            "remote.utils.get_instance_names_by_ids",
            return_value={},  # No names found (e.g., terminated instance)
        )

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "i-terminated" in result.stdout


# ============================================================================
# Cleanup Role Command Tests
# ============================================================================


class TestCleanupRoleCommand:
    """Tests for the 'schedule cleanup-role' command."""

    def test_should_delete_role_when_no_schedules(self, mocker):
        """Should delete role when no schedules exist."""
        from remote.schedule import app

        mocker.patch("remote.schedule.list_schedules", return_value=[])
        mock_delete = mocker.patch("remote.schedule.delete_scheduler_role", return_value=True)

        result = runner.invoke(app, ["cleanup-role", "--yes"])

        assert result.exit_code == 0
        mock_delete.assert_called_once()
        assert "Deleted" in result.stdout or "removed" in result.stdout.lower()

    def test_should_fail_when_schedules_exist(self, mocker):
        """Should fail when schedules still exist."""
        from remote.schedule import app

        mocker.patch(
            "remote.schedule.list_schedules",
            return_value=[{"Name": "remotepy-wake-i-123"}],
        )

        result = runner.invoke(app, ["cleanup-role", "--yes"])

        assert result.exit_code == 1
        assert (
            "schedules still exist" in result.stdout.lower()
            or "cannot delete" in result.stdout.lower()
        )

    def test_should_warn_when_role_not_exists(self, mocker):
        """Should warn when role doesn't exist."""
        from remote.schedule import app

        mocker.patch("remote.schedule.list_schedules", return_value=[])
        mocker.patch("remote.schedule.delete_scheduler_role", return_value=False)

        result = runner.invoke(app, ["cleanup-role", "--yes"])

        assert result.exit_code == 0
        assert "not found" in result.stdout.lower() or "does not exist" in result.stdout.lower()
