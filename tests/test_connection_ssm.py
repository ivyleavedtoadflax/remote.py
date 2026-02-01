"""Tests for the SSM connection provider."""

import json
import subprocess

import pytest

from remote.exceptions import SSMError


class TestSSMConnectionProvider:
    """Test the SSM connection provider."""

    def test_should_not_support_file_transfer(self):
        """SSM provider should report that it does not support file transfer."""
        from remote.connection_ssm import SSMConnectionProvider

        provider = SSMConnectionProvider()
        assert provider.supports_file_transfer() is False

    def test_should_store_ssm_profile(self):
        """Should store SSM profile when provided."""
        from remote.connection_ssm import SSMConnectionProvider

        provider = SSMConnectionProvider(ssm_profile="my-profile")
        assert provider.ssm_profile == "my-profile"


class TestSSMConnectInteractive:
    """Test SSM interactive connection."""

    def test_should_call_aws_ssm_start_session(self, mocker):
        """Should call aws ssm start-session with correct arguments."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSMConnectionProvider()
        exit_code = provider.connect_interactive(
            instance_id="i-123456789",
            dns="example.com",  # Not used for SSM
            user="ubuntu",
        )

        assert exit_code == 0
        mock_run.assert_called_once()

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "aws"
        assert call_args[1] == "ssm"
        assert call_args[2] == "start-session"
        assert "--target" in call_args
        assert "i-123456789" in call_args
        assert "--document-name" in call_args
        assert "AWS-StartInteractiveCommand" in call_args

    def test_should_switch_to_specified_user(self, mocker):
        """Should switch to the specified user via sudo."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSMConnectionProvider()
        provider.connect_interactive(
            instance_id="i-123456789",
            dns="example.com",
            user="ec2-user",
        )

        call_args = mock_run.call_args[0][0]
        # Find the parameters argument
        params_idx = call_args.index("--parameters") + 1
        params = json.loads(call_args[params_idx])

        assert "command" in params
        assert "sudo su - ec2-user" in params["command"]

    def test_should_include_profile_when_specified(self, mocker):
        """Should include --profile when ssm_profile is set."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSMConnectionProvider(ssm_profile="my-profile")
        provider.connect_interactive(
            instance_id="i-123456789",
            dns="example.com",
            user="ubuntu",
        )

        call_args = mock_run.call_args[0][0]
        assert "--profile" in call_args
        assert "my-profile" in call_args

    def test_should_raise_ssm_error_when_aws_cli_not_found(self, mocker):
        """Should raise SSMError when AWS CLI is not installed."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.side_effect = FileNotFoundError("aws not found")

        provider = SSMConnectionProvider()

        with pytest.raises(SSMError) as exc_info:
            provider.connect_interactive(
                instance_id="i-123456789",
                dns="example.com",
                user="ubuntu",
            )

        assert "AWS CLI not found" in str(exc_info.value)


class TestSSMExecuteCommand:
    """Test SSM command execution."""

    def test_should_call_send_command_with_correct_args(self, mocker):
        """Should call aws ssm send-command with correct arguments."""
        from remote.connection_ssm import SSMConnectionProvider

        # Mock send-command response
        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        send_response = {"Command": {"CommandId": "cmd-123456"}}
        get_response = {
            "Status": "Success",
            "StandardOutputContent": "output",
            "StandardErrorContent": "",
        }
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(send_response), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(get_response), stderr=""
            ),
        ]

        # Mock time.sleep to speed up test
        mocker.patch("remote.connection_ssm.time.sleep")

        provider = SSMConnectionProvider()
        exit_code, stdout, stderr = provider.execute_command(
            instance_id="i-123456789",
            dns="example.com",
            command=["whoami"],
            user="ubuntu",
        )

        assert exit_code == 0
        assert stdout == "output"
        assert stderr == ""

        # Verify send-command was called
        first_call = mock_run.call_args_list[0][0][0]
        assert first_call[0] == "aws"
        assert first_call[1] == "ssm"
        assert first_call[2] == "send-command"
        assert "--document-name" in first_call
        assert "AWS-RunShellScript" in first_call

    def test_should_return_nonzero_exit_code_on_failure(self, mocker):
        """Should return non-zero exit code when command fails."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        send_response = {"Command": {"CommandId": "cmd-123456"}}
        get_response = {
            "Status": "Failed",
            "StatusDetails": "Command failed",
            "StandardOutputContent": "",
            "StandardErrorContent": "error message",
        }
        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(send_response), stderr=""
            ),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(get_response), stderr=""
            ),
        ]

        mocker.patch("remote.connection_ssm.time.sleep")

        provider = SSMConnectionProvider()
        exit_code, stdout, stderr = provider.execute_command(
            instance_id="i-123456789",
            dns="example.com",
            command=["false"],
            user="ubuntu",
        )

        assert exit_code == 1
        assert stderr == "error message"

    def test_should_raise_ssm_error_when_aws_cli_not_found(self, mocker):
        """Should raise SSMError when AWS CLI is not installed."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.side_effect = FileNotFoundError("aws not found")

        provider = SSMConnectionProvider()

        with pytest.raises(SSMError) as exc_info:
            provider.execute_command(
                instance_id="i-123456789",
                dns="example.com",
                command=["whoami"],
                user="ubuntu",
            )

        assert "AWS CLI not found" in str(exc_info.value)


class TestSSMPortForward:
    """Test SSM port forwarding."""

    def test_should_call_start_session_with_port_forwarding_document(self, mocker):
        """Should call start-session with AWS-StartPortForwardingSession document."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSMConnectionProvider()
        exit_code = provider.port_forward(
            instance_id="i-123456789",
            dns="example.com",
            local_port=8080,
            remote_port=80,
            user="ubuntu",
        )

        assert exit_code == 0
        mock_run.assert_called_once()

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "aws"
        assert call_args[1] == "ssm"
        assert call_args[2] == "start-session"
        assert "--document-name" in call_args
        assert "AWS-StartPortForwardingSession" in call_args

    def test_should_include_port_numbers_in_parameters(self, mocker):
        """Should include port numbers in session parameters."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSMConnectionProvider()
        provider.port_forward(
            instance_id="i-123456789",
            dns="example.com",
            local_port=8080,
            remote_port=3000,
            user="ubuntu",
        )

        call_args = mock_run.call_args[0][0]
        params_idx = call_args.index("--parameters") + 1
        params = json.loads(call_args[params_idx])

        assert params["portNumber"] == ["3000"]
        assert params["localPortNumber"] == ["8080"]

    def test_should_raise_ssm_error_when_aws_cli_not_found(self, mocker):
        """Should raise SSMError when AWS CLI is not installed."""
        from remote.connection_ssm import SSMConnectionProvider

        mock_run = mocker.patch("remote.connection_ssm.subprocess.run")
        mock_run.side_effect = FileNotFoundError("aws not found")

        provider = SSMConnectionProvider()

        with pytest.raises(SSMError) as exc_info:
            provider.port_forward(
                instance_id="i-123456789",
                dns="example.com",
                local_port=8080,
                remote_port=80,
                user="ubuntu",
            )

        assert "AWS CLI not found" in str(exc_info.value)


class TestSSMExceptions:
    """Test SSM exception handling."""

    def test_ssm_error_should_include_troubleshooting_tips(self):
        """SSMError should include helpful troubleshooting information."""
        error = SSMError("start-session", "Connection refused")

        assert "SSM Agent" in str(error)
        assert "AmazonSSMManagedInstanceCore" in str(error)
        assert "Session Manager plugin" in str(error)
