"""SSM (AWS Systems Manager) connection provider implementation.

This module provides SSM-based connection functionality implementing the
ConnectionProvider protocol. SSM allows instance access without SSH keys
or open inbound ports, using IAM for authentication.
"""

import json
import subprocess
import time

from remote.exceptions import SSMError
from remote.settings import (
    SSM_COMMAND_TIMEOUT_SECONDS,
    SSM_DEFAULT_SHELL_USER,
    SSM_MAX_POLL_ATTEMPTS,
    SSM_POLL_INTERVAL_SECONDS,
)
from remote.utils import print_warning


class SSMConnectionProvider:
    """SSM-based connection provider.

    Implements the ConnectionProvider protocol using AWS Systems Manager
    Session Manager for interactive sessions, send-command for execution,
    and port forwarding sessions.

    Key differences from SSH:
    - No SSH keys required - uses IAM authentication
    - No inbound ports needed - SSM Agent polls AWS outbound
    - All sessions logged in CloudTrail
    - Does not support file transfer (rsync)
    """

    def __init__(self, ssm_profile: str | None = None):
        """Initialize SSM connection provider.

        Args:
            ssm_profile: Optional AWS profile to use for SSM commands
        """
        self.ssm_profile = ssm_profile

    def _get_profile_args(self) -> list[str]:
        """Get AWS profile arguments if configured.

        Returns:
            List of profile arguments for AWS CLI, or empty list
        """
        if self.ssm_profile:
            return ["--profile", self.ssm_profile]
        return []

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
        """Start an interactive SSM session with the instance.

        SSM sessions default to ssm-user in a system directory. To match
        SSH experience, this uses AWS-StartInteractiveCommand to switch
        to the ubuntu user in their home directory.

        Args:
            instance_id: AWS instance ID
            dns: DNS hostname (not used for SSM, included for protocol)
            user: Target user to switch to after connecting
            key_path: Not used for SSM (included for protocol compatibility)
            verbose: Enable verbose output
            timeout: Session timeout (not enforced by SSM, included for protocol)
            port_forward: Not supported - use port_forward method instead
            no_strict_host_key: Not used for SSM (included for protocol)

        Returns:
            Exit code from SSM session
        """
        if port_forward:
            print_warning(
                "Port forwarding via --port-forward is not supported with SSM connect. "
                "Use 'remote instance forward --connection ssm' instead."
            )

        # Build the SSM start-session command
        # Use AWS-StartInteractiveCommand to switch to the target user
        target_user = user if user else SSM_DEFAULT_SHELL_USER
        command = f"sudo su - {target_user}"

        ssm_args = [
            "aws",
            "ssm",
            "start-session",
            "--target",
            instance_id,
            "--document-name",
            "AWS-StartInteractiveCommand",
            "--parameters",
            json.dumps({"command": [command]}),
        ]

        ssm_args.extend(self._get_profile_args())

        if verbose:
            print_warning(f"SSM command: {' '.join(ssm_args)}")

        try:
            result = subprocess.run(ssm_args)
            return result.returncode
        except FileNotFoundError:
            raise SSMError(
                "start-session",
                "AWS CLI not found. Please install the AWS CLI and Session Manager plugin.",
            )

    def execute_command(
        self,
        instance_id: str,
        dns: str,
        command: list[str],
        user: str,
        key_path: str | None = None,
        verbose: bool = False,
        timeout: int = SSM_COMMAND_TIMEOUT_SECONDS,
        no_strict_host_key: bool = False,
    ) -> tuple[int, str, str]:
        """Execute a command on the instance via SSM send-command.

        Uses AWS SSM send-command with AWS-RunShellScript document,
        then polls for completion and retrieves output.

        Args:
            instance_id: AWS instance ID
            dns: DNS hostname (not used for SSM, included for protocol)
            command: Command to execute as list of arguments
            user: Not used for SSM send-command (runs as root)
            key_path: Not used for SSM (included for protocol compatibility)
            verbose: Enable verbose output
            timeout: Command timeout in seconds
            no_strict_host_key: Not used for SSM (included for protocol)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        # Join command list into a single command string
        command_str = " ".join(command)

        # Send the command
        send_args = [
            "aws",
            "ssm",
            "send-command",
            "--instance-ids",
            instance_id,
            "--document-name",
            "AWS-RunShellScript",
            "--parameters",
            json.dumps({"commands": [command_str]}),
            "--timeout-seconds",
            str(timeout),
            "--output",
            "json",
        ]
        send_args.extend(self._get_profile_args())

        if verbose:
            print_warning(f"SSM send-command: {' '.join(send_args)}")

        try:
            send_result = subprocess.run(
                send_args,
                capture_output=True,
                text=True,
                timeout=timeout + 10,  # Extra buffer for API call
            )
        except FileNotFoundError:
            raise SSMError(
                "send-command",
                "AWS CLI not found. Please install the AWS CLI.",
            )
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out waiting for send-command"

        if send_result.returncode != 0:
            return send_result.returncode, "", send_result.stderr

        # Parse response to get command ID
        try:
            response = json.loads(send_result.stdout)
            command_id = response["Command"]["CommandId"]
        except (json.JSONDecodeError, KeyError) as e:
            return 1, "", f"Failed to parse send-command response: {e}"

        if verbose:
            print_warning(f"SSM command ID: {command_id}")

        # Poll for command completion
        return self._wait_for_command(instance_id, command_id, timeout, verbose)

    def _wait_for_command(
        self,
        instance_id: str,
        command_id: str,
        timeout: int,
        verbose: bool,
    ) -> tuple[int, str, str]:
        """Wait for SSM command to complete and retrieve output.

        Args:
            instance_id: AWS instance ID
            command_id: SSM command ID to wait for
            timeout: Maximum time to wait
            verbose: Enable verbose output

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        get_output_args = [
            "aws",
            "ssm",
            "get-command-invocation",
            "--command-id",
            command_id,
            "--instance-id",
            instance_id,
            "--output",
            "json",
        ]
        get_output_args.extend(self._get_profile_args())

        max_attempts = min(SSM_MAX_POLL_ATTEMPTS, timeout // SSM_POLL_INTERVAL_SECONDS)

        for attempt in range(max_attempts):
            time.sleep(SSM_POLL_INTERVAL_SECONDS)

            try:
                result = subprocess.run(
                    get_output_args,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                continue

            if result.returncode != 0:
                # Command may not be ready yet
                if verbose:
                    print_warning(f"Poll attempt {attempt + 1}: waiting for command...")
                continue

            try:
                response = json.loads(result.stdout)
                status = response.get("Status", "")

                if status in ("Pending", "InProgress", "Delayed"):
                    if verbose:
                        print_warning(f"Poll attempt {attempt + 1}: status={status}")
                    continue

                # Command completed
                stdout = response.get("StandardOutputContent", "")
                stderr = response.get("StandardErrorContent", "")

                if status == "Success":
                    return 0, stdout, stderr
                else:
                    # Failed, Cancelled, TimedOut, etc.
                    status_details = response.get("StatusDetails", status)
                    return 1, stdout, stderr or f"Command failed with status: {status_details}"

            except (json.JSONDecodeError, KeyError):
                continue

        return 1, "", f"Command timed out after {timeout} seconds"

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
        """Forward a port from the remote instance to localhost via SSM.

        Uses AWS SSM start-session with AWS-StartPortForwardingSession
        document for port forwarding without SSH.

        Args:
            instance_id: AWS instance ID
            dns: DNS hostname (not used for SSM, included for protocol)
            local_port: Local port to bind
            remote_port: Remote port to forward
            user: Not used for SSM (included for protocol compatibility)
            key_path: Not used for SSM (included for protocol compatibility)
            verbose: Enable verbose output
            no_strict_host_key: Not used for SSM (included for protocol)

        Returns:
            Exit code from SSM port forwarding session
        """
        ssm_args = [
            "aws",
            "ssm",
            "start-session",
            "--target",
            instance_id,
            "--document-name",
            "AWS-StartPortForwardingSession",
            "--parameters",
            json.dumps(
                {
                    "portNumber": [str(remote_port)],
                    "localPortNumber": [str(local_port)],
                }
            ),
        ]
        ssm_args.extend(self._get_profile_args())

        if verbose:
            print_warning(f"SSM port forward command: {' '.join(ssm_args)}")

        try:
            result = subprocess.run(ssm_args)
            return result.returncode
        except FileNotFoundError:
            raise SSMError(
                "port-forward",
                "AWS CLI not found. Please install the AWS CLI and Session Manager plugin.",
            )

    def supports_file_transfer(self) -> bool:
        """SSM does not support file transfer.

        Returns:
            False - SSM cannot use rsync or similar tools
        """
        return False
