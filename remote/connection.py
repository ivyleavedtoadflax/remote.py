"""Connection provider abstraction for remote connections.

This module defines the protocol for connection providers and provides
factory functions for creating providers based on configuration.
"""

from enum import Enum
from typing import Protocol

from remote.config import config_manager


class ConnectionMethod(Enum):
    """Available connection methods for remote access."""

    SSH = "ssh"
    SSM = "ssm"


def parse_connection_method(value: str) -> ConnectionMethod:
    """Parse a connection method from a string.

    Args:
        value: String value to parse (case-insensitive)

    Returns:
        ConnectionMethod enum value

    Raises:
        ValueError: If the value is not a valid connection method
    """
    normalized = value.lower()
    try:
        return ConnectionMethod(normalized)
    except ValueError:
        valid_methods = [m.value for m in ConnectionMethod]
        raise ValueError(
            f"Invalid connection method '{value}'. Valid methods: {', '.join(valid_methods)}"
        )


class ConnectionProvider(Protocol):
    """Protocol defining the interface for connection providers.

    All connection providers (SSH, SSM) must implement this interface
    to ensure consistent behavior across different connection methods.
    """

    def connect_interactive(
        self,
        instance_id: str,
        dns: str,
        user: str,
        key_path: str | None = None,
        verbose: bool = False,
        timeout: int | None = None,
        port_forward: str | None = None,
        no_strict_host_key: bool = False,
    ) -> int:
        """Start an interactive shell session with the remote instance.

        Args:
            instance_id: AWS instance ID
            dns: DNS hostname or IP address
            user: Username for the connection
            key_path: Path to SSH private key (SSH only)
            verbose: Enable verbose mode
            timeout: Session timeout in seconds
            port_forward: Port forwarding specification
            no_strict_host_key: Disable strict host key checking (SSH only)

        Returns:
            Exit code from the session
        """
        ...

    def execute_command(
        self,
        instance_id: str,
        dns: str,
        command: list[str],
        user: str,
        key_path: str | None = None,
        verbose: bool = False,
        timeout: int = 30,
        no_strict_host_key: bool = False,
    ) -> tuple[int, str, str]:
        """Execute a command on the remote instance.

        Args:
            instance_id: AWS instance ID
            dns: DNS hostname or IP address
            command: Command to execute as list of arguments
            user: Username for the connection
            key_path: Path to SSH private key (SSH only)
            verbose: Enable verbose mode
            timeout: Command timeout in seconds
            no_strict_host_key: Disable strict host key checking (SSH only)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        ...

    def port_forward(
        self,
        instance_id: str,
        dns: str,
        local_port: int,
        remote_port: int,
        user: str,
        key_path: str | None = None,
        verbose: bool = False,
        no_strict_host_key: bool = False,
    ) -> int:
        """Forward a port from the remote instance to localhost.

        Args:
            instance_id: AWS instance ID
            dns: DNS hostname or IP address
            local_port: Local port to bind
            remote_port: Remote port to forward
            user: Username for the connection
            key_path: Path to SSH private key (SSH only)
            verbose: Enable verbose mode
            no_strict_host_key: Disable strict host key checking (SSH only)

        Returns:
            Exit code from the port forwarding session
        """
        ...

    def supports_file_transfer(self) -> bool:
        """Check if this provider supports file transfer operations.

        Returns:
            True if file transfer (copy/sync) is supported, False otherwise.
            SSH providers return True (rsync support).
            SSM providers return False (no built-in file transfer).
        """
        ...


def get_connection_provider(method: ConnectionMethod) -> ConnectionProvider:
    """Get a connection provider for the specified method.

    Args:
        method: The connection method to use

    Returns:
        A connection provider instance implementing ConnectionProvider protocol
    """
    if method == ConnectionMethod.SSH:
        from remote.connection_ssh import SSHConnectionProvider

        return SSHConnectionProvider()
    elif method == ConnectionMethod.SSM:
        from remote.connection_ssm import SSMConnectionProvider

        return SSMConnectionProvider()
    else:
        # This should never happen due to enum exhaustiveness
        raise ValueError(f"Unknown connection method: {method}")


def resolve_connection_method(cli_value: str | None) -> ConnectionMethod:
    """Resolve the connection method to use based on CLI argument or config.

    Priority order:
    1. CLI argument (--connection)
    2. Config file (connection_method)
    3. Default (SSH)

    Args:
        cli_value: Value from CLI argument, or None if not provided

    Returns:
        The resolved ConnectionMethod
    """
    # CLI argument takes precedence
    if cli_value is not None:
        return parse_connection_method(cli_value)

    # Check config file
    config_value = config_manager.get_value("connection_method")
    if config_value is not None:
        return parse_connection_method(config_value)

    # Default to SSH for backward compatibility
    return ConnectionMethod.SSH
