"""Tests for the connection module."""

from enum import Enum

import pytest


class TestConnectionMethod:
    """Test the ConnectionMethod enum."""

    def test_should_define_ssh_method(self):
        """ConnectionMethod should have an SSH value."""
        from remote.connection import ConnectionMethod

        assert hasattr(ConnectionMethod, "SSH")
        assert ConnectionMethod.SSH.value == "ssh"

    def test_should_define_ssm_method(self):
        """ConnectionMethod should have an SSM value."""
        from remote.connection import ConnectionMethod

        assert hasattr(ConnectionMethod, "SSM")
        assert ConnectionMethod.SSM.value == "ssm"

    def test_should_be_an_enum(self):
        """ConnectionMethod should be an Enum subclass."""
        from remote.connection import ConnectionMethod

        assert issubclass(ConnectionMethod, Enum)


class TestConnectionMethodFromString:
    """Test parsing connection method from string."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("ssh", "SSH"),
            ("SSH", "SSH"),
            ("ssm", "SSM"),
            ("SSM", "SSM"),
        ],
    )
    def test_should_parse_valid_connection_method(self, input_str, expected):
        """Should parse valid connection method strings."""
        from remote.connection import ConnectionMethod, parse_connection_method

        result = parse_connection_method(input_str)
        assert result == getattr(ConnectionMethod, expected)

    def test_should_raise_for_invalid_connection_method(self):
        """Should raise ValueError for invalid connection method."""
        from remote.connection import parse_connection_method

        with pytest.raises(ValueError) as exc_info:
            parse_connection_method("invalid")

        assert "Invalid connection method" in str(exc_info.value)
        assert "ssh" in str(exc_info.value).lower()
        assert "ssm" in str(exc_info.value).lower()


class TestConnectionProviderProtocol:
    """Test the ConnectionProvider protocol."""

    def test_should_require_connect_interactive_method(self):
        """ConnectionProvider should define connect_interactive method."""

        from remote.connection import ConnectionProvider

        # Check that the protocol has the expected method
        assert hasattr(ConnectionProvider, "connect_interactive")

    def test_should_require_execute_command_method(self):
        """ConnectionProvider should define execute_command method."""
        from remote.connection import ConnectionProvider

        assert hasattr(ConnectionProvider, "execute_command")

    def test_should_require_port_forward_method(self):
        """ConnectionProvider should define port_forward method."""
        from remote.connection import ConnectionProvider

        assert hasattr(ConnectionProvider, "port_forward")

    def test_should_require_supports_file_transfer_method(self):
        """ConnectionProvider should define supports_file_transfer method."""
        from remote.connection import ConnectionProvider

        assert hasattr(ConnectionProvider, "supports_file_transfer")


class TestGetConnectionProvider:
    """Test the connection provider factory function."""

    def test_should_return_ssh_provider_for_ssh_method(self):
        """Should return SSHConnectionProvider for SSH method."""
        from remote.connection import ConnectionMethod, get_connection_provider
        from remote.connection_ssh import SSHConnectionProvider

        provider = get_connection_provider(ConnectionMethod.SSH)
        assert isinstance(provider, SSHConnectionProvider)

    def test_should_return_ssm_provider_for_ssm_method(self):
        """Should return SSMConnectionProvider for SSM method."""
        from remote.connection import ConnectionMethod, get_connection_provider
        from remote.connection_ssm import SSMConnectionProvider

        provider = get_connection_provider(ConnectionMethod.SSM)
        assert isinstance(provider, SSMConnectionProvider)


class TestResolveConnectionMethod:
    """Test resolving connection method from CLI, config, and defaults."""

    def test_should_use_cli_argument_when_provided(self, mocker):
        """Should use CLI argument over config and default."""
        from remote.connection import ConnectionMethod, resolve_connection_method

        # Mock config to return SSM
        mock_config = mocker.patch("remote.connection.config_manager")
        mock_config.get_value.return_value = "ssm"

        # CLI argument should take precedence
        result = resolve_connection_method("ssh")
        assert result == ConnectionMethod.SSH

    def test_should_use_config_when_cli_argument_not_provided(self, mocker):
        """Should fall back to config when CLI argument is None."""
        from remote.connection import ConnectionMethod, resolve_connection_method

        mock_config = mocker.patch("remote.connection.config_manager")
        mock_config.get_value.return_value = "ssm"

        result = resolve_connection_method(None)
        assert result == ConnectionMethod.SSM

    def test_should_default_to_ssh_when_no_config(self, mocker):
        """Should default to SSH when no config or CLI argument."""
        from remote.connection import ConnectionMethod, resolve_connection_method

        mock_config = mocker.patch("remote.connection.config_manager")
        mock_config.get_value.return_value = None

        result = resolve_connection_method(None)
        assert result == ConnectionMethod.SSH
