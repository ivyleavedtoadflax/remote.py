"""Application settings for testing and development."""

import os
from dataclasses import dataclass
from pathlib import Path

# SSH default constants
DEFAULT_SSH_USER = "ubuntu"
SSH_PORT = 22

# Time-related constants
SECONDS_PER_HOUR = 3600

# Instance startup/connection constants
MAX_STARTUP_WAIT_SECONDS = 60
STARTUP_POLL_INTERVAL_SECONDS = 5
CONNECTION_RETRY_SLEEP_SECONDS = 20
MAX_CONNECTION_ATTEMPTS = 5
SSH_READINESS_WAIT_SECONDS = 10

# Instance type change polling constants
TYPE_CHANGE_MAX_POLL_ATTEMPTS = 5
TYPE_CHANGE_POLL_INTERVAL_SECONDS = 5

# Exec command constants
DEFAULT_EXEC_TIMEOUT_SECONDS = 30

# SSH operation timeout (for shutdown/cancel commands)
SSH_OPERATION_TIMEOUT_SECONDS = 30

# SSH connect timeout (interactive sessions)
# Default to 0 (no timeout) for interactive sessions since they run indefinitely.
# Users can specify --timeout to set a maximum session duration if needed.
# Dead connection detection is handled by SSH keepalive options instead.
DEFAULT_SSH_CONNECT_TIMEOUT_SECONDS = 0

# SSH keepalive settings for interactive sessions
# These detect dead connections without killing active sessions
SSH_SERVER_ALIVE_INTERVAL = 60  # Send keepalive every 60 seconds
SSH_SERVER_ALIVE_COUNT_MAX = 3  # Disconnect after 3 missed keepalives (3 minutes)


@dataclass
class Settings:
    """Application settings for testing and development."""

    # Testing overrides
    testing_mode: bool = False
    mock_aws_calls: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables (testing only)."""
        return cls(
            testing_mode=os.getenv("REMOTEPY_TESTING_MODE", "false").lower() == "true",
            mock_aws_calls=os.getenv("REMOTEPY_MOCK_AWS", "false").lower() == "true",
        )

    @staticmethod
    def get_config_path() -> Path:
        """Get the default config file path."""
        return Path.home() / ".config" / "remote.py" / "config.ini"


# Global settings instance - can be overridden for testing
settings = Settings.from_env()

# Table column styling constants
# These styles are applied consistently across all CLI table output
# to provide a cohesive user experience.
TABLE_COLUMN_STYLES: dict[str, str] = {
    # Primary identifiers - cyan for names, green for IDs
    "name": "cyan",  # Resource names (instance name, cluster name, etc.)
    "id": "green",  # AWS resource IDs (instance ID, volume ID, AMI ID, etc.)
    # Secondary/metadata - dim for ARNs, yellow for numeric values
    "arn": "dim",  # AWS ARNs (typically long, less important)
    "numeric": "yellow",  # Numeric values (counts, sizes, row numbers)
    # Status is handled dynamically by get_status_style() based on state
    # Other columns (timestamps, descriptions, DNS names) use default (no style)
}
