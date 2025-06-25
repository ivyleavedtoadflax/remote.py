import configparser
import datetime

import pytest
from typer.testing import CliRunner

import remotepy
import remotepy.utils
from remotepy.instance import app
from remotepy.utils import get_launch_template_id

runner = CliRunner()


# ============================================================================
# Instance CLI Command Tests
# ============================================================================


class TestInstanceStatusCommand:
    """Test the 'remote status' command behavior."""

    def test_should_report_error_when_instance_not_found(self, mocker):
        """Should exit with error code 1 when instance doesn't exist."""
        mocker.patch("remotepy.utils.ec2_client", autospec=True)
        remotepy.utils.ec2_client.describe_instances.return_value = {"Reservations": []}

        result = runner.invoke(app, ["status", "test"])

        assert result.exit_code == 1
        assert "Instance 'test' not found" in result.stdout


class TestInstanceListCommand:
    """Test the 'remote list' command behavior."""

    def test_should_show_table_headers_when_no_instances_exist(self, mocker):
        """Should display table headers even when no instances are found."""
        mocker.patch("remotepy.utils.ec2_client", autospec=True)
        remotepy.utils.ec2_client.describe_instances.return_value = {"Reservations": []}

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "Name" in result.stdout
        assert "InstanceId" in result.stdout
        assert "PublicDnsName" in result.stdout
        assert "Status" in result.stdout

    def test_should_display_instance_details_when_instances_exist(self, mocker, mock_ec2_instances):
        """Should show instance details in tabular format when instances are found."""
        mocker.patch("remotepy.utils.ec2_client", autospec=True)
        remotepy.utils.ec2_client.describe_instances.return_value = mock_ec2_instances

        result = runner.invoke(app, ["list"])

        # Verify API call was made
        remotepy.utils.ec2_client.describe_instances.assert_called_once()

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


class TestLaunchTemplateUtilities:
    """Test launch template utility functions."""

    def test_should_return_template_id_when_template_found_by_name(self, mocker):
        """Should return the launch template ID when template is found by name tag."""
        mocker.patch("remotepy.utils.ec2_client", autospec=True)
        mock_describe_launch_templates = remotepy.utils.ec2_client.describe_launch_templates
        mock_describe_launch_templates.return_value = {
            "LaunchTemplates": [{"LaunchTemplateId": "lt-0123456789abcdef0"}]
        }

        result = get_launch_template_id("my-template-name")

        mock_describe_launch_templates.assert_called_once_with(
            Filters=[{"Name": "tag:Name", "Values": ["my-template-name"]}]
        )
        assert result == "lt-0123456789abcdef0"


    def test_should_show_running_instance_status_details(self, mocker):
        """Should display detailed status information for a running instance."""
        mock_get_instance_name = mocker.patch(
            "remotepy.instance.get_instance_name", return_value="test-instance"
        )
        mock_get_instance_id = mocker.patch(
            "remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0"
        )
        mock_get_instance_status = mocker.patch(
            "remotepy.instance.get_instance_status",
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

    def test_should_report_non_running_instance_status(self, mocker):
        """Should report when instance exists but is not in running state."""
        mock_get_instance_id = mocker.patch(
            "remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0"
        )
        mocker.patch("remotepy.instance.get_instance_status", return_value={"InstanceStatuses": []})

        result = runner.invoke(app, ["status", "specific-instance"])

        assert result.exit_code == 0
        mock_get_instance_id.assert_called_once_with("specific-instance")
        assert "specific-instance is not in running state" in result.stdout


# Removed duplicate - moved to TestInstanceStatusCommand class above


def test_start_instance_already_running(mocker):
    mock_get_instance_name = mocker.patch(
        "remotepy.instance.get_instance_name", return_value="test-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remotepy.instance.is_instance_running", return_value=True
    )

    result = runner.invoke(app, ["start"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    assert "Instance test-instance is already running" in result.stdout


def test_start_instance_success(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mock_get_instance_id = mocker.patch(
        "remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remotepy.instance.is_instance_running", return_value=False
    )

    result = runner.invoke(app, ["start", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    mock_ec2_client.start_instances.assert_called_once_with(InstanceIds=["i-0123456789abcdef0"])
    assert "Instance test-instance started" in result.stdout


def test_start_instance_exception(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.instance.is_instance_running", return_value=False)

    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "TestError", "Message": "AWS Error"}}
    mock_ec2_client.start_instances.side_effect = ClientError(error_response, "start_instances")

    result = runner.invoke(app, ["start", "test-instance"])

    assert result.exit_code == 1
    assert "AWS Error starting instance test-instance: AWS Error (TestError)" in result.stdout


def test_stop_instance_already_stopped(mocker):
    mock_get_instance_id = mocker.patch(
        "remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_is_instance_running = mocker.patch(
        "remotepy.instance.is_instance_running", return_value=False
    )

    result = runner.invoke(app, ["stop", "test-instance"])

    assert result.exit_code == 0
    mock_get_instance_id.assert_called_once_with("test-instance")
    mock_is_instance_running.assert_called_once_with("i-0123456789abcdef0")
    assert "Instance test-instance is already stopped" in result.stdout


def test_stop_instance_confirmed(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["stop", "test-instance"], input="y\n")

    assert result.exit_code == 0
    mock_ec2_client.stop_instances.assert_called_once_with(InstanceIds=["i-0123456789abcdef0"])
    assert "Instance test-instance is stopping" in result.stdout


def test_stop_instance_cancelled(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["stop", "test-instance"], input="n\n")

    assert result.exit_code == 0
    mock_ec2_client.stop_instances.assert_not_called()
    assert "Instance test-instance is still running" in result.stdout


def test_stop_instance_exception(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.instance.is_instance_running", return_value=True)

    from botocore.exceptions import ClientError

    error_response = {"Error": {"Code": "TestError", "Message": "AWS Error"}}
    mock_ec2_client.stop_instances.side_effect = ClientError(error_response, "stop_instances")

    result = runner.invoke(app, ["stop", "test-instance"], input="y\n")

    assert result.exit_code == 1
    assert "AWS Error stopping instance test-instance: AWS Error (TestError)" in result.stdout


def test_type_command_show_current_type(mocker):
    mock_get_instance_name = mocker.patch(
        "remotepy.instance.get_instance_name", return_value="test-instance"
    )
    mock_get_instance_id = mocker.patch(
        "remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0"
    )
    mock_get_instance_type = mocker.patch(
        "remotepy.instance.get_instance_type", return_value="t2.micro"
    )

    result = runner.invoke(app, ["type"])

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    mock_get_instance_id.assert_called_once_with("test-instance")
    # get_instance_type is called twice - once to get current, once at the end
    assert mock_get_instance_type.call_count >= 1
    assert "Instance test-instance is currently of type t2.micro" in result.stdout


def test_type_command_same_type(mocker):
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.instance.get_instance_type", return_value="t2.micro")

    result = runner.invoke(app, ["type", "t2.micro", "test-instance"])

    assert result.exit_code == 0
    assert "Instance test-instance is already of type t2.micro" in result.stdout


def test_type_command_running_instance_error(mocker):
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.instance.get_instance_type", return_value="t2.micro")
    mocker.patch("remotepy.instance.is_instance_running", return_value=True)

    result = runner.invoke(app, ["type", "t2.small", "test-instance"])

    assert result.exit_code == 1
    assert "You can only change the type of a stopped instances" in result.stdout


def test_type_command_change_success(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")
    mocker.patch("remotepy.instance.get_instance_type", side_effect=["t2.micro", "t2.small"])
    mocker.patch("remotepy.instance.is_instance_running", return_value=False)
    mocker.patch("remotepy.instance.time.sleep")

    result = runner.invoke(app, ["type", "t2.small", "test-instance"])

    assert result.exit_code == 0
    mock_ec2_client.modify_instance_attribute.assert_called_once_with(
        InstanceId="i-0123456789abcdef0", InstanceType={"Value": "t2.small"}
    )
    assert "Instance test-instance is now of type t2.small" in result.stdout


def test_terminate_instance_name_mismatch(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mock_get_instance_name = mocker.patch(
        "remotepy.instance.get_instance_name", return_value="test-instance"
    )
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")

    # Mock the describe_instances call that happens in terminate function
    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate"], input="wrong-name\n")

    assert result.exit_code == 0
    mock_get_instance_name.assert_called_once()
    assert "Instance names did not match. Aborting termination." in result.stdout


def test_terminate_instance_cancelled(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")

    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\nn\n")

    assert result.exit_code == 0
    mock_ec2_client.terminate_instances.assert_not_called()
    assert "Termination of instance test-instance has been cancelled" in result.stdout


def test_terminate_instance_confirmed(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")

    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"Tags": []}]}]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\ny\n")

    assert result.exit_code == 0
    mock_ec2_client.terminate_instances.assert_called_once_with(InstanceIds=["i-0123456789abcdef0"])
    assert "Instance test-instance is being terminated" in result.stdout


def test_terminate_terraform_managed_instance(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)
    mocker.patch("remotepy.instance.get_instance_id", return_value="i-0123456789abcdef0")

    mock_ec2_client.describe_instances.return_value = {
        "Reservations": [
            {"Instances": [{"Tags": [{"Key": "Environment", "Value": "terraform-managed"}]}]}
        ]
    }

    result = runner.invoke(app, ["terminate", "test-instance"], input="test-instance\ny\n")

    assert result.exit_code == 0
    assert "This instance appears to be managed by Terraform" in result.stdout


def test_list_launch_templates_command(mocker):
    mock_ec2_client = mocker.patch("remotepy.instance.ec2_client", autospec=True)

    mock_ec2_client.describe_launch_templates.return_value = {
        "LaunchTemplates": [
            {
                "LaunchTemplateId": "lt-0123456789abcdef0",
                "LaunchTemplateName": "test-template-1",
                "LatestVersionNumber": 2,
            }
        ]
    }

    result = runner.invoke(app, ["list-launch-templates"])

    assert result.exit_code == 0
    mock_ec2_client.describe_launch_templates.assert_called_once()
    assert "test-template-1" in result.stdout
    assert "lt-0123456789abcdef0" in result.stdout
