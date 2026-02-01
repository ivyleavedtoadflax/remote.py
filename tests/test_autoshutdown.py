"""Tests for CloudWatch-based auto-shutdown functionality."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from remote.autoshutdown import (
    _create_auto_shutdown_alarm,
    _get_existing_alarm,
    app,
    delete_auto_shutdown_alarm,
)

runner = CliRunner()


# ============================================================================
# Helper Functions Tests
# ============================================================================


class TestGetExistingAlarm:
    """Tests for _get_existing_alarm helper function."""

    def test_should_return_alarm_when_exists(self, mocker):
        """Should return alarm dict when alarm exists."""
        mock_cloudwatch = mocker.patch("remote.autoshutdown.get_cloudwatch_client")
        mock_cloudwatch.return_value.describe_alarms.return_value = {
            "MetricAlarms": [
                {
                    "AlarmName": "remotepy-autoshutdown-i-123",
                    "StateValue": "OK",
                    "Threshold": 5.0,
                }
            ]
        }

        result = _get_existing_alarm("remotepy-autoshutdown-i-123")

        assert result is not None
        assert result["AlarmName"] == "remotepy-autoshutdown-i-123"
        assert result["StateValue"] == "OK"
        mock_cloudwatch.return_value.describe_alarms.assert_called_once_with(
            AlarmNames=["remotepy-autoshutdown-i-123"],
            AlarmTypes=["MetricAlarm"],
        )

    def test_should_return_none_when_alarm_not_found(self, mocker):
        """Should return None when alarm doesn't exist."""
        mock_cloudwatch = mocker.patch("remote.autoshutdown.get_cloudwatch_client")
        mock_cloudwatch.return_value.describe_alarms.return_value = {"MetricAlarms": []}

        result = _get_existing_alarm("remotepy-autoshutdown-i-123")

        assert result is None


class TestCreateAutoShutdownAlarm:
    """Tests for _create_auto_shutdown_alarm helper function."""

    def test_should_create_alarm_with_correct_parameters(self, mocker):
        """Should call put_metric_alarm with correct parameters."""
        mock_cloudwatch = mocker.patch("remote.autoshutdown.get_cloudwatch_client")
        mocker.patch("remote.autoshutdown.get_current_region", return_value="us-east-1")

        _create_auto_shutdown_alarm(
            instance_id="i-0123456789abcdef0",
            instance_name="test-instance",
            threshold=5,
            duration_minutes=30,
        )

        mock_cloudwatch.return_value.put_metric_alarm.assert_called_once()
        call_kwargs = mock_cloudwatch.return_value.put_metric_alarm.call_args[1]

        assert call_kwargs["AlarmName"] == "remotepy-autoshutdown-i-0123456789abcdef0"
        assert call_kwargs["MetricName"] == "CPUUtilization"
        assert call_kwargs["Namespace"] == "AWS/EC2"
        assert call_kwargs["Statistic"] == "Average"
        assert call_kwargs["Threshold"] == 5.0
        assert call_kwargs["ComparisonOperator"] == "LessThanThreshold"
        assert call_kwargs["Period"] == 300
        assert call_kwargs["EvaluationPeriods"] == 6  # 30 min / 5 min periods
        assert call_kwargs["AlarmActions"] == ["arn:aws:automate:us-east-1:ec2:stop"]

    def test_should_calculate_evaluation_periods_correctly(self, mocker):
        """Should calculate evaluation periods based on duration."""
        mock_cloudwatch = mocker.patch("remote.autoshutdown.get_cloudwatch_client")
        mocker.patch("remote.autoshutdown.get_current_region", return_value="us-east-1")

        # 60 minutes / 5 minutes = 12 evaluation periods
        _create_auto_shutdown_alarm(
            instance_id="i-123",
            instance_name="test",
            threshold=10,
            duration_minutes=60,
        )

        call_kwargs = mock_cloudwatch.return_value.put_metric_alarm.call_args[1]
        assert call_kwargs["EvaluationPeriods"] == 12

    def test_should_have_minimum_one_evaluation_period(self, mocker):
        """Should have at least one evaluation period for short durations."""
        mock_cloudwatch = mocker.patch("remote.autoshutdown.get_cloudwatch_client")
        mocker.patch("remote.autoshutdown.get_current_region", return_value="us-east-1")

        # 5 minutes / 5 minutes = 1 evaluation period (minimum)
        _create_auto_shutdown_alarm(
            instance_id="i-123",
            instance_name="test",
            threshold=5,
            duration_minutes=5,
        )

        call_kwargs = mock_cloudwatch.return_value.put_metric_alarm.call_args[1]
        assert call_kwargs["EvaluationPeriods"] == 1


class TestDeleteAutoShutdownAlarm:
    """Tests for delete_auto_shutdown_alarm helper function."""

    def test_should_delete_alarm_when_exists(self, mocker):
        """Should delete alarm and return True when alarm exists."""
        mock_cloudwatch = mocker.patch("remote.autoshutdown.get_cloudwatch_client")
        mock_cloudwatch.return_value.describe_alarms.return_value = {
            "MetricAlarms": [{"AlarmName": "remotepy-autoshutdown-i-123"}]
        }

        result = delete_auto_shutdown_alarm("i-123")

        assert result is True
        mock_cloudwatch.return_value.delete_alarms.assert_called_once_with(
            AlarmNames=["remotepy-autoshutdown-i-123"]
        )

    def test_should_return_false_when_alarm_not_exists(self, mocker):
        """Should return False and not call delete when alarm doesn't exist."""
        mock_cloudwatch = mocker.patch("remote.autoshutdown.get_cloudwatch_client")
        mock_cloudwatch.return_value.describe_alarms.return_value = {"MetricAlarms": []}

        result = delete_auto_shutdown_alarm("i-123")

        assert result is False
        mock_cloudwatch.return_value.delete_alarms.assert_not_called()


# ============================================================================
# Enable Command Tests
# ============================================================================


class TestEnableCommand:
    """Tests for the 'auto-shutdown enable' command."""

    def test_should_create_alarm_with_default_parameters(self, mocker):
        """Should create alarm with default threshold and duration."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)
        mock_create = mocker.patch("remote.autoshutdown._create_auto_shutdown_alarm")

        result = runner.invoke(app, ["enable", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once_with("i-0123456789abcdef0", "test-instance", 5, 30)
        assert "Enabled auto-shutdown" in result.stdout

    def test_should_create_alarm_with_custom_threshold(self, mocker):
        """Should create alarm with custom threshold."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)
        mock_create = mocker.patch("remote.autoshutdown._create_auto_shutdown_alarm")

        result = runner.invoke(app, ["enable", "--threshold", "10", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once_with("i-123", "test-instance", 10, 30)

    def test_should_create_alarm_with_custom_duration(self, mocker):
        """Should create alarm with custom duration."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)
        mock_create = mocker.patch("remote.autoshutdown._create_auto_shutdown_alarm")

        result = runner.invoke(app, ["enable", "--duration", "60", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once_with("i-123", "test-instance", 5, 60)

    def test_should_update_alarm_when_already_exists(self, mocker):
        """Should update existing alarm and show 'Updated' message."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.autoshutdown._get_existing_alarm",
            return_value={"AlarmName": "remotepy-autoshutdown-i-123"},
        )
        mock_create = mocker.patch("remote.autoshutdown._create_auto_shutdown_alarm")

        result = runner.invoke(app, ["enable", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once()
        assert "Updated auto-shutdown" in result.stdout

    def test_should_reject_threshold_below_1(self, mocker):
        """Should reject threshold below 1 percent."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(app, ["enable", "--threshold", "0", "--yes"])

        assert result.exit_code == 1
        assert "Threshold must be between 1 and 99" in result.stdout

    def test_should_reject_threshold_above_99(self, mocker):
        """Should reject threshold above 99 percent."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(app, ["enable", "--threshold", "100", "--yes"])

        assert result.exit_code == 1
        assert "Threshold must be between 1 and 99" in result.stdout

    def test_should_reject_duration_below_5(self, mocker):
        """Should reject duration below 5 minutes."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(app, ["enable", "--duration", "4", "--yes"])

        assert result.exit_code == 1
        assert "Duration must be between 5 and 1440" in result.stdout

    def test_should_reject_duration_above_1440(self, mocker):
        """Should reject duration above 1440 minutes (24 hours)."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(app, ["enable", "--duration", "1441", "--yes"])

        assert result.exit_code == 1
        assert "Duration must be between 5 and 1440" in result.stdout

    def test_should_accept_specific_instance_name(self, mocker):
        """Should work with a specific instance name argument."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("my-server", "i-specific"),
        )
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)
        mock_create = mocker.patch("remote.autoshutdown._create_auto_shutdown_alarm")

        result = runner.invoke(app, ["enable", "my-server", "--yes"])

        assert result.exit_code == 0
        mock_create.assert_called_once_with("i-specific", "my-server", 5, 30)

    def test_should_prompt_for_confirmation_without_yes_flag(self, mocker):
        """Should prompt for confirmation when --yes is not provided."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)
        mocker.patch("remote.autoshutdown._create_auto_shutdown_alarm")
        mock_confirm = mocker.patch("remote.autoshutdown.confirm_action", return_value=False)

        result = runner.invoke(app, ["enable"])

        assert result.exit_code == 0
        mock_confirm.assert_called_once()
        assert "Cancelled" in result.stdout


# ============================================================================
# Disable Command Tests
# ============================================================================


class TestDisableCommand:
    """Tests for the 'auto-shutdown disable' command."""

    def test_should_delete_alarm_when_exists(self, mocker):
        """Should delete alarm and show success message."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.autoshutdown._get_existing_alarm",
            return_value={"AlarmName": "remotepy-autoshutdown-i-123"},
        )
        mock_delete = mocker.patch(
            "remote.autoshutdown.delete_auto_shutdown_alarm", return_value=True
        )

        result = runner.invoke(app, ["disable", "--yes"])

        assert result.exit_code == 0
        mock_delete.assert_called_once_with("i-123")
        assert "Disabled auto-shutdown" in result.stdout

    def test_should_warn_when_alarm_not_enabled(self, mocker):
        """Should show warning when auto-shutdown is not enabled."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)

        result = runner.invoke(app, ["disable", "--yes"])

        assert result.exit_code == 0
        assert "not enabled" in result.stdout

    def test_should_prompt_for_confirmation_without_yes_flag(self, mocker):
        """Should prompt for confirmation when --yes is not provided."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.autoshutdown._get_existing_alarm",
            return_value={"AlarmName": "remotepy-autoshutdown-i-123"},
        )
        mock_confirm = mocker.patch("remote.autoshutdown.confirm_action", return_value=False)

        result = runner.invoke(app, ["disable"])

        assert result.exit_code == 0
        mock_confirm.assert_called_once()
        assert "Cancelled" in result.stdout

    def test_should_delete_alarm_by_instance_id(self, mocker):
        """Should delete alarm using --instance-id without resolving name."""
        mocker.patch(
            "remote.autoshutdown._get_existing_alarm",
            return_value={"AlarmName": "remotepy-autoshutdown-i-0123456789abcdef0"},
        )
        mock_delete = mocker.patch(
            "remote.autoshutdown.delete_auto_shutdown_alarm", return_value=True
        )
        mock_resolve = mocker.patch("remote.autoshutdown.resolve_instance_or_exit")

        result = runner.invoke(app, ["disable", "--instance-id", "i-0123456789abcdef0", "--yes"])

        assert result.exit_code == 0
        mock_resolve.assert_not_called()
        mock_delete.assert_called_once_with("i-0123456789abcdef0")
        assert "Disabled auto-shutdown" in result.stdout

    def test_should_reject_invalid_instance_id_format(self, mocker):
        """Should reject instance IDs that don't match expected format."""
        result = runner.invoke(app, ["disable", "--instance-id", "invalid-id", "--yes"])

        assert result.exit_code == 1
        assert "Invalid instance ID format" in result.stdout

    def test_should_warn_when_alarm_not_found_by_instance_id(self, mocker):
        """Should show warning when no alarm exists for instance ID."""
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)

        result = runner.invoke(app, ["disable", "--instance-id", "i-0123456789abcdef0", "--yes"])

        assert result.exit_code == 0
        assert "not enabled" in result.stdout


# ============================================================================
# Status Command Tests
# ============================================================================


class TestStatusCommand:
    """Tests for the 'auto-shutdown status' command."""

    def test_should_show_status_when_enabled(self, mocker):
        """Should display alarm status when auto-shutdown is enabled."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mocker.patch(
            "remote.autoshutdown._get_existing_alarm",
            return_value={
                "AlarmName": "remotepy-autoshutdown-i-0123456789abcdef0",
                "StateValue": "OK",
                "Threshold": 5.0,
                "Period": 300,
                "EvaluationPeriods": 6,
                "StateReason": "Threshold Crossed: 1 datapoint was not < 5.0",
            },
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "test-instance" in result.stdout
        assert "i-0123456789abcdef0" in result.stdout
        assert "OK" in result.stdout
        assert "5" in result.stdout  # threshold
        assert "30" in result.stdout  # duration in minutes

    def test_should_show_warning_when_not_enabled(self, mocker):
        """Should show warning when auto-shutdown is not enabled."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.autoshutdown._get_existing_alarm", return_value=None)

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "not enabled" in result.stdout

    @pytest.mark.parametrize(
        "state,expected_text",
        [
            ("OK", "OK"),
            ("ALARM", "ALARM"),
            ("INSUFFICIENT_DATA", "INSUFFICIENT_DATA"),
        ],
    )
    def test_should_display_various_alarm_states(self, mocker, state, expected_text):
        """Should correctly display different alarm states."""
        mocker.patch(
            "remote.autoshutdown.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch(
            "remote.autoshutdown._get_existing_alarm",
            return_value={
                "AlarmName": "remotepy-autoshutdown-i-123",
                "StateValue": state,
                "Threshold": 5.0,
                "Period": 300,
                "EvaluationPeriods": 6,
                "StateReason": "Test reason",
            },
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert expected_text in result.stdout


# ============================================================================
# Integration Tests (CloudWatch Client)
# ============================================================================


class TestCloudWatchClientIntegration:
    """Tests for CloudWatch client integration."""

    def test_should_use_cached_cloudwatch_client(self, mocker):
        """Should use cached CloudWatch client from utils."""
        from remote.utils import clear_cloudwatch_client_cache, get_cloudwatch_client

        # Clear any existing cache
        clear_cloudwatch_client_cache()

        mock_boto3 = mocker.patch("remote.utils.boto3")
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # First call should create client
        client1 = get_cloudwatch_client()
        # Second call should return cached client
        client2 = get_cloudwatch_client()

        assert client1 is client2
        mock_boto3.client.assert_called_once_with("cloudwatch")

        # Clean up
        clear_cloudwatch_client_cache()
