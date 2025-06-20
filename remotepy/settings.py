"""Application settings for testing and development."""

import os
from dataclasses import dataclass
from pathlib import Path


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
            mock_aws_calls=os.getenv("REMOTEPY_MOCK_AWS", "false").lower() == "true"
        )

    @staticmethod
    def get_config_path() -> Path:
        """Get the default config file path."""
        return Path.home() / ".config" / "remote.py" / "config.ini"


# Global settings instance - can be overridden for testing
settings = Settings.from_env()
