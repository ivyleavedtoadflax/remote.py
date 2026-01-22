from typer.testing import CliRunner

from remote.instance import app
from remote.utils import get_launch_template_id

runner = CliRunner()


# ============================================================================
# Instance CLI Command Tests
# ============================================================================


class TestInstanceStatusCommand:
    """Test the 'remote status' command behavior."""

    def test_should_report_error_when_instance_not_found(self, mocker):
        """Should exit with error code 1 when instance doesn't exist."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {"Reservations": []}

        result = runner.invoke(app, ["status", "test"])

        assert result.exit_code == 1
        assert "Instance 'test' not found" in result.stdout


class TestInstanceListCommand:
    """Test the 'remote list' command behavior."""

    def test_should_show_table_headers_when_no_instances_exist(self, mocker):
        """Should display table headers even when no instances are found."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        # Mock the paginator for get_instances() which uses pagination
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Name" in result.stdout
        assert "InstanceId" in result.stdout
        assert "PublicDnsName" in result.stdout
        assert "Status" in result.stdout

    def test_should_display_instance_details_when_instances_exist(self, mocker, mock_ec2_instances):
        """Should show instance details in tabular format when instances are found."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Mock the paginator
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [mock_ec2_instances]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list"])

        # Verify paginator was used
        mock_ec2_client.return_value.get_paginator.assert_called_once_with("describe_instances")

        # Verify table headers are present
        assert "Name" in result.stdout
        assert "InstanceId" in result.stdout
        assert "PublicDnsName" in result.stdout
        assert "Status" in result.stdout
        assert "Type" in result.stdout
        assert "Launch Time" in result.stdout

        # Verify actual instance data is displayed
        assert "i-0123456789abcdef0" in result.stdout
        assert "running" in result.stdout
        assert "t2.micro" in result.stdout
        assert "2023-07-15 00:00:00 UTC" in result.stdout

    def test_should_hide_cost_columns_by_default(self, mocker):
        """Should not display cost columns by default (without --cost flag)."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # Cost columns should be hidden by default
        assert "$/hr" not in result.stdout
        assert "Est. Cost" not in result.stdout
        assert "Uptime" not in result.stdout

    def test_should_not_call_pricing_api_by_default(self, mocker, mock_ec2_instances):
        """Should skip pricing API calls by default (without --cost flag)."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [mock_ec2_instances]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        mock_get_price = mocker.patch("remote.instance.get_instance_price_with_fallback")

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        mock_get_price.assert_not_called()

    def test_should_exclude_terminated_instances_by_default(self, mocker):
        """Should call get_instances with exclude_terminated=True by default."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # Verify the paginate was called with the filter to exclude terminated
        mock_paginator.paginate.assert_called_once_with(
            Filters=[
                {
                    "Name": "instance-state-name",
                    "Values": ["pending", "running", "shutting-down", "stopping", "stopped"],
                }
            ]
        )

    def test_should_include_terminated_instances_with_all_flag(self, mocker):
        """Should call get_instances without filter when --all flag is used."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list", "--all"])

        assert result.exit_code == 0
        # Verify the paginate was called without filters (to include all instances)
        mock_paginator.paginate.assert_called_once_with()

    def test_should_include_terminated_instances_with_short_flag(self, mocker):
        """Should call get_instances without filter when -a flag is used."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list", "-a"])

        assert result.exit_code == 0
        # Verify the paginate was called without filters (to include all instances)
        mock_paginator.paginate.assert_called_once_with()


class TestLaunchTemplateUtilities:
    """Test launch template utility functions."""

    def test_should_return_template_id_when_template_found_by_name(self, mocker):
        """Should return the launch template ID when template is found by name tag."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_launch_templates.return_value = {
            "LaunchTemplates": [{"LaunchTemplateId": "lt-0123456789abcdef0"}]
        }

        result = get_launch_template_id("my-template-name")

        mock_ec2_client.return_value.describe_launch_templates.assert_called_once_with(
            Filters=[{"Name": "tag:Name", "Values": ["my-template-name"]}]
        )
        assert result == "lt-0123456789abcdef0"

    def test_should_show_running_instance_status_details(self, mocker):
        """Should display detailed status information for a running instance."""
        mock_resolve_instance = mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mock_get_instance_status = mocker.patch(
            "remote.instance.get_instance_status",
            return_value={
                "InstanceStatuses": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceState": {"Name": "running"},
                        "SystemStatus": {"Status": "ok"},
                        "InstanceStatus": {"Status": "ok", "Details": [{"Status": "passed"}]},
                    }
                ]
            },
        )
        # Mock EC2 client for describe_instances call
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                            "PublicIpAddress": "1.2.3.4",
                            "PrivateIpAddress": "10.0.0.1",
                            "PublicDnsName": "ec2-1-2-3-4.compute-1.amazonaws.com",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [{"GroupName": "default"}],
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        result = runner.invoke(app, ["status"])

        # Verify command succeeds
        assert result.exit_code == 0

        # Verify correct call sequence
        mock_resolve_instance.assert_called_once_with(None)
        mock_get_instance_status.assert_called_once_with("i-0123456789abcdef0")

        # Verify status information is displayed
        assert "test-instance" in result.stdout
        assert "running" in result.stdout
        # Verify detailed info is shown
        assert "t2.micro" in result.stdout
        assert "1.2.3.4" in result.stdout

    def test_should_show_stopped_instance_details(self, mocker):
        """Should display details for stopped instances (without health status)."""
        mock_resolve_instance = mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("specific-instance", "i-0123456789abcdef0"),
        )
        mocker.patch("remote.instance.get_instance_status", return_value={"InstanceStatuses": []})
        # Mock EC2 client for describe_instances call
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t2.micro",
                            "PrivateIpAddress": "10.0.0.1",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [{"GroupName": "default"}],
                            "Tags": [{"Key": "Name", "Value": "specific-instance"}],
                        }
                    ]
                }
            ]
        }

        result = runner.invoke(app, ["status", "specific-instance"])

        assert result.exit_code == 0
        mock_resolve_instance.assert_called_once_with("specific-instance")
        # Verify basic info is displayed
        assert "specific-instance" in result.stdout
        assert "stopped" in result.stdout
        assert "t2.micro" in result.stdout


class TestStatusWatchMode:
    """Test the watch mode functionality for the status command."""

    def test_should_reject_interval_less_than_one(self, mocker):
        """Should exit with error when interval is less than 1."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )

        result = runner.invoke(app, ["status", "--watch", "--interval", "0"])

        assert result.exit_code == 1
        assert "Interval must be at least 1 second" in result.stdout

    def test_should_accept_watch_flag(self, mocker):
        """Should accept the --watch flag and enter watch mode."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )

        # Mock _watch_status to avoid actually entering the infinite loop
        mock_watch = mocker.patch("remote.instance._watch_status")

        result = runner.invoke(app, ["status", "--watch"])

        assert result.exit_code == 0
        mock_watch.assert_called_once_with("test-instance", "i-0123456789abcdef0", 2)

    def test_should_accept_short_watch_flag(self, mocker):
        """Should accept the -w short flag for watch mode."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )

        mock_watch = mocker.patch("remote.instance._watch_status")

        result = runner.invoke(app, ["status", "-w"])

        assert result.exit_code == 0
        mock_watch.assert_called_once()

    def test_should_accept_custom_interval(self, mocker):
        """Should accept custom interval via --interval flag."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )

        mock_watch = mocker.patch("remote.instance._watch_status")

        result = runner.invoke(app, ["status", "--watch", "--interval", "5"])

        assert result.exit_code == 0
        mock_watch.assert_called_once_with("test-instance", "i-0123456789abcdef0", 5)

    def test_should_accept_short_interval_flag(self, mocker):
        """Should accept -i short flag for interval."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )

        mock_watch = mocker.patch("remote.instance._watch_status")

        result = runner.invoke(app, ["status", "-w", "-i", "10"])

        assert result.exit_code == 0
        mock_watch.assert_called_once_with("test-instance", "i-0123456789abcdef0", 10)


class TestBuildStatusTable:
    """Test the _build_status_table helper function."""

    def test_should_return_panel_for_running_instance(self, mocker):
        """Should return a Rich Panel for a running instance."""
        from rich.panel import Panel

        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={
                "InstanceStatuses": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceState": {"Name": "running"},
                        "SystemStatus": {"Status": "ok"},
                        "InstanceStatus": {"Status": "ok", "Details": [{"Status": "passed"}]},
                    }
                ]
            },
        )
        # Mock EC2 client for describe_instances call
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                            "PublicIpAddress": "1.2.3.4",
                            "PrivateIpAddress": "10.0.0.1",
                            "PublicDnsName": "ec2-1-2-3-4.compute-1.amazonaws.com",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [{"GroupName": "default"}],
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        assert isinstance(result, Panel)

    def test_should_return_panel_with_expand_false(self, mocker):
        """Panel should not expand to full terminal width."""
        from rich.panel import Panel

        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={
                "InstanceStatuses": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceState": {"Name": "running"},
                        "SystemStatus": {"Status": "ok"},
                        "InstanceStatus": {"Status": "ok", "Details": [{"Status": "passed"}]},
                    }
                ]
            },
        )
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running"},
                            "InstanceType": "t2.micro",
                            "PublicIpAddress": "1.2.3.4",
                            "PrivateIpAddress": "10.0.0.1",
                            "PublicDnsName": "ec2-1-2-3-4.compute-1.amazonaws.com",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [{"GroupName": "default"}],
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        assert isinstance(result, Panel)
        assert result.expand is False

    def test_should_return_panel_for_stopped_instance(self, mocker):
        """Should return a Panel for stopped instances (without health section)."""
        from rich.panel import Panel

        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        # Mock EC2 client for describe_instances call
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t2.micro",
                            "PrivateIpAddress": "10.0.0.1",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [{"GroupName": "default"}],
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        # Should still return a Panel with basic info (just no health section)
        assert isinstance(result, Panel)

    def test_should_raise_exception_for_not_found_instance(self, mocker):
        """Should raise InstanceNotFoundError when instance is not found."""
        import pytest

        from remote.exceptions import InstanceNotFoundError
        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        # Mock EC2 client returning empty reservations
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {"Reservations": []}

        with pytest.raises(InstanceNotFoundError) as exc_info:
            _build_status_table("test-instance", "i-0123456789abcdef0")

        assert "test-instance" in str(exc_info.value)


class TestWatchStatusFunction:
    """Test the _watch_status function."""

    def test_should_handle_keyboard_interrupt(self, mocker):
        """Should handle Ctrl+C gracefully."""
        from rich.panel import Panel

        from remote.instance import _watch_status

        # Mock time.sleep to raise KeyboardInterrupt
        mocker.patch("remote.instance.time.sleep", side_effect=KeyboardInterrupt)

        # Mock _build_status_table to return a Panel (new behavior)
        mock_panel = Panel("test content", title="Test")
        mocker.patch("remote.instance._build_status_table", return_value=mock_panel)

        # Mock console (imported from utils) and Live
        mocker.patch("remote.instance.console")
        mock_live = mocker.patch("remote.instance.Live")
        mock_live.return_value.__enter__ = mocker.Mock(return_value=mock_live.return_value)
        mock_live.return_value.__exit__ = mocker.Mock(return_value=False)

        # Should not raise, should exit gracefully
        _watch_status("test-instance", "i-0123456789abcdef0", 2)

        # Verify the function tried to update at least once
        mock_live.return_value.update.assert_called()


def test_start_instance_already_running(mocker):
    mock_resolve_instance = mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mock_get_instance_id = mocker.patch(
        "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remote.instance.is_instance_running", return_value=True
    )

    result = runner.invoke(app, ["start"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with(None)
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    assert "Instance test-instance is already running" in result.stdout


def test_start_instance_success(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mock_resolve_instance = mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mock_get_instance_id = mocker.patch(
        "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remote.instance.is_instance_running", return_value=False
    )

    result = runner.invoke(app, ["start", "test-instance"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with("test-instance")
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    mock_ec2_client.return_value.start_instances.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )
    assert "Instance test-instance started" in result.stdout


def test_start_instance_exception(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.is_instance_running", return_value=False)

    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "TestError", "Message": "AWS Error"}}
    mock_ec2_client.return_value.start_instances.side_effect = ClientError(
        error_response, "start_instances"
    )

    result = runner.invoke(app, ["start", "test-instance"])

    assert result.exit_code == 1
    assert "AWS Error:" in result.stdout
    assert "start_instances" in result.stdout


def test_stop_instance_already_stopped(mocker):
    mock_resolve_instance = mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mock_is_instance_running = mocker.patch(
        "remote.instance.is_instance_running", return_value=False
    )

    result = runner.invoke(app, ["stop", "test-instance"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    assert "Instance test-instance is already stopped" in result.stdout


def test_stop_instance_confirmed(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.is_instance_running", return_value=True)
    mocker.patch("remote.instance.get_instance_type", return_value="t3.micro")
    mocker.patch("remote.instance.get_instance_price_with_fallback", return_value=(0.0104, False))
    mocker.patch("remote.instance.tracking_manager")

    result = runner.invoke(app, ["stop", "test-instance"], input="y\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.stop_instances.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )
    assert "Instance test-instance is stopping" in result.stdout


def test_stop_instance_cancelled(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["stop", "test-instance"], input="n\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.stop_instances.assert_not_called()
    assert "Instance test-instance is still running" in result.stdout


def test_stop_instance_exception(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.is_instance_running", return_value=True)
    mocker.patch("remote.instance.get_instance_type", return_value="t3.micro")
    mocker.patch("remote.instance.get_instance_price_with_fallback", return_value=(0.0104, False))
    mocker.patch("remote.instance.tracking_manager")

    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "TestError", "Message": "AWS Error"}}
    mock_ec2_client.return_value.stop_instances.side_effect = ClientError(
        error_response, "stop_instances"
    )

    result = runner.invoke(app, ["stop", "test-instance"], input="y\n")

    assert result.exit_code == 1
    assert "AWS Error:" in result.stdout
    assert "stop_instances" in result.stdout


def test_type_command_show_current_type(mocker):
    mock_resolve_instance = mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mock_get_instance_type = mocker.patch(
        "remote.instance.get_instance_type", return_value="t2.micro"
    )

    result = runner.invoke(app, ["type"])

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with(None)
    # get_instance_type is called twice - once to get current, once at the end
    assert mock_get_instance_type.call_count >= 1
    assert "Instance test-instance is currently of type t2.micro" in result.stdout


def test_type_command_same_type(mocker):
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.get_instance_type", return_value="t2.micro")

    result = runner.invoke(app, ["type", "test-instance", "--type", "t2.micro"])

    assert result.exit_code == 0
    assert "Instance test-instance is already of type t2.micro" in result.stdout


def test_type_command_running_instance_error(mocker):
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.get_instance_type", return_value="t2.micro")
    mocker.patch("remote.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["type", "test-instance", "--type", "t2.small"])

    assert result.exit_code == 1
    assert "You can only change the type of a stopped instance" in result.stdout


def test_type_command_change_success(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.get_instance_type", side_effect=["t2.micro", "t2.small"])
    mocker.patch("remote.instance.is_instance_running", return_value=False)
    mocker.patch("remote.instance.time.sleep")

    result = runner.invoke(app, ["type", "test-instance", "--type", "t2.small"], input="y\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.modify_instance_attribute.assert_called_once_with(
        InstanceId="i-0123456789abcdef0", InstanceType={"Value": "t2.small"}
    )
    assert "Instance test-instance is now of type t2.small" in result.stdout


def test_type_command_change_cancelled(mocker):
    """Test that declining confirmation cancels the type change."""
    mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.get_instance_type", return_value="t2.micro")
    mocker.patch("remote.instance.is_instance_running", return_value=False)

    result = runner.invoke(app, ["type", "test-instance", "--type", "t2.small"], input="n\n")

    assert result.exit_code == 0
    assert "Type change cancelled" in result.stdout


def test_type_command_change_with_yes_flag(mocker):
    """Test that --yes flag skips confirmation."""
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.get_instance_type", side_effect=["t2.micro", "t2.small"])
    mocker.patch("remote.instance.is_instance_running", return_value=False)
    mocker.patch("remote.instance.time.sleep")

    result = runner.invoke(app, ["type", "test-instance", "--type", "t2.small", "--yes"])

    assert result.exit_code == 0
    mock_ec2_client.return_value.modify_instance_attribute.assert_called_once_with(
        InstanceId="i-0123456789abcdef0", InstanceType={"Value": "t2.small"}
    )
    assert "Instance test-instance is now of type t2.small" in result.stdout


def test_type_command_change_timeout(mocker):
    """Test that timeout warning is shown when type change doesn't complete in time."""
    mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    # Always return the old type to simulate the change never completing
    mocker.patch("remote.instance.get_instance_type", return_value="t2.micro")
    mocker.patch("remote.instance.is_instance_running", return_value=False)
    mocker.patch("remote.instance.time.sleep")

    result = runner.invoke(app, ["type", "test-instance", "--type", "t2.small", "--yes"])

    assert result.exit_code == 0
    assert "Timed out waiting for type change to complete" in result.stdout
    assert "Please verify the instance type with: remote type test-instance" in result.stdout


def test_type_command_invalid_instance_type_format(mocker):
    """Test that invalid instance type format is rejected before API call."""
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )
    mocker.patch("remote.instance.get_instance_type", return_value="t2.micro")

    result = runner.invoke(app, ["type", "test-instance", "--type", "invalid-type"])

    assert result.exit_code == 1
    assert "Invalid instance_type" in result.stdout
    assert "invalid-type" in result.stdout


def test_terminate_instance_name_mismatch(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mock_resolve_instance = mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    # Mock the describe_instances call that happens in terminate function
    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate"], input="wrong-name\n")

    assert result.exit_code == 0
    mock_resolve_instance.assert_called_once_with(None)
    assert "Instance names did not match. Aborting termination." in result.stdout


def test_terminate_instance_cancelled(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\nn\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.terminate_instances.assert_not_called()
    assert "Termination of instance test-instance has been cancelled" in result.stdout


def test_terminate_instance_confirmed(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\ny\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.terminate_instances.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )
    assert "Instance test-instance is being terminated" in result.stdout


def test_terminate_terraform_managed_instance(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch(
        "remote.instance.resolve_instance_or_exit",
        return_value=("test-instance", "i-0123456789abcdef0"),
    )

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"Tags": [{"Key": "Environment", "Value": "terraform-managed"}]}]}
        ]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\ny\n")

    assert result.exit_code == 0
    assert "This instance appears to be managed by Terraform" in result.stdout


def test_connect_with_key_option(mocker, tmp_path):
    """Test that --key option adds -i flag to SSH command."""
    # Create a temporary key file (SSH key validation now happens at parse time)
    key_file = tmp_path / "my-key.pem"
    key_file.touch()

    # Mock the AWS EC2 client in utils (where get_instance_id and is_instance_running are defined)
    mock_ec2 = mocker.patch("remote.utils.get_ec2_client")

    # Mock subprocess.run to capture the SSH command
    mock_subprocess = mocker.patch("remote.instance.subprocess.run")

    # Mock describe_instances for get_instance_id
    mock_ec2.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]
    }

    # Mock describe_instance_status for is_instance_running
    mock_ec2.return_value.describe_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    # Call connect with --key option
    runner.invoke(app, ["connect", "test-instance", "--key", str(key_file)])

    # Verify subprocess.run was called
    mock_subprocess.assert_called_once()

    # Get the actual SSH command that was called
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the key option is included
    assert "-i" in ssh_command
    assert str(key_file) in ssh_command
    assert "ssh" in ssh_command
    assert "ubuntu@ec2-123-45-67-89.compute-1.amazonaws.com" in ssh_command


def test_connect_uses_accept_new_by_default(mocker):
    """Test that SSH uses StrictHostKeyChecking=accept-new by default (more secure)."""
    mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
    mock_subprocess = mocker.patch("remote.instance.subprocess.run")

    mock_ec2.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]
    }
    mock_ec2.return_value.describe_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    runner.invoke(app, ["connect", "test-instance"])

    mock_subprocess.assert_called_once()
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the default uses accept-new (secure option)
    assert "StrictHostKeyChecking=accept-new" in ssh_command


def test_connect_with_no_strict_host_key_flag(mocker):
    """Test that --no-strict-host-key disables strict host key checking."""
    mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
    mock_subprocess = mocker.patch("remote.instance.subprocess.run")

    mock_ec2.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]
    }
    mock_ec2.return_value.describe_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    runner.invoke(app, ["connect", "test-instance", "--no-strict-host-key"])

    mock_subprocess.assert_called_once()
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the flag uses 'no' (legacy behavior)
    assert "StrictHostKeyChecking=no" in ssh_command


def test_connect_with_short_form_no_strict_host_key_flag(mocker):
    """Test that -S short form disables strict host key checking."""
    mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
    mock_subprocess = mocker.patch("remote.instance.subprocess.run")

    mock_ec2.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]
    }
    mock_ec2.return_value.describe_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    runner.invoke(app, ["connect", "test-instance", "-S"])

    mock_subprocess.assert_called_once()
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the short form -S works the same as --no-strict-host-key
    assert "StrictHostKeyChecking=no" in ssh_command


def test_connect_uses_ssh_key_from_config(mocker):
    """Test that connect uses ssh_key from config when --key is not provided."""
    mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
    mock_subprocess = mocker.patch("remote.instance.subprocess.run")
    mock_config = mocker.patch("remote.instance.config_manager")

    mock_ec2.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]
    }
    mock_ec2.return_value.describe_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    # Configure mock to return ssh_key from config
    mock_config.get_value.return_value = "/home/user/.ssh/config-key.pem"

    runner.invoke(app, ["connect", "test-instance"])

    mock_subprocess.assert_called_once()
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the key from config is included
    assert "-i" in ssh_command
    assert "/home/user/.ssh/config-key.pem" in ssh_command


def test_connect_key_option_overrides_config(mocker, tmp_path):
    """Test that --key option takes precedence over config ssh_key."""
    # Create temporary key files
    explicit_key = tmp_path / "explicit-key.pem"
    explicit_key.touch()
    config_key = tmp_path / "config-key.pem"
    config_key.touch()

    mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
    mock_subprocess = mocker.patch("remote.instance.subprocess.run")
    mock_config = mocker.patch("remote.instance.config_manager")

    mock_ec2.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]
    }
    mock_ec2.return_value.describe_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    # Configure mock to return ssh_key from config
    mock_config.get_value.return_value = str(config_key)

    # Pass --key option explicitly
    runner.invoke(app, ["connect", "test-instance", "--key", str(explicit_key)])

    mock_subprocess.assert_called_once()
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the explicit key is used, not the config key
    assert "-i" in ssh_command
    assert str(explicit_key) in ssh_command
    assert str(config_key) not in ssh_command

    # Verify get_value was NOT called for ssh_key since --key was provided
    # (The config is checked only when key is not provided)
    mock_config.get_value.assert_not_called()


def test_connect_no_key_when_not_in_config(mocker):
    """Test that connect works without -i flag when no key is provided or configured."""
    mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
    mock_subprocess = mocker.patch("remote.instance.subprocess.run")
    mock_config = mocker.patch("remote.instance.config_manager")

    mock_ec2.return_value.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]
    }
    mock_ec2.return_value.describe_instance_status.return_value = {
        "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
    }

    # Configure mock to return None (no ssh_key in config)
    mock_config.get_value.return_value = None

    runner.invoke(app, ["connect", "test-instance"])

    mock_subprocess.assert_called_once()
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify no -i flag is included
    assert "-i" not in ssh_command


# ============================================================================
# SSH Error Handling Tests (Issue 14)
# ============================================================================


class TestSSHErrorHandling:
    """Test SSH subprocess error handling in the connect command."""

    def test_connect_ssh_nonzero_exit_code(self, mocker):
        """Test that SSH connection failure with non-zero exit code is handled."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock subprocess.run to return non-zero exit code
        mock_result = mocker.MagicMock()
        mock_result.returncode = 255
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["connect", "test-instance"])

        assert result.exit_code == 255
        assert "SSH connection failed with exit code 255" in result.stdout

    def test_connect_ssh_client_not_found(self, mocker):
        """Test that missing SSH client is handled gracefully."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock subprocess.run to raise FileNotFoundError
        mock_subprocess.side_effect = FileNotFoundError("ssh not found")

        result = runner.invoke(app, ["connect", "test-instance"])

        assert result.exit_code == 1
        assert "SSH client not found" in result.stdout
        assert "Please install OpenSSH" in result.stdout

    def test_connect_ssh_os_error(self, mocker):
        """Test that OS errors during SSH connection are handled."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock subprocess.run to raise OSError
        mock_subprocess.side_effect = OSError("Connection refused")

        result = runner.invoke(app, ["connect", "test-instance"])

        assert result.exit_code == 1
        assert "SSH connection error" in result.stdout
        assert "Connection refused" in result.stdout

    def test_connect_ssh_success(self, mocker):
        """Test that successful SSH connection exits cleanly."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock subprocess.run to return success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["connect", "test-instance"])

        assert result.exit_code == 0
        assert "SSH connection failed" not in result.stdout

    def test_connect_no_public_dns(self, mocker):
        """Test that missing public DNS is handled in connect command (Issue 261)."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "",  # No public DNS
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        result = runner.invoke(app, ["connect", "test-instance"])

        assert result.exit_code == 1
        assert "has no public DNS" in result.stdout


# ============================================================================
# Issue 39: Scheduled Shutdown Tests
# ============================================================================


class TestScheduledShutdown:
    """Tests for scheduled instance shutdown functionality."""

    def test_stop_with_stop_in_option_schedules_shutdown(self, mocker):
        """Test that --stop-in option schedules shutdown via SSH."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        # Mock instance lookup
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock config values
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # Mock subprocess success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "3h"])

        assert result.exit_code == 0
        assert "will shut down in 3h" in result.stdout

        # Verify SSH was called twice: first to cancel any existing shutdown, then to schedule new one
        assert mock_subprocess.call_count == 2
        # The second call should be the shutdown schedule command
        ssh_command = mock_subprocess.call_args_list[1][0][0]
        assert "ssh" in ssh_command
        assert "sudo shutdown -h +180" in ssh_command

    def test_stop_with_stop_in_option_invalid_duration(self, mocker):
        """Test that --stop-in option with invalid duration shows error."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mocker.patch("remote.instance.is_instance_running", return_value=True)

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "invalid"])

        assert result.exit_code == 1
        assert "Invalid duration format" in result.stdout

    def test_stop_with_stop_in_option_not_running(self, mocker):
        """Test that --stop-in option on stopped instance shows warning."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mocker.patch("remote.instance.is_instance_running", return_value=False)

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "3h"])

        assert result.exit_code == 0
        assert "is not running" in result.stdout
        assert "cannot schedule shutdown" in result.stdout

    def test_stop_with_cancel_option(self, mocker):
        """Test that --cancel option cancels scheduled shutdown."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        # Mock instance lookup
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock config values
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # Mock subprocess success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["stop", "test-instance", "--cancel"])

        assert result.exit_code == 0
        assert "Cancelled scheduled shutdown" in result.stdout

        # Verify SSH command was called with shutdown -c
        mock_subprocess.assert_called_once()
        ssh_command = mock_subprocess.call_args[0][0]
        assert "sudo shutdown -c" in ssh_command

    def test_stop_with_cancel_not_running(self, mocker):
        """Test that --cancel on stopped instance shows warning."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mocker.patch("remote.instance.is_instance_running", return_value=False)

        result = runner.invoke(app, ["stop", "test-instance", "--cancel"])

        assert result.exit_code == 0
        assert "is not running" in result.stdout
        assert "cannot cancel shutdown" in result.stdout


class TestStartWithStopIn:
    """Tests for start command with --stop-in option."""

    def test_start_with_stop_in_option_invalid_duration(self, mocker):
        """Test that --stop-in option with invalid duration fails early."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-0123456789abcdef0"),
        )
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

        result = runner.invoke(app, ["start", "test-instance", "--stop-in", "bad"])

        assert result.exit_code == 1
        assert "Invalid duration format" in result.stdout

    def test_start_with_stop_in_already_running(self, mocker):
        """Test that --stop-in on running instance still schedules shutdown."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        # Mock instance already running
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # Mock subprocess success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["start", "test-instance", "--stop-in", "2h"])

        assert result.exit_code == 0
        assert "already running" in result.stdout
        assert "Scheduling automatic shutdown" in result.stdout
        assert "will shut down in 2h" in result.stdout


class TestScheduledShutdownSSHErrors:
    """Tests for SSH error handling in scheduled shutdown."""

    def test_schedule_shutdown_ssh_timeout(self, mocker):
        """Test that SSH timeout is handled gracefully."""
        import subprocess

        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # Mock subprocess timeout
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=30)

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "1h"])

        assert result.exit_code == 1
        assert "timed out" in result.stdout

    def test_schedule_shutdown_no_ssh_client(self, mocker):
        """Test that missing SSH client is handled."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # Mock SSH not found
        mock_subprocess.side_effect = FileNotFoundError("ssh not found")

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "1h"])

        assert result.exit_code == 1
        assert "SSH client not found" in result.stdout

    def test_schedule_shutdown_no_public_dns(self, mocker):
        """Test that missing public DNS is handled."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_config = mocker.patch("remote.instance.config_manager")

        # Instance has no public DNS
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "",  # No public DNS
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "1h"])

        assert result.exit_code == 1
        assert "has no public DNS" in result.stdout

    def test_schedule_shutdown_uses_config_ssh_key(self, mocker):
        """Test that SSH key from config is used."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Return SSH key from config
        def get_config_value(key):
            if key == "ssh_user":
                return "ec2-user"
            elif key == "ssh_key_path":
                return "/path/to/key.pem"
            return None

        mock_config.get_value.side_effect = get_config_value

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "30m"])

        assert result.exit_code == 0

        # Verify SSH command includes the key
        ssh_command = mock_subprocess.call_args[0][0]
        assert "-i" in ssh_command
        assert "/path/to/key.pem" in ssh_command
        assert "ec2-user@" in ssh_command[-2]  # User from config


class TestConcurrentShutdownValidation:
    """Tests for issue #203: concurrent shutdown validation."""

    def test_schedule_shutdown_cancels_existing_before_new(self, mocker):
        """Test that scheduling a new shutdown cancels any existing shutdown first."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # Mock subprocess calls - first for cancel, second for new shutdown
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "1h"])

        assert result.exit_code == 0

        # Verify subprocess was called twice: once for cancel, once for new shutdown
        assert mock_subprocess.call_count == 2

        # First call should be the cancel command
        first_call_args = mock_subprocess.call_args_list[0][0][0]
        assert "shutdown -c" in first_call_args[-1]

        # Second call should be the new shutdown schedule
        second_call_args = mock_subprocess.call_args_list[1][0][0]
        assert "shutdown -h +60" in second_call_args[-1]

    def test_schedule_shutdown_reports_cancelled_existing(self, mocker):
        """Test that user is notified when an existing shutdown is cancelled."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # Mock the first call (cancel) to indicate a shutdown was cancelled
        mock_cancel_result = mocker.MagicMock()
        mock_cancel_result.returncode = 0
        mock_cancel_result.stderr = ""
        mock_cancel_result.stdout = "Shutdown cancelled"

        # Mock the second call (new shutdown) to succeed
        mock_schedule_result = mocker.MagicMock()
        mock_schedule_result.returncode = 0
        mock_schedule_result.stderr = ""
        mock_schedule_result.stdout = ""

        mock_subprocess.side_effect = [mock_cancel_result, mock_schedule_result]

        result = runner.invoke(app, ["stop", "test-instance", "--stop-in", "30m"])

        assert result.exit_code == 0
        assert "Cancelled existing scheduled shutdown" in result.stdout


# ============================================================================
# Issue 41: Instance List Cost Flag Tests
# ============================================================================


class TestInstanceListCostFlag:
    """Tests for the --cost flag on instance ls command."""

    def test_list_shows_cost_columns_with_cost_flag(self, mocker):
        """Test that --cost flag adds uptime, hourly rate, and estimated cost columns."""
        import datetime

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        launch_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "running", "Code": 16},
                                "LaunchTime": launch_time,
                                "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        # Mock pricing
        mocker.patch(
            "remote.instance.get_instance_price_with_fallback", return_value=(0.0104, False)
        )

        result = runner.invoke(app, ["list", "--cost"])

        assert result.exit_code == 0
        # Verify cost-related columns are present
        assert "Uptime" in result.stdout
        assert "$/hr" in result.stdout
        assert "Est. Cost" in result.stdout
        # Verify instance data is present
        assert "test-instance" in result.stdout
        assert "i-0123456789abcdef0" in result.stdout

    def test_list_shows_cost_columns_with_short_flag(self, mocker):
        """Test that -c short flag adds cost columns."""
        import datetime

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        launch_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "running", "Code": 16},
                                "LaunchTime": launch_time,
                                "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        mocker.patch(
            "remote.instance.get_instance_price_with_fallback", return_value=(0.0104, False)
        )

        result = runner.invoke(app, ["list", "-c"])

        assert result.exit_code == 0
        assert "Uptime" in result.stdout
        assert "$/hr" in result.stdout
        assert "Est. Cost" in result.stdout

    def test_list_hides_cost_columns_by_default(self, mocker):
        """Test that cost columns are not shown by default (without --cost flag)."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Uptime" not in result.stdout
        assert "$/hr" not in result.stdout
        assert "Est. Cost" not in result.stdout

    def test_list_cost_shows_uptime_and_estimated_cost(self, mocker):
        """Test that cost flag shows actual uptime and calculated estimated cost."""
        import datetime

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Instance running for 2 hours
        launch_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "running", "Code": 16},
                                "LaunchTime": launch_time,
                                "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        # Mock $0.01/hr pricing
        mocker.patch("remote.instance.get_instance_price_with_fallback", return_value=(0.01, False))

        result = runner.invoke(app, ["list", "--cost"])

        assert result.exit_code == 0
        # Check uptime is shown (approximately 2h)
        assert "2h" in result.stdout
        # Check hourly rate is shown
        assert "$0.01" in result.stdout
        # Check estimated cost (2 hours * $0.01 = $0.02)
        assert "$0.02" in result.stdout

    def test_list_cost_handles_stopped_instance(self, mocker):
        """Test that cost flag shows dash for stopped instances."""

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "stopped", "Code": 80},
                                "PublicDnsName": "",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        result = runner.invoke(app, ["list", "--cost"])

        assert result.exit_code == 0
        # Stopped instances should show dash for uptime and cost
        assert "stopped" in result.stdout

    def test_list_cost_handles_unavailable_pricing(self, mocker):
        """Test that cost flag handles unavailable pricing gracefully."""
        import datetime

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        launch_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "InstanceType": "t3.micro",
                                "State": {"Name": "running", "Code": 16},
                                "LaunchTime": launch_time,
                                "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        # Mock pricing to return None
        mocker.patch("remote.instance.get_instance_price_with_fallback", return_value=(None, False))

        result = runner.invoke(app, ["list", "--cost"])

        assert result.exit_code == 0
        # Should show "-" for unavailable pricing
        assert "-" in result.stdout

    def test_list_cost_does_not_call_pricing_without_flag(self, mocker):
        """Test that pricing API is not called without --cost flag."""
        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        mock_get_price = mocker.patch("remote.instance.get_instance_price_with_fallback")

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        mock_get_price.assert_not_called()

    def test_list_cost_shows_fallback_indicator_when_region_not_mapped(self, mocker):
        """Test that prices show asterisk and footnote when fallback pricing is used."""
        import datetime

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        launch_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "State": {"Name": "running"},
                                "InstanceType": "t2.micro",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                                "LaunchTime": launch_time,
                                "PublicDnsName": "ec2.test.amazonaws.com",
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        # Mock pricing to return fallback (used_fallback=True)
        mocker.patch(
            "remote.instance.get_instance_price_with_fallback", return_value=(0.0116, True)
        )

        result = runner.invoke(app, ["list", "--cost"])

        assert result.exit_code == 0
        # Should show asterisk on price columns
        assert "$0.01*" in result.stdout
        # Should show footnote explaining the asterisk
        assert "Estimated price" in result.stdout
        assert "region pricing unavailable" in result.stdout

    def test_list_cost_no_fallback_indicator_when_region_mapped(self, mocker):
        """Test that no asterisk or footnote shown when region pricing is available."""
        import datetime

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        launch_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "State": {"Name": "running"},
                                "InstanceType": "t2.micro",
                                "Tags": [{"Key": "Name", "Value": "test-instance"}],
                                "LaunchTime": launch_time,
                                "PublicDnsName": "ec2.test.amazonaws.com",
                            }
                        ]
                    }
                ]
            }
        ]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        # Mock pricing to return without fallback (used_fallback=False)
        mocker.patch(
            "remote.instance.get_instance_price_with_fallback", return_value=(0.0116, False)
        )

        result = runner.invoke(app, ["list", "--cost"])

        assert result.exit_code == 0
        # Should show price without asterisk
        assert "$0.01" in result.stdout
        # Should NOT show footnote
        assert "Estimated price" not in result.stdout
        assert "region pricing unavailable" not in result.stdout


class TestFormatUptime:
    """Tests for format_duration with seconds parameter (uptime formatting)."""

    def test_format_uptime_minutes_only(self):
        """Test formatting uptime with minutes only."""
        from remote.utils import format_duration

        assert format_duration(seconds=300) == "5m"  # 5 minutes
        assert format_duration(seconds=0) == "0m"

    def test_format_uptime_hours_and_minutes(self):
        """Test formatting uptime with hours and minutes."""
        from remote.utils import format_duration

        assert format_duration(seconds=3900) == "1h 5m"  # 1 hour 5 minutes
        assert format_duration(seconds=7200) == "2h"  # 2 hours exactly

    def test_format_uptime_days_hours_minutes(self):
        """Test formatting uptime with days, hours, and minutes."""
        from remote.utils import format_duration

        assert format_duration(seconds=90000) == "1d 1h"  # 25 hours
        assert format_duration(seconds=180000) == "2d 2h"  # 50 hours

    def test_format_uptime_none(self):
        """Test formatting None uptime."""
        from remote.utils import format_duration

        assert format_duration(seconds=None) == "-"

    def test_format_uptime_negative(self):
        """Test formatting negative uptime."""
        from remote.utils import format_duration

        assert format_duration(seconds=-100) == "-"


class TestGetRawLaunchTimes:
    """Tests for the _get_raw_launch_times helper function."""

    def test_get_raw_launch_times_for_running_instance(self):
        """Test that running instances return their launch time."""
        import datetime

        from remote.instance import _get_raw_launch_times

        launch_time = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": launch_time,
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 1
        assert result[0] == launch_time

    def test_get_raw_launch_times_for_stopped_instance(self):
        """Test that stopped instances return None for launch time."""
        from remote.instance import _get_raw_launch_times

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "stopped", "Code": 80},
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 1
        assert result[0] is None

    def test_get_raw_launch_times_skips_nameless_instances(self):
        """Test that instances without Name tag are skipped."""
        import datetime

        from remote.instance import _get_raw_launch_times

        launch_time = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": launch_time,
                        "Tags": [],  # No Name tag
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 0


# ============================================================================
# Issue 46: Connect Stopped Instance Behavior Tests
# ============================================================================


class TestConnectStoppedInstanceBehavior:
    """Tests for connect command behavior when instance is stopped."""

    def test_connect_with_start_flag_auto_starts_instance(self, mocker):
        """Test that --start flag automatically starts a stopped instance."""
        # Need to patch both locations since instance.py imports get_ec2_client at module level
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mocker.patch("remote.instance.get_ec2_client", mock_ec2)
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mocker.patch("remote.instance.time.sleep")

        # Mock instance lookup
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        # Instance starts as stopped, then becomes running after start
        # Need enough responses for:
        # 1. Initial is_instance_running check in connect (stopped)
        # 2. While loop check in connect (stopped)
        # 3. is_instance_running check in _start_instance (stopped - triggers start)
        # 4. Check after start in while loop (running)
        mock_ec2.return_value.describe_instance_status.side_effect = [
            {"InstanceStatuses": []},  # Initial check: stopped
            {"InstanceStatuses": []},  # While loop first check: still not running
            {"InstanceStatuses": []},  # _start_instance check: not running, so actually starts
            {"InstanceStatuses": [{"InstanceState": {"Name": "running"}}]},  # After start: running
        ]

        # Mock subprocess success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["connect", "test-instance", "--start"])

        assert result.exit_code == 0
        assert "is not running" in result.stdout
        assert "trying to start it" in result.stdout

    def test_connect_with_no_start_flag_fails_immediately(self, mocker):
        """Test that --no-start flag fails immediately when instance is stopped."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")

        # Mock instance lookup - stopped
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped", "Code": 80},
                            "PublicDnsName": "",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {"InstanceStatuses": []}

        result = runner.invoke(app, ["connect", "test-instance", "--no-start"])

        assert result.exit_code == 1
        assert "is not running" in result.stdout
        assert "Use --start to automatically start" in result.stdout

    def test_connect_mutually_exclusive_start_no_start(self, mocker):
        """Test that --start and --no-start flags are mutually exclusive.

        Validation now happens at parse time via callback, returning exit code 2
        (standard CLI usage error) instead of 1.
        """
        # No AWS mocking needed - validation happens before instance resolution
        result = runner.invoke(app, ["connect", "test-instance", "--start", "--no-start"])

        assert result.exit_code == 2  # CLI usage error
        # Check for key parts of the error message (Rich box may wrap text)
        assert "--start" in result.output
        assert "--no-start" in result.output
        assert "Cannot use both" in result.output

    def test_connect_non_interactive_without_flags_fails(self, mocker):
        """Test that non-interactive mode without flags fails with helpful message."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mocker.patch("remote.instance.sys.stdin.isatty", return_value=False)

        # Mock instance lookup - stopped
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped", "Code": 80},
                            "PublicDnsName": "",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {"InstanceStatuses": []}

        result = runner.invoke(app, ["connect", "test-instance"])

        assert result.exit_code == 1
        assert "is not running" in result.stdout
        assert "Use --start to automatically start" in result.stdout

    def test_connect_running_instance_ignores_start_flag(self, mocker):
        """Test that --start flag is ignored when instance is already running."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        # Mock instance lookup - already running
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock subprocess success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["connect", "test-instance", "--start"])

        assert result.exit_code == 0
        # Should not mention starting
        assert "trying to start it" not in result.stdout

    def test_connect_running_instance_ignores_no_start_flag(self, mocker):
        """Test that --no-start flag is ignored when instance is already running."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        # Mock instance lookup - already running
        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Mock subprocess success
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["connect", "test-instance", "--no-start"])

        assert result.exit_code == 0


# ============================================================================
# Exec Command Tests
# ============================================================================


class TestExecCommand:
    """Tests for the 'remote exec' command."""

    def test_exec_runs_command_on_running_instance(self, mocker):
        """Test that exec runs a command on a running instance and returns output."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "command output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["exec", "test-instance", "ls", "-la"])

        assert result.exit_code == 0
        mock_subprocess.assert_called_once()

        # Verify the SSH command includes the remote command
        ssh_command = mock_subprocess.call_args[0][0]
        assert "ssh" in ssh_command
        assert "ls" in ssh_command
        assert "-la" in ssh_command

    def test_exec_fails_when_no_command_provided(self, mocker):
        """Test that exec fails when no command is provided."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
        mocker.patch("remote.instance.is_instance_running", return_value=True)

        result = runner.invoke(app, ["exec", "test-instance"])

        assert result.exit_code == 1
        assert "No command specified" in result.stdout

    def test_exec_fails_when_instance_not_found(self, mocker):
        """Test that exec fails when instance doesn't exist."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2.return_value.describe_instances.return_value = {"Reservations": []}

        result = runner.invoke(app, ["exec", "nonexistent-instance", "ls"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_exec_with_no_start_flag_fails_when_stopped(self, mocker):
        """Test that --no-start flag fails immediately when instance is stopped."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped", "Code": 80},
                            "PublicDnsName": "",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {"InstanceStatuses": []}

        result = runner.invoke(app, ["exec", "test-instance", "--no-start", "ls"])

        assert result.exit_code == 1
        assert "not running" in result.stdout
        assert "--start" in result.stdout

    def test_exec_passes_through_remote_command_exit_code(self, mocker):
        """Test that exec returns the remote command's exit code."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        # Remote command fails with exit code 42
        mock_result = mocker.MagicMock()
        mock_result.returncode = 42
        mock_result.stdout = ""
        mock_result.stderr = "command failed"
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["exec", "test-instance", "exit", "42"])

        assert result.exit_code == 42

    def test_exec_handles_ssh_timeout(self, mocker):
        """Test that exec handles SSH timeout gracefully."""
        import subprocess

        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=30)

        result = runner.invoke(app, ["exec", "test-instance", "sleep", "1000"])

        assert result.exit_code == 1
        assert "timed out" in result.stdout

    def test_exec_handles_ssh_not_found(self, mocker):
        """Test that exec handles missing SSH client."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_subprocess.side_effect = FileNotFoundError("ssh not found")

        result = runner.invoke(app, ["exec", "test-instance", "ls"])

        assert result.exit_code == 1
        assert "SSH client not found" in result.stdout

    def test_exec_uses_ssh_key_from_option(self, mocker, tmp_path):
        """Test that --key option adds -i flag to SSH command."""
        # Create a temporary key file (SSH key validation now happens at parse time)
        key_file = tmp_path / "key.pem"
        key_file.touch()

        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Options must come before positional args due to allow_interspersed_args=False
        result = runner.invoke(app, ["exec", "--key", str(key_file), "test-instance", "ls"])

        assert result.exit_code == 0
        ssh_command = mock_subprocess.call_args[0][0]
        assert "-i" in ssh_command
        assert str(key_file) in ssh_command

    def test_exec_uses_ssh_key_from_config(self, mocker):
        """Test that exec uses ssh_key from config when --key is not provided."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_config = mocker.patch("remote.instance.config_manager")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_config.get_value.side_effect = (
            lambda k: "/home/user/.ssh/config-key.pem" if k == "ssh_key_path" else None
        )

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["exec", "test-instance", "ls"])

        assert result.exit_code == 0
        ssh_command = mock_subprocess.call_args[0][0]
        assert "-i" in ssh_command
        assert "/home/user/.ssh/config-key.pem" in ssh_command

    def test_exec_uses_custom_user(self, mocker):
        """Test that --user option is passed to SSH."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Options must come before instance name with allow_interspersed_args=False
        result = runner.invoke(app, ["exec", "--user", "ec2-user", "test-instance", "ls"])

        assert result.exit_code == 0
        ssh_command = mock_subprocess.call_args[0][0]
        assert "ec2-user@" in " ".join(ssh_command)

    def test_exec_uses_custom_timeout(self, mocker):
        """Test that --timeout option is passed to subprocess."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Options must come before instance name with allow_interspersed_args=False
        result = runner.invoke(app, ["exec", "--timeout", "60", "test-instance", "ls"])

        assert result.exit_code == 0
        # Verify timeout was passed to subprocess
        call_kwargs = mock_subprocess.call_args[1]
        assert call_kwargs.get("timeout") == 60

    def test_exec_quiet_mode_shows_only_output(self, mocker):
        """Test that --quiet mode suppresses status messages."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello world"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Options must come before instance name with allow_interspersed_args=False
        result = runner.invoke(app, ["exec", "--quiet", "test-instance", "echo", "hello"])

        assert result.exit_code == 0
        # Should not contain status messages like "Executing" or "Connecting"
        assert "Executing" not in result.stdout
        assert "Connecting" not in result.stdout

    def test_exec_mutually_exclusive_start_no_start(self, mocker):
        """Test that --start and --no-start flags are mutually exclusive.

        Validation now happens at parse time via callback, returning exit code 2
        (standard CLI usage error) instead of 1.
        """
        # No mocking needed - validation happens before instance resolution

        # Options must come before instance name with allow_interspersed_args=False
        result = runner.invoke(app, ["exec", "--start", "--no-start", "test-instance", "ls"])

        assert result.exit_code == 2  # CLI usage error
        # Check for key parts of the error message (Rich box may wrap text)
        assert "--start" in result.output
        assert "--no-start" in result.output
        assert "Cannot use both" in result.output

    def test_exec_uses_default_instance_when_name_not_resolved(self, mocker):
        """Test that exec uses default instance when first arg doesn't resolve to an instance."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_get_instance_name = mocker.patch(
            "remote.instance.get_instance_name", return_value="default-instance"
        )

        # First call with "ls" fails (not an instance), second call with "default-instance" succeeds
        def describe_instances_side_effect(**kwargs):
            filters = kwargs.get("Filters", [])

            # Check if looking for "ls" (should fail) or "default-instance" (should succeed)
            if filters:
                name_filter = next((f for f in filters if f["Name"] == "tag:Name"), None)
                if name_filter and "ls" in name_filter["Values"]:
                    return {"Reservations": []}

            return {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-0123456789abcdef0",
                                "State": {"Name": "running", "Code": 16},
                                "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                                "Tags": [{"Key": "Name", "Value": "default-instance"}],
                            }
                        ]
                    }
                ]
            }

        mock_ec2.return_value.describe_instances.side_effect = describe_instances_side_effect
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # When only "ls" is provided and it doesn't resolve as an instance,
        # it should be treated as the command and default instance should be used
        result = runner.invoke(app, ["exec", "ls"])

        assert result.exit_code == 0
        mock_get_instance_name.assert_called_once()
        # Verify the command was "ls"
        ssh_command = mock_subprocess.call_args[0][0]
        assert "ls" in ssh_command

    def test_exec_handles_os_error(self, mocker):
        """Test that exec handles OS errors gracefully."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_subprocess.side_effect = OSError("Connection refused")

        result = runner.invoke(app, ["exec", "test-instance", "ls"])

        assert result.exit_code == 1
        assert "SSH connection error" in result.stdout

    def test_exec_prints_stdout(self, mocker):
        """Test that exec prints command stdout."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }
        mock_ec2.return_value.describe_instance_status.return_value = {
            "InstanceStatuses": [{"InstanceState": {"Name": "running"}}]
        }

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file1.txt\nfile2.txt\n"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = runner.invoke(app, ["exec", "test-instance", "ls"])

        assert result.exit_code == 0
        assert "file1.txt" in result.stdout
        assert "file2.txt" in result.stdout

    def test_exec_with_start_flag_auto_starts_instance(self, mocker):
        """Test that --start flag automatically starts a stopped instance."""
        mock_ec2 = mocker.patch("remote.utils.get_ec2_client")
        mocker.patch("remote.instance.get_ec2_client", mock_ec2)
        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mocker.patch("remote.instance.time.sleep")

        mock_ec2.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "running", "Code": 16},
                            "PublicDnsName": "ec2-123-45-67-89.compute-1.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        # Instance starts as stopped, then becomes running
        mock_ec2.return_value.describe_instance_status.side_effect = [
            {"InstanceStatuses": []},  # Initial check: stopped
            {"InstanceStatuses": []},  # While loop check: stopped
            {"InstanceStatuses": []},  # _start_instance check
            {"InstanceStatuses": [{"InstanceState": {"Name": "running"}}]},  # After start
        ]

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # Options must come before instance name with allow_interspersed_args=False
        result = runner.invoke(app, ["exec", "--start", "test-instance", "ls"])

        assert result.exit_code == 0
        # Verify start_instances was called
        mock_ec2.return_value.start_instances.assert_called()


# ============================================================================
# Launch Command Tests
# ============================================================================


class TestLaunchCommand:
    """Test the 'remote launch' command behavior."""

    def test_launch_with_yes_flag_requires_launch_template(self, mocker):
        """Should error when --yes is used without --launch-template."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None

        result = runner.invoke(app, ["launch", "--name", "test-instance", "--yes"])

        assert result.exit_code == 1
        assert "--launch-template is required when using --yes" in result.stdout

    def test_launch_with_yes_flag_requires_name(self, mocker):
        """Should error when --yes is used without --name."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None
        mocker.patch(
            "remote.instance_resolver.get_launch_template_id",
            return_value="lt-0123456789abcdef0",
        )

        result = runner.invoke(app, ["launch", "--launch-template", "my-template", "--yes"])

        assert result.exit_code == 1
        assert "--name is required when using --yes" in result.stdout

    def test_launch_with_yes_flag_success(self, mocker):
        """Should launch instance without prompts when --yes is used with all required params."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None
        mocker.patch(
            "remote.instance_resolver.get_launch_template_id",
            return_value="lt-0123456789abcdef0",
        )
        mock_ec2 = mocker.patch("remote.instance_resolver.get_ec2_client")
        mock_ec2.return_value.run_instances.return_value = {
            "Instances": [
                {
                    "InstanceId": "i-0123456789abcdef0",
                    "InstanceType": "t3.micro",
                }
            ]
        }

        result = runner.invoke(
            app,
            [
                "launch",
                "--name",
                "test-instance",
                "--launch-template",
                "my-template",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        mock_ec2.return_value.run_instances.assert_called_once()
        assert "Instance Launched" in result.stdout
        assert "i-0123456789abcdef0" in result.stdout

    def test_launch_with_yes_flag_uses_default_template(self, mocker):
        """Should use default template from config when --yes is used."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = "default-template"
        mocker.patch(
            "remote.instance_resolver.get_launch_template_id",
            return_value="lt-0123456789abcdef0",
        )
        mock_ec2 = mocker.patch("remote.instance_resolver.get_ec2_client")
        mock_ec2.return_value.run_instances.return_value = {
            "Instances": [
                {
                    "InstanceId": "i-0123456789abcdef0",
                    "InstanceType": "t3.micro",
                }
            ]
        }

        result = runner.invoke(
            app,
            ["launch", "--name", "test-instance", "--yes"],
        )

        assert result.exit_code == 0
        assert "Using default template: default-template" in result.stdout
        mock_ec2.return_value.run_instances.assert_called_once()

    def test_launch_interactive_template_selection(self, mocker):
        """Should allow interactive template selection (lines 154-200)."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None  # No default template

        # Mock get_launch_templates to return available templates
        mocker.patch(
            "remote.instance_resolver.get_launch_templates",
            return_value=[
                {
                    "LaunchTemplateId": "lt-001",
                    "LaunchTemplateName": "web-server",
                    "LatestVersionNumber": 2,
                },
                {
                    "LaunchTemplateId": "lt-002",
                    "LaunchTemplateName": "db-server",
                    "LatestVersionNumber": 1,
                },
            ],
        )

        mocker.patch(
            "remote.instance_resolver.get_launch_template_id",
            return_value="lt-001",
        )

        mock_ec2 = mocker.patch("remote.instance_resolver.get_ec2_client")
        mock_ec2.return_value.run_instances.return_value = {
            "Instances": [{"InstanceId": "i-new123", "InstanceType": "t3.micro"}]
        }

        # User selects template 1, then provides instance name
        result = runner.invoke(
            app,
            ["launch"],
            input="1\nmy-new-instance\n",
        )

        assert result.exit_code == 0
        assert "web-server selected" in result.stdout
        mock_ec2.return_value.run_instances.assert_called_once()

    def test_launch_no_templates_found(self, mocker):
        """Should error when no launch templates exist (lines 158-160)."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None

        mocker.patch("remote.instance_resolver.get_launch_templates", return_value=[])

        result = runner.invoke(app, ["launch"])

        assert result.exit_code == 1
        assert "No launch templates found" in result.stdout

    def test_launch_empty_template_number_input(self, mocker):
        """Should error on empty template number (lines 184-186)."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None

        mocker.patch(
            "remote.instance_resolver.get_launch_templates",
            return_value=[
                {
                    "LaunchTemplateId": "lt-001",
                    "LaunchTemplateName": "test",
                    "LatestVersionNumber": 1,
                }
            ],
        )

        # User enters whitespace-only for template number
        result = runner.invoke(app, ["launch"], input="   \n")

        assert result.exit_code == 1
        assert "Template number cannot be empty" in result.stdout

    def test_launch_invalid_template_number(self, mocker):
        """Should error on invalid template number (lines 192-194)."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None

        mocker.patch(
            "remote.instance_resolver.get_launch_templates",
            return_value=[
                {
                    "LaunchTemplateId": "lt-001",
                    "LaunchTemplateName": "test",
                    "LatestVersionNumber": 1,
                }
            ],
        )

        # User enters out-of-range template number
        result = runner.invoke(app, ["launch"], input="99\n")

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_launch_interactive_name_prompt(self, mocker):
        """Should prompt for name and provide suggestion (lines 213-222)."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None

        mocker.patch(
            "remote.instance_resolver.get_launch_template_id",
            return_value="lt-001",
        )

        mock_ec2 = mocker.patch("remote.instance_resolver.get_ec2_client")
        mock_ec2.return_value.run_instances.return_value = {
            "Instances": [{"InstanceId": "i-new123", "InstanceType": "t3.micro"}]
        }

        # User provides launch template but not name, then enters name at prompt
        result = runner.invoke(
            app,
            ["launch", "--launch-template", "my-template"],
            input="custom-name\n",
        )

        assert result.exit_code == 0
        mock_ec2.return_value.run_instances.assert_called_once()

    def test_launch_empty_prompted_name(self, mocker):
        """Should error when user enters empty name at prompt (lines 220-222)."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None

        mocker.patch(
            "remote.instance_resolver.get_launch_template_id",
            return_value="lt-001",
        )

        # User provides empty name at prompt
        result = runner.invoke(
            app,
            ["launch", "--launch-template", "my-template"],
            input="   \n",  # Whitespace-only name
        )

        assert result.exit_code == 1
        assert "Instance name cannot be empty" in result.stdout

    def test_launch_no_instances_returned(self, mocker):
        """Should warn when no instances returned from launch (lines 245-246)."""
        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_value.return_value = None

        mocker.patch(
            "remote.instance_resolver.get_launch_template_id",
            return_value="lt-001",
        )

        mock_ec2 = mocker.patch("remote.instance_resolver.get_ec2_client")
        mock_ec2.return_value.run_instances.return_value = {
            "Instances": []  # Empty - no instances returned
        }

        result = runner.invoke(
            app,
            ["launch", "--name", "test", "--launch-template", "my-template", "--yes"],
        )

        assert result.exit_code == 0
        assert "No instance information returned" in result.stdout


class TestResolveInstanceWithoutName:
    """Test resolve_instance when instance_name is None (line 80)."""

    def test_should_use_default_instance_when_none_provided(self, mocker):
        """Should call get_instance_name when instance_name is None (line 80)."""
        from remote.instance_resolver import resolve_instance

        mock_config = mocker.patch("remote.instance_resolver.config_manager")
        mock_config.get_instance_name.return_value = "default-instance"

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-default123",
                            "Tags": [{"Key": "Name", "Value": "default-instance"}],
                        }
                    ]
                }
            ]
        }

        result = resolve_instance()  # No instance_name provided

        assert result == ("default-instance", "i-default123")
        mock_config.get_instance_name.assert_called_once()


# ============================================================================
# Issue #202: Private Function Unit Tests
# ============================================================================


class TestBuildSshCommand:
    """Test the _build_ssh_command() helper function directly."""

    def test_should_return_basic_ssh_command_with_dns_only(self):
        """Should return minimal SSH command with just DNS and default user."""
        from remote.instance import _build_ssh_command
        from remote.settings import DEFAULT_SSH_USER

        result = _build_ssh_command("ec2-1-2-3-4.compute-1.amazonaws.com")

        assert result[0] == "ssh"
        assert "-o" in result
        assert "StrictHostKeyChecking=accept-new" in result
        assert "BatchMode=yes" in result
        assert "ConnectTimeout=10" in result
        assert f"{DEFAULT_SSH_USER}@ec2-1-2-3-4.compute-1.amazonaws.com" in result

    def test_should_include_key_when_provided(self):
        """Should add -i flag with key path when key is provided."""
        from remote.instance import _build_ssh_command

        result = _build_ssh_command(
            "ec2-1-2-3-4.compute-1.amazonaws.com",
            key="/path/to/key.pem",
        )

        assert "-i" in result
        key_index = result.index("-i")
        assert result[key_index + 1] == "/path/to/key.pem"

    def test_should_use_custom_user_when_provided(self):
        """Should use provided username instead of default."""
        from remote.instance import _build_ssh_command

        result = _build_ssh_command(
            "ec2-1-2-3-4.compute-1.amazonaws.com",
            user="ec2-user",
        )

        assert "ec2-user@ec2-1-2-3-4.compute-1.amazonaws.com" in result

    def test_should_use_strict_host_key_no_when_flag_set(self):
        """Should use StrictHostKeyChecking=no when no_strict_host_key is True."""
        from remote.instance import _build_ssh_command

        result = _build_ssh_command(
            "ec2-1-2-3-4.compute-1.amazonaws.com",
            no_strict_host_key=True,
        )

        assert "StrictHostKeyChecking=no" in result
        assert "StrictHostKeyChecking=accept-new" not in result

    def test_should_add_verbose_flag_when_requested(self):
        """Should add -v flag when verbose is True."""
        from remote.instance import _build_ssh_command

        result = _build_ssh_command(
            "ec2-1-2-3-4.compute-1.amazonaws.com",
            verbose=True,
        )

        assert "-v" in result

    def test_should_omit_batch_mode_and_timeout_for_interactive(self):
        """Should omit BatchMode and ConnectTimeout for interactive sessions."""
        from remote.instance import _build_ssh_command

        result = _build_ssh_command(
            "ec2-1-2-3-4.compute-1.amazonaws.com",
            interactive=True,
        )

        result_str = " ".join(result)
        assert "BatchMode" not in result_str
        assert "ConnectTimeout" not in result_str

    def test_should_add_port_forwarding_when_specified(self):
        """Should add -L flag with port forwarding specification."""
        from remote.instance import _build_ssh_command

        result = _build_ssh_command(
            "ec2-1-2-3-4.compute-1.amazonaws.com",
            port_forward="8080:localhost:80",
        )

        assert "-L" in result
        l_index = result.index("-L")
        assert result[l_index + 1] == "8080:localhost:80"

    def test_should_combine_all_options_correctly(self):
        """Should correctly combine all SSH options."""
        from remote.instance import _build_ssh_command

        result = _build_ssh_command(
            "ec2-1-2-3-4.compute-1.amazonaws.com",
            key="/path/to/key.pem",
            user="admin",
            no_strict_host_key=True,
            verbose=True,
            interactive=True,
            port_forward="3000:localhost:3000",
        )

        assert "-i" in result
        assert "/path/to/key.pem" in result
        assert "-v" in result
        assert "-L" in result
        assert "3000:localhost:3000" in result
        assert "StrictHostKeyChecking=no" in result
        assert "admin@ec2-1-2-3-4.compute-1.amazonaws.com" in result
        # Should NOT have BatchMode/ConnectTimeout due to interactive=True
        result_str = " ".join(result)
        assert "BatchMode" not in result_str


class TestGetSshConfig:
    """Test the get_ssh_config() and reset_ssh_config_cache() functions."""

    def test_should_return_ssh_config_with_user_and_key(self, mocker):
        """Should return SSHConfig with user and key from config manager."""
        from remote.instance import SSHConfig, get_ssh_config, reset_ssh_config_cache

        # Reset cache to ensure fresh config
        reset_ssh_config_cache()

        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = (
            lambda k: "ec2-user" if k == "ssh_user" else "/path/to/key.pem"
        )

        result = get_ssh_config()

        assert isinstance(result, SSHConfig)
        assert result.user == "ec2-user"
        assert result.key_path == "/path/to/key.pem"

    def test_should_use_default_user_when_not_configured(self, mocker):
        """Should use DEFAULT_SSH_USER when ssh_user is not configured."""
        from remote.instance import get_ssh_config, reset_ssh_config_cache
        from remote.settings import DEFAULT_SSH_USER

        reset_ssh_config_cache()

        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.return_value = None

        result = get_ssh_config()

        assert result.user == DEFAULT_SSH_USER
        assert result.key_path is None

    def test_should_cache_config_on_subsequent_calls(self, mocker):
        """Should return cached config on subsequent calls."""
        from remote.instance import get_ssh_config, reset_ssh_config_cache

        reset_ssh_config_cache()

        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        # First call
        result1 = get_ssh_config()
        # Second call
        result2 = get_ssh_config()

        # Should be the same object (cached)
        assert result1 is result2
        # Config should only be read once
        assert mock_config.get_value.call_count == 2  # ssh_user and ssh_key_path

    def test_reset_should_clear_cache(self, mocker):
        """Should clear the cache when reset_ssh_config_cache is called."""
        from remote.instance import get_ssh_config, reset_ssh_config_cache

        reset_ssh_config_cache()

        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "user1" if k == "ssh_user" else None

        # First call
        result1 = get_ssh_config()

        # Reset and change mock
        reset_ssh_config_cache()
        mock_config.get_value.side_effect = lambda k: "user2" if k == "ssh_user" else None

        # Second call after reset
        result2 = get_ssh_config()

        assert result1.user == "user1"
        assert result2.user == "user2"
        assert result1 is not result2


class TestScheduleShutdownDirect:
    """Test the _schedule_shutdown() function directly."""

    def test_should_exit_when_no_public_dns(self, mocker):
        """Should exit with error when instance has no public DNS."""
        import pytest
        import typer

        from remote.instance import _schedule_shutdown

        mocker.patch("remote.instance.get_instance_dns", return_value=None)

        with pytest.raises(typer.Exit) as exc_info:
            _schedule_shutdown("test-instance", "i-123", 60)

        assert exc_info.value.exit_code == 1

    def test_should_cancel_existing_shutdown_first(self, mocker):
        """Should call _cancel_existing_shutdown_silently before scheduling new shutdown."""
        from remote.instance import _schedule_shutdown

        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        mock_cancel = mocker.patch(
            "remote.instance._cancel_existing_shutdown_silently", return_value=False
        )

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        _schedule_shutdown("test-instance", "i-123", 30)

        mock_cancel.assert_called_once()

    def test_should_build_correct_shutdown_command(self, mocker):
        """Should build SSH command with correct shutdown duration."""
        from remote.instance import _schedule_shutdown

        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        mocker.patch("remote.instance._cancel_existing_shutdown_silently", return_value=False)

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        _schedule_shutdown("test-instance", "i-123", 45)

        # Check that subprocess was called with correct shutdown command
        call_args = mock_subprocess.call_args[0][0]
        assert "sudo shutdown -h +45" in call_args[-1]

    def test_should_exit_on_ssh_failure(self, mocker):
        """Should exit with error when SSH command fails."""
        import pytest
        import typer

        from remote.instance import _schedule_shutdown

        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        mocker.patch("remote.instance._cancel_existing_shutdown_silently", return_value=False)

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "SSH error"
        mock_subprocess.return_value = mock_result

        with pytest.raises(typer.Exit) as exc_info:
            _schedule_shutdown("test-instance", "i-123", 30)

        assert exc_info.value.exit_code == 1


class TestCancelScheduledShutdownDirect:
    """Test the _cancel_scheduled_shutdown() function directly."""

    def test_should_exit_when_no_public_dns(self, mocker):
        """Should exit with error when instance has no public DNS."""
        import pytest
        import typer

        from remote.instance import _cancel_scheduled_shutdown

        mocker.patch("remote.instance.get_instance_dns", return_value=None)

        with pytest.raises(typer.Exit) as exc_info:
            _cancel_scheduled_shutdown("test-instance", "i-123")

        assert exc_info.value.exit_code == 1

    def test_should_send_shutdown_cancel_command(self, mocker):
        """Should send 'sudo shutdown -c' via SSH."""
        from remote.instance import _cancel_scheduled_shutdown

        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        _cancel_scheduled_shutdown("test-instance", "i-123")

        call_args = mock_subprocess.call_args[0][0]
        assert "sudo shutdown -c" in call_args[-1]

    def test_should_handle_no_scheduled_shutdown_gracefully(self, mocker):
        """Should print warning when no shutdown is scheduled."""
        from remote.instance import _cancel_scheduled_shutdown

        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "No scheduled shutdown"
        mock_subprocess.return_value = mock_result

        # Should not raise, just print warning
        _cancel_scheduled_shutdown("test-instance", "i-123")

    def test_should_exit_on_unexpected_ssh_error(self, mocker):
        """Should exit with error on unexpected SSH failures."""
        import pytest
        import typer

        from remote.instance import _cancel_scheduled_shutdown

        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mock_config = mocker.patch("remote.instance.config_manager")
        mock_config.get_value.side_effect = lambda k: "ubuntu" if k == "ssh_user" else None

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 255  # SSH connection failure
        mock_result.stderr = "Connection refused"
        mock_subprocess.return_value = mock_result

        with pytest.raises(typer.Exit) as exc_info:
            _cancel_scheduled_shutdown("test-instance", "i-123")

        assert exc_info.value.exit_code == 1


class TestCancelExistingShutdownSilently:
    """Test the _cancel_existing_shutdown_silently() function directly."""

    def test_should_return_true_when_shutdown_cancelled(self, mocker):
        """Should return True when an existing shutdown was cancelled."""
        from remote.instance import SSHConfig, _cancel_existing_shutdown_silently

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Shutdown cancelled"
        mock_subprocess.return_value = mock_result

        ssh_config = SSHConfig(user="ubuntu", key_path=None)
        result = _cancel_existing_shutdown_silently(
            "ec2-1-2-3-4.compute-1.amazonaws.com", ssh_config, "test-instance"
        )

        assert result is True

    def test_should_return_false_when_no_shutdown_to_cancel(self, mocker):
        """Should return False when no shutdown was scheduled."""
        from remote.instance import SSHConfig, _cancel_existing_shutdown_silently

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""  # No output means no shutdown was cancelled
        mock_subprocess.return_value = mock_result

        ssh_config = SSHConfig(user="ubuntu", key_path=None)
        result = _cancel_existing_shutdown_silently(
            "ec2-1-2-3-4.compute-1.amazonaws.com", ssh_config, "test-instance"
        )

        assert result is False

    def test_should_use_provided_ssh_config(self, mocker):
        """Should use the provided SSH config for the command."""
        from remote.instance import SSHConfig, _cancel_existing_shutdown_silently

        mock_subprocess = mocker.patch("remote.instance.subprocess.run")
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_subprocess.return_value = mock_result

        ssh_config = SSHConfig(user="ec2-user", key_path="/path/to/key.pem")
        _cancel_existing_shutdown_silently(
            "ec2-1-2-3-4.compute-1.amazonaws.com", ssh_config, "test-instance"
        )

        call_args = mock_subprocess.call_args[0][0]
        assert "-i" in call_args
        assert "/path/to/key.pem" in call_args
        assert "ec2-user@" in call_args[-2]


class TestBuildStatusTableEdgeCases:
    """Additional edge case tests for _build_status_table()."""

    def test_should_handle_instance_with_no_security_groups(self, mocker):
        """Should handle instance with empty security groups."""
        from rich.panel import Panel

        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t2.micro",
                            "PrivateIpAddress": "10.0.0.1",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [],  # Empty security groups
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        assert isinstance(result, Panel)

    def test_should_handle_instance_with_no_public_dns(self, mocker):
        """Should display dash for missing public DNS."""
        from rich.panel import Panel

        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t2.micro",
                            "PrivateIpAddress": "10.0.0.1",
                            # No PublicDnsName field
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [],
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        assert isinstance(result, Panel)

    def test_should_handle_instance_with_no_launch_time(self, mocker):
        """Should display dash for missing launch time."""
        from rich.panel import Panel

        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t2.micro",
                            "PrivateIpAddress": "10.0.0.1",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [],
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                            # No LaunchTime field
                        }
                    ]
                }
            ]
        }

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        assert isinstance(result, Panel)

    def test_should_show_other_tags_excluding_name(self, mocker):
        """Should display other tags but exclude the Name tag."""
        from rich.panel import Panel

        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "State": {"Name": "stopped"},
                            "InstanceType": "t2.micro",
                            "PrivateIpAddress": "10.0.0.1",
                            "KeyName": "my-key",
                            "Placement": {"AvailabilityZone": "us-east-1a"},
                            "SecurityGroups": [],
                            "Tags": [
                                {"Key": "Name", "Value": "test-instance"},
                                {"Key": "Environment", "Value": "production"},
                                {"Key": "Team", "Value": "platform"},
                            ],
                        }
                    ]
                }
            ]
        }

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        assert isinstance(result, Panel)

    def test_should_raise_for_empty_instances_list(self, mocker):
        """Should raise InstanceNotFoundError when Instances list is empty."""
        import pytest

        from remote.exceptions import InstanceNotFoundError
        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {
            "Reservations": [{"Instances": []}]  # Empty instances
        }

        with pytest.raises(InstanceNotFoundError):
            _build_status_table("test-instance", "i-0123456789abcdef0")


class TestWatchStatusEdgeCases:
    """Additional edge case tests for _watch_status()."""

    def test_should_display_error_panel_on_aws_error(self, mocker):
        """Should display error in panel when AWS error occurs."""
        from remote.exceptions import AWSServiceError
        from remote.instance import _watch_status

        # Mock _build_status_table to raise an error after one successful call
        mock_panel = mocker.MagicMock()
        mocker.patch(
            "remote.instance._build_status_table",
            side_effect=[mock_panel, AWSServiceError("EC2", "describe", "TestError", "Test error")],
        )

        mocker.patch("remote.instance.console")
        mock_live = mocker.patch("remote.instance.Live")
        mock_live.return_value.__enter__ = mocker.Mock(return_value=mock_live.return_value)
        mock_live.return_value.__exit__ = mocker.Mock(return_value=False)

        # Mock time.sleep to raise KeyboardInterrupt after being called
        mocker.patch("remote.instance.time.sleep", side_effect=[None, KeyboardInterrupt])

        try:
            _watch_status("test-instance", "i-0123456789abcdef0", 1)
        except AWSServiceError:
            pass  # Expected

        # Verify update was called with error panel
        assert mock_live.return_value.update.call_count >= 1

    def test_should_re_raise_instance_not_found_error(self, mocker):
        """Should re-raise InstanceNotFoundError after displaying in live view."""
        import pytest

        from remote.exceptions import InstanceNotFoundError
        from remote.instance import _watch_status

        mocker.patch(
            "remote.instance._build_status_table",
            side_effect=InstanceNotFoundError("test-instance"),
        )

        mocker.patch("remote.instance.console")
        mock_live = mocker.patch("remote.instance.Live")
        mock_live.return_value.__enter__ = mocker.Mock(return_value=mock_live.return_value)
        mock_live.return_value.__exit__ = mocker.Mock(return_value=False)

        with pytest.raises(InstanceNotFoundError):
            _watch_status("test-instance", "i-0123456789abcdef0", 1)


class TestEnsureInstanceRunning:
    """Test the _ensure_instance_running() function directly."""

    def test_should_return_immediately_if_instance_running(self, mocker):
        """Should return immediately if instance is already running."""
        from remote.instance import _ensure_instance_running

        mocker.patch("remote.instance.is_instance_running", return_value=True)

        # Should not raise
        _ensure_instance_running("test-instance", "i-123", auto_start=False, no_start=False)

    def test_should_exit_if_no_start_flag_and_not_running(self, mocker):
        """Should exit with error when --no-start is set and instance not running."""
        import pytest
        import typer

        from remote.instance import _ensure_instance_running

        mocker.patch("remote.instance.is_instance_running", return_value=False)

        with pytest.raises(typer.Exit) as exc_info:
            _ensure_instance_running("test-instance", "i-123", auto_start=False, no_start=True)

        assert exc_info.value.exit_code == 1

    def test_should_auto_start_when_flag_set(self, mocker):
        """Should start instance automatically when --start flag is set."""
        from remote.instance import _ensure_instance_running

        # First call returns False (not running), subsequent calls return True
        mocker.patch("remote.instance.is_instance_running", side_effect=[False, False, True])
        mock_start = mocker.patch("remote.instance._start_instance")
        mocker.patch("remote.instance.time.sleep")

        _ensure_instance_running(
            "test-instance", "i-123", auto_start=True, no_start=False, quiet=True
        )

        mock_start.assert_called()

    def test_should_exit_if_non_interactive_without_flags(self, mocker):
        """Should exit when non-interactive and neither start nor no-start flag set."""
        import sys

        import pytest
        import typer

        from remote.instance import _ensure_instance_running

        mocker.patch("remote.instance.is_instance_running", return_value=False)
        mocker.patch.object(sys.stdin, "isatty", return_value=False)

        with pytest.raises(typer.Exit) as exc_info:
            _ensure_instance_running(
                "test-instance",
                "i-123",
                auto_start=False,
                no_start=False,
                allow_interactive=True,
            )

        assert exc_info.value.exit_code == 1

    def test_should_exit_if_start_fails_after_max_attempts(self, mocker):
        """Should exit with error if instance cannot be started after max attempts."""
        import pytest
        import typer

        from remote.instance import _ensure_instance_running

        # Always return False (instance never starts)
        mocker.patch("remote.instance.is_instance_running", return_value=False)
        mocker.patch("remote.instance._start_instance")
        mocker.patch("remote.instance.time.sleep")

        with pytest.raises(typer.Exit) as exc_info:
            _ensure_instance_running("test-instance", "i-123", auto_start=True, no_start=False)

        assert exc_info.value.exit_code == 1


class TestHandleSshErrors:
    """Test the handle_ssh_errors context manager."""

    def test_should_handle_timeout_expired(self, mocker):
        """Should handle subprocess.TimeoutExpired."""
        import subprocess

        import pytest
        import typer

        from remote.instance import handle_ssh_errors

        with pytest.raises(typer.Exit) as exc_info:
            with handle_ssh_errors("Test operation"):
                raise subprocess.TimeoutExpired(cmd="ssh", timeout=30)

        assert exc_info.value.exit_code == 1

    def test_should_handle_file_not_found(self, mocker):
        """Should handle FileNotFoundError (SSH not installed)."""
        import pytest
        import typer

        from remote.instance import handle_ssh_errors

        with pytest.raises(typer.Exit) as exc_info:
            with handle_ssh_errors("Test operation"):
                raise FileNotFoundError("ssh not found")

        assert exc_info.value.exit_code == 1

    def test_should_handle_os_error(self, mocker):
        """Should handle OSError (connection errors)."""
        import pytest
        import typer

        from remote.instance import handle_ssh_errors

        with pytest.raises(typer.Exit) as exc_info:
            with handle_ssh_errors("Test operation"):
                raise OSError("Connection refused")

        assert exc_info.value.exit_code == 1

    def test_should_pass_through_other_exceptions(self):
        """Should not catch exceptions other than SSH-related ones."""
        import pytest

        from remote.instance import handle_ssh_errors

        with pytest.raises(ValueError):
            with handle_ssh_errors("Test operation"):
                raise ValueError("Not an SSH error")


class TestEnsureSshKey:
    """Test the _ensure_ssh_key() function."""

    def test_should_return_provided_key_when_given(self, mocker):
        """Should return the provided key if one is given."""
        from remote.instance import _ensure_ssh_key

        result = _ensure_ssh_key("/provided/key.pem")

        assert result == "/provided/key.pem"

    def test_should_fall_back_to_config_when_no_key(self, mocker):
        """Should fall back to config key when no key provided."""
        from remote.instance import SSHConfig, _ensure_ssh_key, reset_ssh_config_cache

        reset_ssh_config_cache()

        mock_get_config = mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=SSHConfig(user="ubuntu", key_path="/config/key.pem"),
        )

        result = _ensure_ssh_key(None)

        assert result == "/config/key.pem"
        mock_get_config.assert_called_once()

    def test_should_return_none_if_no_key_anywhere(self, mocker):
        """Should return None if no key provided and none in config."""
        from remote.instance import SSHConfig, _ensure_ssh_key, reset_ssh_config_cache

        reset_ssh_config_cache()

        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=SSHConfig(user="ubuntu", key_path=None),
        )

        result = _ensure_ssh_key(None)

        assert result is None


# ============================================================================
# Issue 213: Comprehensive Edge Case Tests
# ============================================================================


class TestGetRawLaunchTimesEdgeCases:
    """Additional edge case tests for the _get_raw_launch_times helper function.

    These tests cover edge cases identified in issue #213 for improved coverage.
    """

    def test_get_raw_launch_times_empty_instances_array(self):
        """Test that empty Instances array is handled correctly."""
        from remote.instance import _get_raw_launch_times

        instances = [
            {
                "Instances": []  # Empty instances array
            }
        ]

        result = _get_raw_launch_times(instances)
        assert len(result) == 0

    def test_get_raw_launch_times_empty_reservations(self):
        """Test that empty reservations list is handled correctly."""
        from remote.instance import _get_raw_launch_times

        result = _get_raw_launch_times([])
        assert len(result) == 0

    def test_get_raw_launch_times_naive_datetime(self):
        """Test that naive datetime (no timezone) is converted to UTC."""
        import datetime

        from remote.instance import _get_raw_launch_times

        # Create a naive datetime (no tzinfo)
        naive_launch_time = datetime.datetime(2024, 1, 15, 10, 30, 0)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": naive_launch_time,
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 1
        # The result should have timezone info set to UTC
        assert result[0].tzinfo == datetime.timezone.utc

    def test_get_raw_launch_times_multiple_reservations(self):
        """Test handling of multiple reservations with mixed states."""
        import datetime

        from remote.instance import _get_raw_launch_times

        launch_time1 = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)
        launch_time2 = datetime.datetime(2024, 1, 16, 11, 45, 0, tzinfo=datetime.timezone.utc)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-running1",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": launch_time1,
                        "Tags": [{"Key": "Name", "Value": "running-instance-1"}],
                    }
                ]
            },
            {
                "Instances": [
                    {
                        "InstanceId": "i-stopped1",
                        "State": {"Name": "stopped", "Code": 80},
                        "Tags": [{"Key": "Name", "Value": "stopped-instance"}],
                    }
                ]
            },
            {
                "Instances": [
                    {
                        "InstanceId": "i-running2",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": launch_time2,
                        "Tags": [{"Key": "Name", "Value": "running-instance-2"}],
                    }
                ]
            },
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 3
        assert result[0] == launch_time1  # Running
        assert result[1] is None  # Stopped
        assert result[2] == launch_time2  # Running

    def test_get_raw_launch_times_running_without_launch_time(self):
        """Test that running instance without LaunchTime key returns None."""
        from remote.instance import _get_raw_launch_times

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "running", "Code": 16},
                        # No LaunchTime key
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 1
        assert result[0] is None

    def test_get_raw_launch_times_missing_state_info(self):
        """Test handling of instance with missing State information."""
        import datetime

        from remote.instance import _get_raw_launch_times

        launch_time = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        # Missing State key - should default to "unknown"
                        "LaunchTime": launch_time,
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 1
        # With state defaulting to "unknown", launch time should be None
        assert result[0] is None

    def test_get_raw_launch_times_multiple_instances_per_reservation(self):
        """Test handling of multiple instances within a single reservation."""
        import datetime

        from remote.instance import _get_raw_launch_times

        launch_time1 = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)
        launch_time2 = datetime.datetime(2024, 1, 16, 11, 45, 0, tzinfo=datetime.timezone.utc)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-running1",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": launch_time1,
                        "Tags": [{"Key": "Name", "Value": "instance-1"}],
                    },
                    {
                        "InstanceId": "i-running2",
                        "State": {"Name": "running", "Code": 16},
                        "LaunchTime": launch_time2,
                        "Tags": [{"Key": "Name", "Value": "instance-2"}],
                    },
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 2
        assert result[0] == launch_time1
        assert result[1] == launch_time2

    def test_get_raw_launch_times_pending_state(self):
        """Test that pending state instances return None for launch time."""
        import datetime

        from remote.instance import _get_raw_launch_times

        launch_time = datetime.datetime(2024, 1, 15, 10, 30, 0, tzinfo=datetime.timezone.utc)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "State": {"Name": "pending", "Code": 0},
                        "LaunchTime": launch_time,
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 1
        # Pending is not "running", so should return None
        assert result[0] is None


class TestHandleSshErrorsEdgeCases:
    """Additional edge case tests for the handle_ssh_errors context manager.

    These tests verify error message content and cover additional scenarios.
    """

    def test_should_include_operation_name_in_timeout_message(self, capsys):
        """Should include the operation name in timeout error message."""
        import subprocess

        import pytest
        import typer

        from remote.instance import handle_ssh_errors

        with pytest.raises(typer.Exit):
            with handle_ssh_errors("Custom SSH test"):
                raise subprocess.TimeoutExpired(cmd="ssh", timeout=30)

        captured = capsys.readouterr()
        assert "Custom SSH test" in captured.out
        assert "timed out" in captured.out

    def test_should_show_ssh_not_found_message(self, capsys):
        """Should display informative message when SSH client is not found."""
        import pytest
        import typer

        from remote.instance import handle_ssh_errors

        with pytest.raises(typer.Exit):
            with handle_ssh_errors("Test operation"):
                raise FileNotFoundError("ssh not found")

        captured = capsys.readouterr()
        assert "SSH client not found" in captured.out
        assert "OpenSSH" in captured.out

    def test_should_include_os_error_details(self, capsys):
        """Should include the OS error details in the error message."""
        import pytest
        import typer

        from remote.instance import handle_ssh_errors

        with pytest.raises(typer.Exit):
            with handle_ssh_errors("Test operation"):
                raise OSError("Connection refused by host")

        captured = capsys.readouterr()
        assert "Connection refused by host" in captured.out
        assert "SSH connection error" in captured.out

    def test_should_pass_through_successful_operation(self):
        """Should allow successful operations to complete normally."""
        from remote.instance import handle_ssh_errors

        result = None
        with handle_ssh_errors("Test operation"):
            result = "success"

        assert result == "success"

    def test_should_pass_through_keyboard_interrupt(self):
        """Should not catch KeyboardInterrupt."""
        import pytest

        from remote.instance import handle_ssh_errors

        with pytest.raises(KeyboardInterrupt):
            with handle_ssh_errors("Test operation"):
                raise KeyboardInterrupt()

    def test_should_use_default_operation_name(self, capsys):
        """Should use default operation name when none provided."""
        import subprocess

        import pytest
        import typer

        from remote.instance import handle_ssh_errors

        with pytest.raises(typer.Exit):
            with handle_ssh_errors():
                raise subprocess.TimeoutExpired(cmd="ssh", timeout=30)

        captured = capsys.readouterr()
        assert "SSH operation" in captured.out
        assert "timed out" in captured.out


# ============================================================================
# Tests for Uncovered Code Paths (Issue #255)
# ============================================================================


class TestListInstancesTimezoneHandling:
    """Test timezone handling in list_instances (line 243)."""

    def test_should_handle_naive_datetime_in_launch_time(self, mocker):
        """Should handle naive datetime (no timezone) by adding UTC (line 243)."""
        import datetime

        mock_ec2_client = mocker.patch("remote.utils.get_ec2_client")

        # Create instance with naive datetime (no tzinfo)
        naive_datetime = datetime.datetime(2023, 7, 15, 12, 0, 0)  # No timezone
        instance_data = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "InstanceType": "t2.micro",
                            "State": {"Name": "running"},
                            "LaunchTime": naive_datetime,
                            "PublicDnsName": "test.amazonaws.com",
                            "Tags": [{"Key": "Name", "Value": "test-instance"}],
                        }
                    ]
                }
            ]
        }

        mock_paginator = mocker.MagicMock()
        mock_paginator.paginate.return_value = [instance_data]
        mock_ec2_client.return_value.get_paginator.return_value = mock_paginator

        # Mock pricing to avoid external calls
        mocker.patch(
            "remote.instance.get_instance_price_with_fallback",
            return_value=(0.05, False),
        )

        result = runner.invoke(app, ["list", "--cost"])

        assert result.exit_code == 0
        assert "test-instance" in result.stdout


class TestRawLaunchTimesWithTimezones:
    """Test _get_raw_launch_times timezone handling (line 243)."""

    def test_should_return_launch_time_with_timezone(self):
        """Should properly return launch time from running instance."""
        import datetime

        from remote.instance import _get_raw_launch_times

        launch_time = datetime.datetime(2023, 7, 15, 14, 30, 45, tzinfo=datetime.timezone.utc)

        instances = [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceType": "t2.micro",
                        "State": {"Name": "running"},
                        "LaunchTime": launch_time,
                        "Tags": [{"Key": "Name", "Value": "test-instance"}],
                    }
                ]
            }
        ]

        result = _get_raw_launch_times(instances)

        assert len(result) == 1
        assert result[0] == launch_time


# ============================================================================
# File Transfer Command Tests (copy and sync)
# ============================================================================


class TestParseRemotePath:
    """Test _parse_remote_path helper function."""

    def test_should_parse_remote_path_with_instance_name(self):
        """Should extract instance name and path from remote path format."""
        from remote.instance import _parse_remote_path

        instance, path = _parse_remote_path("my-instance:/home/ubuntu/data")

        assert instance == "my-instance"
        assert path == "/home/ubuntu/data"

    def test_should_return_none_for_local_absolute_path(self):
        """Should return None for instance name when path is local absolute."""
        from remote.instance import _parse_remote_path

        instance, path = _parse_remote_path("/local/path/to/file")

        assert instance is None
        assert path == "/local/path/to/file"

    def test_should_return_none_for_local_relative_path(self):
        """Should return None for instance name when path is local relative."""
        from remote.instance import _parse_remote_path

        instance, path = _parse_remote_path("./relative/path")

        assert instance is None
        assert path == "./relative/path"

    def test_should_handle_path_with_colon_but_no_slash(self):
        """Should not parse as remote if colon is not followed by slash."""
        from remote.instance import _parse_remote_path

        # This pattern (colon not followed by /) should be treated as local
        instance, path = _parse_remote_path("file:name.txt")

        assert instance is None
        assert path == "file:name.txt"


class TestBuildRsyncCommand:
    """Test _build_rsync_command helper function."""

    def test_should_build_basic_rsync_command(self):
        """Should build rsync command with SSH options."""
        from remote.instance import _build_rsync_command

        cmd = _build_rsync_command(
            source="./local/",
            destination="user@host:/remote/",
            ssh_key=None,
            ssh_user="ubuntu",
        )

        assert cmd[0] == "rsync"
        assert "-avz" in cmd
        assert "-e" in cmd
        assert "ssh -o StrictHostKeyChecking=accept-new" in cmd
        assert "./local/" in cmd
        assert "user@host:/remote/" in cmd

    def test_should_include_ssh_key_when_provided(self):
        """Should add SSH key to command when provided."""
        from remote.instance import _build_rsync_command

        cmd = _build_rsync_command(
            source="./local/",
            destination="user@host:/remote/",
            ssh_key="/path/to/key.pem",
            ssh_user="ubuntu",
        )

        ssh_cmd_index = cmd.index("-e") + 1
        assert "-i /path/to/key.pem" in cmd[ssh_cmd_index]

    def test_should_add_delete_flag_when_requested(self):
        """Should add --delete flag when delete=True."""
        from remote.instance import _build_rsync_command

        cmd = _build_rsync_command(
            source="./local/",
            destination="user@host:/remote/",
            ssh_key=None,
            ssh_user="ubuntu",
            delete=True,
        )

        assert "--delete" in cmd

    def test_should_add_dry_run_flag_when_requested(self):
        """Should add --dry-run flag when dry_run=True."""
        from remote.instance import _build_rsync_command

        cmd = _build_rsync_command(
            source="./local/",
            destination="user@host:/remote/",
            ssh_key=None,
            ssh_user="ubuntu",
            dry_run=True,
        )

        assert "--dry-run" in cmd

    def test_should_add_progress_flag_when_verbose(self):
        """Should add --progress flag when verbose=True."""
        from remote.instance import _build_rsync_command

        cmd = _build_rsync_command(
            source="./local/",
            destination="user@host:/remote/",
            ssh_key=None,
            ssh_user="ubuntu",
            verbose=True,
        )

        assert "--progress" in cmd

    def test_should_add_exclude_patterns(self):
        """Should add --exclude for each pattern."""
        from remote.instance import _build_rsync_command

        cmd = _build_rsync_command(
            source="./local/",
            destination="user@host:/remote/",
            ssh_key=None,
            ssh_user="ubuntu",
            exclude=["*.pyc", "__pycache__"],
        )

        assert "--exclude" in cmd
        exclude_indices = [i for i, x in enumerate(cmd) if x == "--exclude"]
        assert len(exclude_indices) == 2
        assert cmd[exclude_indices[0] + 1] == "*.pyc"
        assert cmd[exclude_indices[1] + 1] == "__pycache__"


class TestResolveTransferPaths:
    """Test _resolve_transfer_paths helper function."""

    def test_should_resolve_upload_path(self):
        """Should correctly resolve paths for upload (local -> remote)."""
        from remote.instance import _resolve_transfer_paths

        instance, src, dst, is_upload = _resolve_transfer_paths(
            "./local/data/", "my-instance:/home/ubuntu/data/"
        )

        assert instance == "my-instance"
        assert src == "./local/data/"
        assert dst == "/home/ubuntu/data/"
        assert is_upload is True

    def test_should_resolve_download_path(self):
        """Should correctly resolve paths for download (remote -> local)."""
        from remote.instance import _resolve_transfer_paths

        instance, src, dst, is_upload = _resolve_transfer_paths(
            "my-instance:/home/ubuntu/logs/", "./logs/"
        )

        assert instance == "my-instance"
        assert src == "/home/ubuntu/logs/"
        assert dst == "./logs/"
        assert is_upload is False

    def test_should_reject_two_remote_paths(self):
        """Should exit with error when both paths are remote."""
        import click
        import pytest

        from remote.instance import _resolve_transfer_paths

        with pytest.raises(click.exceptions.Exit):
            _resolve_transfer_paths("instance1:/path1/", "instance2:/path2/")

    def test_should_reject_two_local_paths(self):
        """Should exit with error when both paths are local."""
        import click
        import pytest

        from remote.instance import _resolve_transfer_paths

        with pytest.raises(click.exceptions.Exit):
            _resolve_transfer_paths("./local1/", "./local2/")


class TestCopyCommand:
    """Test the 'remote instance copy' command behavior."""

    def test_should_copy_local_to_remote(self, mocker):
        """Should execute rsync to copy local files to remote instance."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path="/path/to/key.pem"),
        )
        mock_subprocess = mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=0),
        )

        result = runner.invoke(app, ["copy", "./local/data/", "test-instance:/home/ubuntu/data/"])

        assert result.exit_code == 0
        assert "Copying files" in result.stdout
        assert "local -> test-instance" in result.stdout
        assert "File transfer complete" in result.stdout
        mock_subprocess.assert_called_once()
        rsync_cmd = mock_subprocess.call_args[0][0]
        assert rsync_cmd[0] == "rsync"
        assert "./local/data/" in rsync_cmd
        assert "ubuntu@ec2-1-2-3-4.compute-1.amazonaws.com:/home/ubuntu/data/" in rsync_cmd

    def test_should_copy_remote_to_local(self, mocker):
        """Should execute rsync to copy remote files to local."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path="/path/to/key.pem"),
        )
        mock_subprocess = mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=0),
        )

        result = runner.invoke(app, ["copy", "test-instance:/home/ubuntu/logs/", "./logs/"])

        assert result.exit_code == 0
        assert "Copying files" in result.stdout
        assert "test-instance -> local" in result.stdout
        mock_subprocess.assert_called_once()
        rsync_cmd = mock_subprocess.call_args[0][0]
        assert "ubuntu@ec2-1-2-3-4.compute-1.amazonaws.com:/home/ubuntu/logs/" in rsync_cmd
        assert "./logs/" in rsync_cmd

    def test_should_use_dry_run_flag(self, mocker):
        """Should perform dry run when --dry-run flag is used."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path=None),
        )
        mock_subprocess = mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=0),
        )

        result = runner.invoke(app, ["copy", "--dry-run", "./local/", "test-instance:/remote/"])

        assert result.exit_code == 0
        assert "Would copy" in result.stdout
        rsync_cmd = mock_subprocess.call_args[0][0]
        assert "--dry-run" in rsync_cmd

    def test_should_fail_with_two_local_paths(self, mocker):
        """Should exit with error when both paths are local."""
        result = runner.invoke(app, ["copy", "./local1/", "./local2/"])

        assert result.exit_code == 1
        assert "At least one path must be a remote path" in result.stdout

    def test_should_fail_when_instance_not_running(self, mocker):
        """Should exit with error when instance is not running and --no-start is used."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=False,
        )

        result = runner.invoke(app, ["copy", "--no-start", "./local/", "test-instance:/remote/"])

        assert result.exit_code == 1
        assert "not running" in result.stdout

    def test_should_fail_when_no_dns(self, mocker):
        """Should exit with error when instance has no public DNS."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value=None,
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path=None),
        )

        result = runner.invoke(app, ["copy", "./local/", "test-instance:/remote/"])

        assert result.exit_code == 1
        assert "no public DNS" in result.stdout


class TestSyncCommand:
    """Test the 'remote instance sync' command behavior."""

    def test_should_sync_without_delete(self, mocker):
        """Should execute rsync without --delete when not specified."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path=None),
        )
        mock_subprocess = mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=0),
        )

        result = runner.invoke(app, ["sync", "./local/src/", "test-instance:/app/src/"])

        assert result.exit_code == 0
        assert "Syncing files" in result.stdout
        rsync_cmd = mock_subprocess.call_args[0][0]
        assert "--delete" not in rsync_cmd

    def test_should_sync_with_delete_and_yes_flag(self, mocker):
        """Should execute rsync with --delete when specified with --yes."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path=None),
        )
        mock_subprocess = mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=0),
        )

        result = runner.invoke(
            app, ["sync", "--delete", "--yes", "./local/src/", "test-instance:/app/src/"]
        )

        assert result.exit_code == 0
        assert "(with delete)" in result.stdout
        rsync_cmd = mock_subprocess.call_args[0][0]
        assert "--delete" in rsync_cmd

    def test_should_prompt_for_delete_confirmation(self, mocker):
        """Should prompt for confirmation when --delete is used without --yes."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.confirm_action",
            return_value=False,
        )

        result = runner.invoke(app, ["sync", "--delete", "./local/", "test-instance:/remote/"])

        assert result.exit_code == 0
        assert "Sync cancelled" in result.stdout

    def test_should_skip_confirmation_for_dry_run_delete(self, mocker):
        """Should not prompt when --delete and --dry-run are used together."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path=None),
        )
        mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=0),
        )
        mock_confirm = mocker.patch("remote.instance.confirm_action")

        result = runner.invoke(
            app, ["sync", "--delete", "--dry-run", "./local/", "test-instance:/remote/"]
        )

        assert result.exit_code == 0
        assert "Would sync" in result.stdout
        mock_confirm.assert_not_called()

    def test_should_use_exclude_patterns(self, mocker):
        """Should pass exclude patterns to rsync."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path=None),
        )
        mock_subprocess = mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=0),
        )

        result = runner.invoke(
            app, ["sync", "-e", "*.log", "-e", "tmp/", "./data/", "test-instance:/data/"]
        )

        assert result.exit_code == 0
        rsync_cmd = mock_subprocess.call_args[0][0]
        assert "--exclude" in rsync_cmd
        assert "*.log" in rsync_cmd
        assert "tmp/" in rsync_cmd

    def test_should_handle_rsync_failure(self, mocker):
        """Should exit with rsync's exit code on failure."""
        mocker.patch(
            "remote.instance.get_instance_id",
            return_value="i-0123456789abcdef0",
        )
        mocker.patch(
            "remote.instance.is_instance_running",
            return_value=True,
        )
        mocker.patch(
            "remote.instance.get_instance_dns",
            return_value="ec2-1-2-3-4.compute-1.amazonaws.com",
        )
        mocker.patch(
            "remote.instance.get_ssh_config",
            return_value=mocker.MagicMock(user="ubuntu", key_path=None),
        )
        mocker.patch(
            "remote.instance.subprocess.run",
            return_value=mocker.MagicMock(returncode=12),
        )

        result = runner.invoke(app, ["sync", "./local/", "test-instance:/remote/"])

        assert result.exit_code == 12
        assert "rsync failed" in result.stdout
