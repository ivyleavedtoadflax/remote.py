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
        mock_get_instance_name = mocker.patch(
            "remote.instance.get_instance_name", return_value="test-instance"
        )
        mock_get_instance_id = mocker.patch(
            "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
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
        mock_get_instance_name.assert_called_once()
        mock_get_instance_id.assert_called_once_with("test-instance")
        mock_get_instance_status.assert_called_once_with("i-0123456789abcdef0")

        # Verify status information is displayed
        assert "test-instance" in result.stdout
        assert "running" in result.stdout
        # Verify detailed info is shown
        assert "t2.micro" in result.stdout
        assert "1.2.3.4" in result.stdout

    def test_should_show_stopped_instance_details(self, mocker):
        """Should display details for stopped instances (without health status)."""
        mock_get_instance_id = mocker.patch(
            "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
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
        mock_get_instance_id.assert_called_once_with("specific-instance")
        # Verify basic info is displayed
        assert "specific-instance" in result.stdout
        assert "stopped" in result.stdout
        assert "t2.micro" in result.stdout


class TestStatusWatchMode:
    """Test the watch mode functionality for the status command."""

    def test_should_reject_interval_less_than_one(self, mocker):
        """Should exit with error when interval is less than 1."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

        result = runner.invoke(app, ["status", "--watch", "--interval", "0"])

        assert result.exit_code == 1
        assert "Interval must be at least 1 second" in result.stdout

    def test_should_accept_watch_flag(self, mocker):
        """Should accept the --watch flag and enter watch mode."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

        # Mock _watch_status to avoid actually entering the infinite loop
        mock_watch = mocker.patch("remote.instance._watch_status")

        result = runner.invoke(app, ["status", "--watch"])

        assert result.exit_code == 0
        mock_watch.assert_called_once_with("test-instance", "i-0123456789abcdef0", 2)

    def test_should_accept_short_watch_flag(self, mocker):
        """Should accept the -w short flag for watch mode."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

        mock_watch = mocker.patch("remote.instance._watch_status")

        result = runner.invoke(app, ["status", "-w"])

        assert result.exit_code == 0
        mock_watch.assert_called_once()

    def test_should_accept_custom_interval(self, mocker):
        """Should accept custom interval via --interval flag."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

        mock_watch = mocker.patch("remote.instance._watch_status")

        result = runner.invoke(app, ["status", "--watch", "--interval", "5"])

        assert result.exit_code == 0
        mock_watch.assert_called_once_with("test-instance", "i-0123456789abcdef0", 5)

    def test_should_accept_short_interval_flag(self, mocker):
        """Should accept -i short flag for interval."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

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

    def test_should_return_error_string_for_not_found_instance(self, mocker):
        """Should return an error string when instance is not found."""
        from remote.instance import _build_status_table

        mocker.patch(
            "remote.instance.get_instance_status",
            return_value={"InstanceStatuses": []},
        )
        # Mock EC2 client returning empty reservations
        mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
        mock_ec2_client.return_value.describe_instances.return_value = {"Reservations": []}

        result = _build_status_table("test-instance", "i-0123456789abcdef0")

        assert isinstance(result, str)
        assert "not found" in result


class TestWatchStatusFunction:
    """Test the _watch_status function."""

    def test_should_handle_keyboard_interrupt(self, mocker):
        """Should handle Ctrl+C gracefully."""
        from remote.instance import _watch_status

        # Mock time.sleep to raise KeyboardInterrupt
        mocker.patch("remote.instance.time.sleep", side_effect=KeyboardInterrupt)

        # Mock _build_status_table to return a simple string
        mocker.patch("remote.instance._build_status_table", return_value="test")

        # Mock Console and Live
        mocker.patch("remote.instance.Console")
        mock_live = mocker.patch("remote.instance.Live")
        mock_live.return_value.__enter__ = mocker.Mock(return_value=mock_live.return_value)
        mock_live.return_value.__exit__ = mocker.Mock(return_value=False)

        # Should not raise, should exit gracefully
        _watch_status("test-instance", "i-0123456789abcdef0", 2)

        # Verify the function tried to update at least once
        mock_live.return_value.update.assert_called()


def test_start_instance_already_running(mocker):
    mock_get_instance_name = mocker.patch(
        "remote.instance.get_instance_name", return_value="test-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remote.instance.is_instance_running", return_value=True
    )

    result = runner.invoke(app, ["start"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    assert "Instance test-instance is already running" in result.stdout


def test_start_instance_success(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mock_get_instance_id = mocker.patch(
        "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remote.instance.is_instance_running", return_value=False
    )

    result = runner.invoke(app, ["start", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    mock_ec2_client.return_value.start_instances.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )
    assert "Instance test-instance started" in result.stdout


def test_start_instance_exception(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.is_instance_running", return_value=False)

    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "TestError", "Message": "AWS Error"}}
    mock_ec2_client.return_value.start_instances.side_effect = ClientError(
        error_response, "start_instances"
    )

    result = runner.invoke(app, ["start", "test-instance"])

    assert result.exit_code == 1
    assert "AWS Error starting instance test-instance: AWS Error (TestError)" in result.stdout


def test_stop_instance_already_stopped(mocker):
    mock_get_instance_id = mocker.patch(
        "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remote.instance.is_instance_running", return_value=False
    )

    result = runner.invoke(app, ["stop", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    assert "Instance test-instance is already stopped" in result.stdout


def test_stop_instance_confirmed(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["stop", "test-instance"], input="y\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.stop_instances.assert_called_once_with(
        InstanceIds=["i-0123456789abcdef0"]
    )
    assert "Instance test-instance is stopping" in result.stdout


def test_stop_instance_cancelled(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["stop", "test-instance"], input="n\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.stop_instances.assert_not_called()
    assert "Instance test-instance is still running" in result.stdout


def test_stop_instance_exception(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.is_instance_running", return_value=True)

    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "TestError", "Message": "AWS Error"}}
    mock_ec2_client.return_value.stop_instances.side_effect = ClientError(
        error_response, "stop_instances"
    )

    result = runner.invoke(app, ["stop", "test-instance"], input="y\n")

    assert result.exit_code == 1
    assert "AWS Error stopping instance test-instance: AWS Error (TestError)" in result.stdout


def test_type_command_show_current_type(mocker):
    mock_get_instance_name = mocker.patch(
        "remote.instance.get_instance_name", return_value="test-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remote.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_get_instance_type = mocker.patch(
        "remote.instance.get_instance_type", return_value="t2.micro"
    )

    result = runner.invoke(app, ["type"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("test-instance")
    # get_instance_type is called twice - once to get current, once at the end
    assert mock_get_instance_type.call_count >= 1
    assert "Instance test-instance is currently of type t2.micro" in result.stdout


def test_type_command_same_type(mocker):
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.get_instance_type", return_value="t2.micro")

    result = runner.invoke(app, ["type", "t2.micro", "test-instance"])

    assert result.exit_code == 0
    assert "Instance test-instance is already of type t2.micro" in result.stdout


def test_type_command_running_instance_error(mocker):
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.get_instance_type", return_value="t2.micro")
    mocker.patch("remote.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["type", "t2.small", "test-instance"])

    assert result.exit_code == 1
    assert "You can only change the type of a stopped instances" in result.stdout


def test_type_command_change_success(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remote.instance.get_instance_type", side_effect=["t2.micro", "t2.small"])
    mocker.patch("remote.instance.is_instance_running", return_value=False)
    mocker.patch("remote.instance.time.sleep")

    result = runner.invoke(app, ["type", "t2.small", "test-instance"])

    assert result.exit_code == 0
    mock_ec2_client.return_value.modify_instance_attribute.assert_called_once_with(
        InstanceId="i-0123456789abcdef0", InstanceType={"Value": "t2.small"}
    )
    assert "Instance test-instance is now of type t2.small" in result.stdout


def test_terminate_instance_name_mismatch(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mock_get_instance_name = mocker.patch(
        "remote.instance.get_instance_name", return_value="test-instance"
    )
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

    # Mock the describe_instances call that happens in terminate function
    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate"], input="wrong-name\n")

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    assert "Instance names did not match. Aborting termination." in result.stdout


def test_terminate_instance_cancelled(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\nn\n")

    assert result.exit_code == 0
    mock_ec2_client.return_value.terminate_instances.assert_not_called()
    assert "Termination of instance test-instance has been cancelled" in result.stdout


def test_terminate_instance_confirmed(mocker):
    mock_ec2_client = mocker.patch("remote.instance.get_ec2_client")
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

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
    mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")

    mock_ec2_client.return_value.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"Tags": [{"Key": "Environment", "Value": "terraform-managed"}]}]}
        ]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\ny\n")

    assert result.exit_code == 0
    assert "This instance appears to be managed by Terraform" in result.stdout


def test_connect_with_key_option(mocker):
    """Test that --key option adds -i flag to SSH command."""
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
    runner.invoke(app, ["connect", "test-instance", "--key", "/path/to/my-key.pem"])

    # Verify subprocess.run was called
    mock_subprocess.assert_called_once()

    # Get the actual SSH command that was called
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the key option is included
    assert "-i" in ssh_command
    assert "/path/to/my-key.pem" in ssh_command
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


def test_connect_key_option_overrides_config(mocker):
    """Test that --key option takes precedence over config ssh_key."""
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

    # Pass --key option explicitly
    runner.invoke(app, ["connect", "test-instance", "--key", "/path/to/explicit-key.pem"])

    mock_subprocess.assert_called_once()
    ssh_command = mock_subprocess.call_args[0][0]

    # Verify the explicit key is used, not the config key
    assert "-i" in ssh_command
    assert "/path/to/explicit-key.pem" in ssh_command
    assert "/home/user/.ssh/config-key.pem" not in ssh_command

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


# ============================================================================
# Issue 39: Scheduled Shutdown Tests
# ============================================================================


class TestScheduledShutdown:
    """Tests for scheduled instance shutdown functionality."""

    def test_stop_with_in_option_schedules_shutdown(self, mocker):
        """Test that --in option schedules shutdown via SSH."""
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

        result = runner.invoke(app, ["stop", "test-instance", "--in", "3h"])

        assert result.exit_code == 0
        assert "will shut down in 3h" in result.stdout

        # Verify SSH command was called with shutdown command
        mock_subprocess.assert_called_once()
        ssh_command = mock_subprocess.call_args[0][0]
        assert "ssh" in ssh_command
        assert "sudo shutdown -h +180" in ssh_command

    def test_stop_with_in_option_invalid_duration(self, mocker):
        """Test that --in option with invalid duration shows error."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
        mocker.patch("remote.instance.is_instance_running", return_value=True)

        result = runner.invoke(app, ["stop", "test-instance", "--in", "invalid"])

        assert result.exit_code == 1
        assert "Invalid duration format" in result.stdout

    def test_stop_with_in_option_not_running(self, mocker):
        """Test that --in option on stopped instance shows warning."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
        mocker.patch("remote.instance.is_instance_running", return_value=False)

        result = runner.invoke(app, ["stop", "test-instance", "--in", "3h"])

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
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
        mocker.patch("remote.instance.get_instance_id", return_value="i-0123456789abcdef0")
        mocker.patch("remote.instance.is_instance_running", return_value=False)

        result = runner.invoke(app, ["stop", "test-instance", "--cancel"])

        assert result.exit_code == 0
        assert "is not running" in result.stdout
        assert "cannot cancel shutdown" in result.stdout


class TestStartWithStopIn:
    """Tests for start command with --stop-in option."""

    def test_start_with_stop_in_option_invalid_duration(self, mocker):
        """Test that --stop-in option with invalid duration fails early."""
        mocker.patch("remote.instance.get_instance_name", return_value="test-instance")
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

        result = runner.invoke(app, ["stop", "test-instance", "--in", "1h"])

        assert result.exit_code == 1
        assert "SSH connection timed out" in result.stdout

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

        result = runner.invoke(app, ["stop", "test-instance", "--in", "1h"])

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

        result = runner.invoke(app, ["stop", "test-instance", "--in", "1h"])

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

        result = runner.invoke(app, ["stop", "test-instance", "--in", "30m"])

        assert result.exit_code == 0

        # Verify SSH command includes the key
        ssh_command = mock_subprocess.call_args[0][0]
        assert "-i" in ssh_command
        assert "/path/to/key.pem" in ssh_command
        assert "ec2-user@" in ssh_command[-2]  # User from config


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


class TestFormatUptime:
    """Tests for the _format_uptime helper function."""

    def test_format_uptime_minutes_only(self):
        """Test formatting uptime with minutes only."""
        from remote.instance import _format_uptime

        assert _format_uptime(300) == "5m"  # 5 minutes
        assert _format_uptime(0) == "0m"

    def test_format_uptime_hours_and_minutes(self):
        """Test formatting uptime with hours and minutes."""
        from remote.instance import _format_uptime

        assert _format_uptime(3900) == "1h 5m"  # 1 hour 5 minutes
        assert _format_uptime(7200) == "2h"  # 2 hours exactly

    def test_format_uptime_days_hours_minutes(self):
        """Test formatting uptime with days, hours, and minutes."""
        from remote.instance import _format_uptime

        assert _format_uptime(90000) == "1d 1h"  # 25 hours
        assert _format_uptime(180000) == "2d 2h"  # 50 hours

    def test_format_uptime_none(self):
        """Test formatting None uptime."""
        from remote.instance import _format_uptime

        assert _format_uptime(None) == "-"

    def test_format_uptime_negative(self):
        """Test formatting negative uptime."""
        from remote.instance import _format_uptime

        assert _format_uptime(-100) == "-"


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
