"""Tests for the SSH connection provider."""

import subprocess


class TestSSHConnectionProvider:
    """Test the SSH connection provider."""

    def test_should_support_file_transfer(self):
        """SSH provider should report that it supports file transfer."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        assert provider.supports_file_transfer() is True


class TestSSHBuildCommand:
    """Test SSH command building."""

    def test_should_include_strict_host_key_accept_new_by_default(self):
        """Should use StrictHostKeyChecking=accept-new by default."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command("example.com", user="ubuntu")

        assert "-o" in cmd
        assert "StrictHostKeyChecking=accept-new" in cmd

    def test_should_use_strict_host_key_no_when_disabled(self):
        """Should use StrictHostKeyChecking=no when no_strict_host_key is True."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command("example.com", user="ubuntu", no_strict_host_key=True)

        assert "StrictHostKeyChecking=no" in cmd

    def test_should_include_batch_mode_for_non_interactive(self):
        """Should include BatchMode=yes for non-interactive sessions."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command("example.com", user="ubuntu", interactive=False)

        assert "BatchMode=yes" in cmd
        assert "ConnectTimeout=10" in cmd

    def test_should_include_keepalive_for_interactive(self):
        """Should include ServerAliveInterval for interactive sessions."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command("example.com", user="ubuntu", interactive=True)

        # Should NOT have BatchMode
        assert "BatchMode=yes" not in cmd
        # Should have keepalive settings
        assert any("ServerAliveInterval" in arg for arg in cmd)
        assert any("ServerAliveCountMax" in arg for arg in cmd)

    def test_should_include_key_path_when_provided(self):
        """Should include -i key_path when key is provided."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command("example.com", key="/path/to/key.pem", user="ubuntu")

        assert "-i" in cmd
        assert "/path/to/key.pem" in cmd

    def test_should_include_verbose_flag_when_enabled(self):
        """Should include -v flag when verbose is True."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command("example.com", user="ubuntu", verbose=True)

        assert "-v" in cmd

    def test_should_include_port_forward_option(self):
        """Should include -L option for port forwarding."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command(
            "example.com", user="ubuntu", port_forward="8080:localhost:80"
        )

        assert "-L" in cmd
        assert "8080:localhost:80" in cmd

    def test_should_format_user_at_host_correctly(self):
        """Should format user@host as last argument."""
        from remote.connection_ssh import SSHConnectionProvider

        provider = SSHConnectionProvider()
        cmd = provider._build_ssh_command("example.com", user="ec2-user")

        assert cmd[-1] == "ec2-user@example.com"


class TestSSHConnectInteractive:
    """Test SSH interactive connection."""

    def test_should_call_subprocess_run_with_correct_args(self, mocker):
        """Should call subprocess.run with built SSH command."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSHConnectionProvider()
        exit_code = provider.connect_interactive(
            instance_id="i-123",
            dns="example.com",
            user="ubuntu",
            key_path="/path/to/key.pem",
        )

        assert exit_code == 0
        mock_run.assert_called_once()

        # Verify key components of the command
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "ssh" in cmd
        assert "ubuntu@example.com" in cmd
        assert "-i" in cmd
        assert "/path/to/key.pem" in cmd

    def test_should_use_timeout_when_specified(self, mocker):
        """Should pass timeout to subprocess.run when specified."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSHConnectionProvider()
        provider.connect_interactive(
            instance_id="i-123",
            dns="example.com",
            user="ubuntu",
            timeout=3600,
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 3600

    def test_should_use_no_timeout_when_zero(self, mocker):
        """Should use None timeout when timeout is 0."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSHConnectionProvider()
        provider.connect_interactive(
            instance_id="i-123",
            dns="example.com",
            user="ubuntu",
            timeout=0,
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] is None


class TestSSHExecuteCommand:
    """Test SSH command execution."""

    def test_should_return_stdout_and_stderr(self, mocker):
        """Should return exit code, stdout, and stderr from subprocess."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="output", stderr="errors"
        )

        provider = SSHConnectionProvider()
        exit_code, stdout, stderr = provider.execute_command(
            instance_id="i-123",
            dns="example.com",
            command=["whoami"],
            user="ubuntu",
        )

        assert exit_code == 0
        assert stdout == "output"
        assert stderr == "errors"

    def test_should_append_command_to_ssh_args(self, mocker):
        """Should append the remote command to SSH arguments."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        provider = SSHConnectionProvider()
        provider.execute_command(
            instance_id="i-123",
            dns="example.com",
            command=["ls", "-la", "/tmp"],
            user="ubuntu",
        )

        call_args = mock_run.call_args[0][0]
        # Command should be at the end
        assert call_args[-3:] == ["ls", "-la", "/tmp"]

    def test_should_use_specified_timeout(self, mocker):
        """Should pass timeout to subprocess.run."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )

        provider = SSHConnectionProvider()
        provider.execute_command(
            instance_id="i-123",
            dns="example.com",
            command=["whoami"],
            user="ubuntu",
            timeout=60,
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 60


class TestSSHPortForward:
    """Test SSH port forwarding."""

    def test_should_include_port_forward_specification(self, mocker):
        """Should include correct -L option for port forwarding."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSHConnectionProvider()
        provider.port_forward(
            instance_id="i-123",
            dns="example.com",
            local_port=8080,
            remote_port=80,
            user="ubuntu",
        )

        call_args = mock_run.call_args[0][0]
        assert "-L" in call_args
        assert "8080:localhost:80" in call_args

    def test_should_include_no_command_flag(self, mocker):
        """Should include -N flag for no remote command."""
        from remote.connection_ssh import SSHConnectionProvider

        mock_run = mocker.patch("remote.connection_ssh.subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

        provider = SSHConnectionProvider()
        provider.port_forward(
            instance_id="i-123",
            dns="example.com",
            local_port=8080,
            remote_port=80,
            user="ubuntu",
        )

        call_args = mock_run.call_args[0][0]
        assert "-N" in call_args
