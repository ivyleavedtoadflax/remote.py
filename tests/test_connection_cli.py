"""Tests for CLI integration of connection methods."""

from typer.testing import CliRunner

from remote.instance import app

runner = CliRunner()


class TestConnectCommandConnectionOption:
    """Test the --connection option for the connect command."""

    def test_should_use_ssh_connection_by_default(self, mocker):
        """Should use SSH connection when no --connection option provided."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="test.example.com")
        mocker.patch("remote.instance._ensure_ssh_key", return_value="/path/to/key")

        # Mock the SSH provider
        mock_ssh_provider = mocker.MagicMock()
        mock_ssh_provider.connect_interactive.return_value = 0
        mocker.patch(
            "remote.connection.get_connection_provider",
            return_value=mock_ssh_provider,
        )

        result = runner.invoke(app, ["connect", "test-instance"])

        assert result.exit_code == 0
        mock_ssh_provider.connect_interactive.assert_called_once()

    def test_should_use_ssm_connection_with_option(self, mocker):
        """Should use SSM connection when --connection ssm is provided."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="")

        # Mock the SSM provider
        mock_ssm_provider = mocker.MagicMock()
        mock_ssm_provider.connect_interactive.return_value = 0

        # Patch to return SSM provider when SSM method requested
        def mock_provider(method):
            from remote.connection import ConnectionMethod

            if method == ConnectionMethod.SSM:
                return mock_ssm_provider
            return mocker.MagicMock()

        mocker.patch("remote.connection.get_connection_provider", side_effect=mock_provider)

        result = runner.invoke(app, ["connect", "test-instance", "--connection", "ssm"])

        assert result.exit_code == 0
        mock_ssm_provider.connect_interactive.assert_called_once()

    def test_should_ignore_whitelist_ip_with_ssm(self, mocker):
        """Should warn that --whitelist-ip is ignored with SSM."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="")

        mock_ssm_provider = mocker.MagicMock()
        mock_ssm_provider.connect_interactive.return_value = 0

        def mock_provider(method):
            from remote.connection import ConnectionMethod

            if method == ConnectionMethod.SSM:
                return mock_ssm_provider
            return mocker.MagicMock()

        mocker.patch("remote.connection.get_connection_provider", side_effect=mock_provider)

        # Whitelist should NOT be called for SSM
        mock_whitelist = mocker.patch("remote.sg.whitelist_ip_for_instance")

        result = runner.invoke(
            app, ["connect", "test-instance", "--connection", "ssm", "--whitelist-ip"]
        )

        assert result.exit_code == 0
        assert "--whitelist-ip is ignored with SSM" in result.stdout
        mock_whitelist.assert_not_called()


class TestExecCommandConnectionOption:
    """Test the --connection option for the exec command."""

    def test_should_use_ssh_by_default(self, mocker):
        """Should use SSH for exec when no --connection option provided."""
        mocker.patch("remote.instance.get_instance_id", return_value="i-123")
        mocker.patch("remote.instance.get_instance_name", return_value="test")
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="test.example.com")
        mocker.patch("remote.instance._ensure_ssh_key", return_value="/path/to/key")

        mock_ssh_provider = mocker.MagicMock()
        mock_ssh_provider.execute_command.return_value = (0, "output", "")
        mocker.patch(
            "remote.connection.get_connection_provider",
            return_value=mock_ssh_provider,
        )

        result = runner.invoke(app, ["exec", "test-instance", "whoami"])

        assert result.exit_code == 0
        mock_ssh_provider.execute_command.assert_called_once()

    def test_should_use_ssm_with_option(self, mocker):
        """Should use SSM for exec when --connection ssm is provided."""
        mocker.patch("remote.instance.get_instance_id", return_value="i-123")
        mocker.patch("remote.instance.get_instance_name", return_value="test")
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="")

        mock_ssm_provider = mocker.MagicMock()
        mock_ssm_provider.execute_command.return_value = (0, "output", "")

        def mock_provider(method):
            from remote.connection import ConnectionMethod

            if method == ConnectionMethod.SSM:
                return mock_ssm_provider
            return mocker.MagicMock()

        mocker.patch("remote.connection.get_connection_provider", side_effect=mock_provider)

        result = runner.invoke(app, ["exec", "--connection", "ssm", "test-instance", "whoami"])

        assert result.exit_code == 0
        mock_ssm_provider.execute_command.assert_called_once()


class TestForwardCommandConnectionOption:
    """Test the --connection option for the forward command."""

    def test_should_use_ssh_by_default(self, mocker):
        """Should use SSH for forward when no --connection option provided."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="test.example.com")
        mocker.patch("remote.instance._ensure_ssh_key", return_value="/path/to/key")
        mocker.patch("remote.instance.webbrowser.open")

        mock_ssh_provider = mocker.MagicMock()
        mock_ssh_provider.port_forward.return_value = 0
        mocker.patch(
            "remote.connection.get_connection_provider",
            return_value=mock_ssh_provider,
        )

        result = runner.invoke(app, ["forward", "8080", "test-instance", "--no-browser"])

        assert result.exit_code == 0
        mock_ssh_provider.port_forward.assert_called_once()

    def test_should_use_ssm_with_option(self, mocker):
        """Should use SSM for forward when --connection ssm is provided."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="")
        mocker.patch("remote.instance.webbrowser.open")

        mock_ssm_provider = mocker.MagicMock()
        mock_ssm_provider.port_forward.return_value = 0

        def mock_provider(method):
            from remote.connection import ConnectionMethod

            if method == ConnectionMethod.SSM:
                return mock_ssm_provider
            return mocker.MagicMock()

        mocker.patch("remote.connection.get_connection_provider", side_effect=mock_provider)

        result = runner.invoke(
            app, ["forward", "8080", "test-instance", "--connection", "ssm", "--no-browser"]
        )

        assert result.exit_code == 0
        mock_ssm_provider.port_forward.assert_called_once()


class TestCopyCommandWithSSM:
    """Test that copy command fails gracefully with SSM."""

    def test_should_fail_with_ssm_connection(self, mocker):
        """Should show helpful error when SSM is used for copy."""
        result = runner.invoke(app, ["copy", "--connection", "ssm", "./local", "test:/remote"])

        assert result.exit_code == 1
        assert "File transfer is not supported with SSM" in result.stdout
        assert "Use --connection ssh" in result.stdout


class TestSyncCommandWithSSM:
    """Test that sync command fails gracefully with SSM."""

    def test_should_fail_with_ssm_connection(self, mocker):
        """Should show helpful error when SSM is used for sync."""
        result = runner.invoke(app, ["sync", "--connection", "ssm", "./local", "test:/remote"])

        assert result.exit_code == 1
        assert "File transfer is not supported with SSM" in result.stdout
        assert "Use --connection ssh" in result.stdout


class TestWhitelistPortsOption:
    """Test the --whitelist-ports option for the connect command."""

    def test_should_reject_whitelist_ports_without_whitelist_ip(self, mocker):
        """Should error when --whitelist-ports is used without --whitelist-ip."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )

        result = runner.invoke(app, ["connect", "test-instance", "--whitelist-ports", "ssh"])

        assert result.exit_code == 1
        assert "--whitelist-ports can only be used with --whitelist-ip" in result.stdout

    def test_should_whitelist_multiple_ports(self, mocker):
        """Should whitelist multiple ports when --whitelist-ports is specified."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="test.example.com")
        mocker.patch("remote.instance._ensure_ssh_key", return_value="/path/to/key")

        mock_ssh_provider = mocker.MagicMock()
        mock_ssh_provider.connect_interactive.return_value = 0
        mocker.patch(
            "remote.connection.get_connection_provider",
            return_value=mock_ssh_provider,
        )

        mock_whitelist = mocker.patch(
            "remote.sg.whitelist_ip_for_instance",
            return_value=("203.0.113.1", ["sg-12345"]),
        )
        mocker.patch("remote.sg.resolve_port", side_effect=[22, 22000])

        result = runner.invoke(
            app,
            [
                "connect",
                "test-instance",
                "--whitelist-ip",
                "--whitelist-ports",
                "ssh",
                "--whitelist-ports",
                "syncthing",
            ],
        )

        assert result.exit_code == 0
        mock_whitelist.assert_called_once()
        call_kwargs = mock_whitelist.call_args
        assert call_kwargs.kwargs.get("ports") == [22, 22000]

    def test_should_default_to_ssh_without_whitelist_ports(self, mocker):
        """Should whitelist only SSH port when --whitelist-ports is not specified."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="test.example.com")
        mocker.patch("remote.instance._ensure_ssh_key", return_value="/path/to/key")

        mock_ssh_provider = mocker.MagicMock()
        mock_ssh_provider.connect_interactive.return_value = 0
        mocker.patch(
            "remote.connection.get_connection_provider",
            return_value=mock_ssh_provider,
        )

        mock_whitelist = mocker.patch(
            "remote.sg.whitelist_ip_for_instance",
            return_value=("203.0.113.1", ["sg-12345"]),
        )

        result = runner.invoke(
            app,
            ["connect", "test-instance", "--whitelist-ip"],
        )

        assert result.exit_code == 0
        mock_whitelist.assert_called_once()
        call_kwargs = mock_whitelist.call_args
        # Without --whitelist-ports, resolved_ports should be None
        assert call_kwargs.kwargs.get("ports") is None


class TestSSMProfileOption:
    """Test the --ssm-profile option."""

    def test_should_use_ssm_profile_when_specified(self, mocker):
        """Should create SSMConnectionProvider with profile when specified."""
        mocker.patch(
            "remote.instance.resolve_instance_or_exit",
            return_value=("test-instance", "i-123"),
        )
        mocker.patch("remote.instance._ensure_instance_running")
        mocker.patch("remote.instance.get_instance_dns", return_value="")

        # Spy on SSMConnectionProvider to verify it's created with the profile
        mock_provider_instance = mocker.MagicMock()
        mock_provider_instance.connect_interactive.return_value = 0

        mock_provider_class = mocker.patch(
            "remote.connection_ssm.SSMConnectionProvider",
            return_value=mock_provider_instance,
        )

        result = runner.invoke(
            app,
            ["connect", "test-instance", "--connection", "ssm", "--ssm-profile", "my-profile"],
        )

        assert result.exit_code == 0
        # Called twice: once by get_connection_provider(), then again with ssm_profile
        # The second call is the one with the profile
        calls = mock_provider_class.call_args_list
        assert len(calls) == 2
        assert calls[1] == mocker.call(ssm_profile="my-profile")
