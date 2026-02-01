"""SSH connection provider implementation.

This module provides SSH-based connection functionality extracted from instance.py,
implementing the ConnectionProvider protocol for SSH connections.
"""

import subprocess

from remote.settings import (
    DEFAULT_SSH_USER,
    SSH_SERVER_ALIVE_COUNT_MAX,
    SSH_SERVER_ALIVE_INTERVAL,
)


class SSHConnectionProvider:
    """SSH-based connection provider.

    Implements the ConnectionProvider protocol using OpenSSH client for
    interactive sessions, command execution, and port forwarding.
    """

    def _build_ssh_command(
        self,
        dns: str,
        key: str | None = None,
        user: str = DEFAULT_SSH_USER,
        no_strict_host_key: bool = False,
        verbose: bool = False,
        interactive: bool = False,
        port_forward: str | None = None,
    ) -> list[str]:
        """Build base SSH command arguments with standard options.

        Args:
            dns: The DNS hostname or IP address to connect to
            key: Optional path to SSH private key
            user: SSH username (default: ubuntu)
            no_strict_host_key: If True, use StrictHostKeyChecking=no (less secure)
            verbose: If True, enable SSH verbose mode
            interactive: If True, omit BatchMode and ConnectTimeout for interactive sessions
            port_forward: Optional port forwarding specification (e.g., "8080:localhost:80")

        Returns:
            List of SSH command arguments ready for subprocess
        """
        strict_host_key_value = "no" if no_strict_host_key else "accept-new"
        ssh_args = [
            "ssh",
            "-o",
            f"StrictHostKeyChecking={strict_host_key_value}",
        ]

        # Non-interactive sessions use BatchMode and timeout
        if not interactive:
            ssh_args.extend(["-o", "BatchMode=yes"])
            ssh_args.extend(["-o", "ConnectTimeout=10"])
        else:
            # Interactive sessions use keepalive to detect dead connections
            # instead of a subprocess timeout which would kill active sessions
            ssh_args.extend(["-o", f"ServerAliveInterval={SSH_SERVER_ALIVE_INTERVAL}"])
            ssh_args.extend(["-o", f"ServerAliveCountMax={SSH_SERVER_ALIVE_COUNT_MAX}"])

        if key:
            ssh_args.extend(["-i", key])

        if verbose:
            ssh_args.append("-v")

        if port_forward:
            ssh_args.extend(["-L", port_forward])

        ssh_args.append(f"{user}@{dns}")
        return ssh_args

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
        """Start an interactive SSH shell session.

        Args:
            instance_id: AWS instance ID (not used for SSH, included for protocol)
            dns: DNS hostname or IP address
            user: SSH username
            key_path: Path to SSH private key
            verbose: Enable SSH verbose mode
            timeout: Session timeout in seconds (0 or None = no timeout)
            port_forward: Port forwarding specification
            no_strict_host_key: Disable strict host key checking

        Returns:
            Exit code from SSH session
        """
        ssh_command = self._build_ssh_command(
            dns,
            key=key_path,
            user=user,
            no_strict_host_key=no_strict_host_key,
            verbose=verbose,
            interactive=True,
            port_forward=port_forward,
        )

        # Use timeout if specified (0 or None means no timeout)
        timeout_value = timeout if timeout and timeout > 0 else None
        result = subprocess.run(ssh_command, timeout=timeout_value)
        return result.returncode

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
        """Execute a command on the remote instance via SSH.

        Args:
            instance_id: AWS instance ID (not used for SSH, included for protocol)
            dns: DNS hostname or IP address
            command: Command to execute as list of arguments
            user: SSH username
            key_path: Path to SSH private key
            verbose: Enable SSH verbose mode
            timeout: Command timeout in seconds
            no_strict_host_key: Disable strict host key checking

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        ssh_args = self._build_ssh_command(
            dns,
            key=key_path,
            user=user,
            no_strict_host_key=no_strict_host_key,
            verbose=verbose,
        )

        # Append the remote command
        ssh_args.extend(command)

        result = subprocess.run(
            ssh_args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return result.returncode, result.stdout, result.stderr

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
        """Forward a port from the remote instance to localhost via SSH.

        Args:
            instance_id: AWS instance ID (not used for SSH, included for protocol)
            dns: DNS hostname or IP address
            local_port: Local port to bind
            remote_port: Remote port to forward
            user: SSH username
            key_path: Path to SSH private key
            verbose: Enable SSH verbose mode
            no_strict_host_key: Disable strict host key checking

        Returns:
            Exit code from SSH port forwarding session
        """
        # Build port forwarding specification for SSH -L option
        # Format: local_port:localhost:remote_port
        port_forward_spec = f"{local_port}:localhost:{remote_port}"

        ssh_command = self._build_ssh_command(
            dns,
            key=key_path,
            user=user,
            no_strict_host_key=no_strict_host_key,
            verbose=verbose,
            interactive=True,
            port_forward=port_forward_spec,
        )

        # Add -N flag to not execute a remote command (just forward ports)
        ssh_command.insert(1, "-N")

        result = subprocess.run(ssh_command)
        return result.returncode

    def supports_file_transfer(self) -> bool:
        """SSH supports file transfer via rsync.

        Returns:
            True - SSH can use rsync for file transfer
        """
        return True
