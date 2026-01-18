import configparser
import os
import re
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.panel import Panel
from rich.table import Table

from remote.settings import Settings
from remote.utils import console, get_instance_ids, get_instance_info, get_instances

app = typer.Typer()

# Valid configuration keys with descriptions
VALID_KEYS: dict[str, str] = {
    "instance_name": "Default EC2 instance name",
    "ssh_user": "SSH username (default: ubuntu)",
    "ssh_key_path": "Path to SSH private key",
    "aws_region": "AWS region override",
    "default_launch_template": "Default launch template name",
}


class RemoteConfig(BaseSettings):
    """
    Pydantic configuration model for Remote.py.

    Supports loading from:
    1. INI config file (default: ~/.config/remote.py/config.ini)
    2. Environment variables with REMOTE_ prefix

    Environment variables take precedence over config file values.

    Example environment variables:
        REMOTE_INSTANCE_NAME=my-server
        REMOTE_SSH_USER=ec2-user
        REMOTE_SSH_KEY_PATH=~/.ssh/my-key.pem
        REMOTE_AWS_REGION=us-west-2
        REMOTE_DEFAULT_LAUNCH_TEMPLATE=my-template
    """

    model_config = SettingsConfigDict(
        env_prefix="REMOTE_",
        env_file=None,  # We handle INI files separately
        extra="ignore",  # Allow unknown fields from INI file
    )

    instance_name: str | None = Field(default=None, description="Default EC2 instance name")
    ssh_user: str = Field(default="ubuntu", description="SSH username")
    ssh_key_path: str | None = Field(default=None, description="Path to SSH private key")
    aws_region: str | None = Field(default=None, description="AWS region override")
    default_launch_template: str | None = Field(
        default=None, description="Default launch template name"
    )

    @field_validator("instance_name", mode="before")
    @classmethod
    def validate_instance_name(cls, v: str | None) -> str | None:
        """Validate instance name contains only allowed characters."""
        if v is None or v == "":
            return None
        # Allow alphanumeric, hyphens, underscores, and dots
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
            raise ValueError(
                f"Invalid instance name '{v}': "
                "must contain only alphanumeric characters, hyphens, underscores, and dots"
            )
        return v

    @field_validator("ssh_key_path", mode="before")
    @classmethod
    def validate_ssh_key_path(cls, v: str | None) -> str | None:
        """Validate and expand SSH key path."""
        if v is None or v == "":
            return None
        # Expand ~ to home directory
        return os.path.expanduser(v)

    @field_validator("ssh_user", mode="before")
    @classmethod
    def validate_ssh_user(cls, v: str | None) -> str:
        """Validate SSH username."""
        if v is None or v == "":
            return "ubuntu"
        # Allow alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError(
                f"Invalid SSH user '{v}': "
                "must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v

    @field_validator("aws_region", mode="before")
    @classmethod
    def validate_aws_region(cls, v: str | None) -> str | None:
        """Validate AWS region format."""
        if v is None or v == "":
            return None
        # AWS region format: xx-xxxx-N
        if not re.match(r"^[a-z]{2}-[a-z]+-\d+$", v):
            raise ValueError(
                f"Invalid AWS region '{v}': must be in format like 'us-east-1' or 'eu-west-2'"
            )
        return v

    def check_ssh_key_exists(self) -> tuple[bool, str | None]:
        """
        Check if SSH key file exists.

        Returns:
            Tuple of (exists, error_message). If exists is True, error_message is None.
        """
        if self.ssh_key_path is None:
            return True, None
        path = Path(self.ssh_key_path)
        if not path.exists():
            return False, f"SSH key not found: {self.ssh_key_path}"
        return True, None

    @classmethod
    def from_ini_file(cls, config_path: Path | str | None = None) -> "RemoteConfig":
        """
        Load configuration from INI file and environment variables.

        Environment variables take precedence over INI file values.

        Args:
            config_path: Path to INI file. Defaults to ~/.config/remote.py/config.ini

        Returns:
            RemoteConfig instance with validated configuration
        """
        config_path = Settings.get_config_path() if config_path is None else Path(config_path)

        # Load INI file if it exists
        ini_values: dict[str, Any] = {}
        if config_path.exists():
            parser = configparser.ConfigParser()
            parser.read(config_path)
            if "DEFAULT" in parser:
                for key in VALID_KEYS:
                    if key in parser["DEFAULT"]:
                        # Only use INI value if no environment variable is set
                        env_key = f"REMOTE_{key.upper()}"
                        if os.environ.get(env_key) is None:
                            ini_values[key] = parser["DEFAULT"][key]

        # Create model - environment variables are handled by pydantic-settings
        return cls(**ini_values)


class ConfigValidationResult(BaseModel):
    """Result of configuration validation."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool = Field(description="Whether configuration is valid")
    errors: list[str] = Field(default_factory=list, description="List of errors")
    warnings: list[str] = Field(default_factory=list, description="List of warnings")

    @classmethod
    def validate_config(cls, config_path: Path | str | None = None) -> "ConfigValidationResult":
        """
        Validate configuration file using Pydantic model.

        Args:
            config_path: Path to INI file. Defaults to ~/.config/remote.py/config.ini

        Returns:
            ConfigValidationResult with validation status and messages
        """
        config_path = Settings.get_config_path() if config_path is None else Path(config_path)

        errors: list[str] = []
        warnings: list[str] = []

        # Check file exists
        if not config_path.exists():
            errors.append(f"Config file not found: {config_path}")
            return cls(is_valid=False, errors=errors, warnings=warnings)

        # Load and validate with Pydantic
        try:
            config = RemoteConfig.from_ini_file(config_path)
        except ValueError as e:
            errors.append(f"Configuration error: {e}")
            return cls(is_valid=False, errors=errors, warnings=warnings)

        # Check SSH key exists
        key_exists, key_error = config.check_ssh_key_exists()
        if not key_exists and key_error:
            errors.append(key_error)

        # Check for unknown keys in INI file
        parser = configparser.ConfigParser()
        parser.read(config_path)
        if "DEFAULT" in parser:
            for key in parser["DEFAULT"]:
                if key not in VALID_KEYS:
                    warnings.append(f"Unknown config key: {key}")

        return cls(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


class ConfigManager:
    """Configuration manager for config file operations."""

    def __init__(self) -> None:
        self._file_config: configparser.ConfigParser | None = None
        self._pydantic_config: RemoteConfig | None = None

    @property
    def file_config(self) -> configparser.ConfigParser:
        """Lazy load file configuration."""
        if self._file_config is None:
            self._file_config = configparser.ConfigParser()
            config_path = Settings.get_config_path()
            if config_path.exists():
                self._file_config.read(config_path)
        return self._file_config

    def get_validated_config(self) -> RemoteConfig:
        """
        Get validated configuration using Pydantic model.

        This includes environment variable overrides.

        Returns:
            RemoteConfig instance with validated configuration
        """
        if self._pydantic_config is None:
            self._pydantic_config = RemoteConfig.from_ini_file()
        return self._pydantic_config

    def reload(self) -> None:
        """Reload configuration from file and environment variables."""
        self._file_config = None
        self._pydantic_config = None

    def _handle_config_error(self, error: Exception) -> None:
        """Handle and display config-related errors."""
        if isinstance(error, configparser.Error | OSError | PermissionError):
            typer.secho(f"Warning: Could not read config file: {error}", fg=typer.colors.YELLOW)
        elif isinstance(error, KeyError | TypeError | AttributeError):
            typer.secho("Warning: Config file structure is invalid", fg=typer.colors.YELLOW)
        elif isinstance(error, ValueError):
            typer.secho(f"Warning: Config validation error: {error}", fg=typer.colors.YELLOW)

    def get_instance_name(self) -> str | None:
        """Get default instance name from config file or environment variable."""
        try:
            # Try Pydantic config first (includes env var override)
            config = self.get_validated_config()
            if config.instance_name:
                return config.instance_name

            # Fall back to file config for backwards compatibility
            if "DEFAULT" in self.file_config and "instance_name" in self.file_config["DEFAULT"]:
                return self.file_config["DEFAULT"]["instance_name"]
        except (
            configparser.Error,
            OSError,
            PermissionError,
            KeyError,
            TypeError,
            AttributeError,
            ValueError,
        ) as e:
            self._handle_config_error(e)

        return None

    def set_instance_name(self, instance_name: str, config_path: str | None = None) -> None:
        """Set default instance name in config file."""
        self.set_value("instance_name", instance_name, config_path)

    def get_value(self, key: str) -> str | None:
        """Get a config value by key, with environment variable override support."""
        try:
            # Try Pydantic config first (includes env var override)
            config = self.get_validated_config()
            value = getattr(config, key, None)
            if value is not None:
                return str(value) if not isinstance(value, str) else value

            # Fall back to file config for backwards compatibility
            if "DEFAULT" in self.file_config and key in self.file_config["DEFAULT"]:
                return self.file_config["DEFAULT"][key]
        except (
            configparser.Error,
            OSError,
            PermissionError,
            KeyError,
            TypeError,
            AttributeError,
            ValueError,
        ) as e:
            self._handle_config_error(e)
        return None

    def set_value(self, key: str, value: str, config_path: str | None = None) -> None:
        """Set a config value by key."""
        if config_path is None:
            config_path = str(Settings.get_config_path())

        # Reload config to get latest state
        self.reload()
        config = self.file_config

        # Ensure DEFAULT section exists
        if "DEFAULT" not in config:
            config.add_section("DEFAULT")

        config.set("DEFAULT", key, value)
        write_config(config, config_path)

        # Reset pydantic config to reload on next access
        self._pydantic_config = None

    def remove_value(self, key: str, config_path: str | None = None) -> bool:
        """Remove a config value by key. Returns True if key existed."""
        if config_path is None:
            config_path = str(Settings.get_config_path())

        # Read from specified config path
        config = read_config(config_path)

        if "DEFAULT" not in config or key not in config["DEFAULT"]:
            return False

        config.remove_option("DEFAULT", key)
        write_config(config, config_path)

        # Reset cached configs to reload on next access
        self._file_config = None
        self._pydantic_config = None
        return True


# Global config manager instance
config_manager = ConfigManager()

# Default config path for CLI commands
CONFIG_PATH = str(Settings.get_config_path())


def read_config(config_path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(config_path)

    return config


def create_config_dir(config_path: str) -> None:
    # check whether the config path exists, and create if not.

    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
        typer.secho(f"Created config directory: {os.path.dirname(config_path)}", fg="green")


def write_config(config: configparser.ConfigParser, config_path: str) -> None:
    create_config_dir(config_path)

    with open(config_path, "w") as configfile:
        config.write(configfile)


@app.command()
def show(config_path: str = typer.Option(CONFIG_PATH, "--config", "-c")) -> None:
    """
    Show current configuration settings.

    Displays all settings from the config file in a table format.
    """

    # Print out the config file
    config = read_config(config_path=config_path)
    default_section = config["DEFAULT"]

    # Format table using rich
    table = Table(title="Configuration")
    table.add_column("Section")
    table.add_column("Name", style="cyan")
    table.add_column("Value", style="green")

    for k, v in default_section.items():
        table.add_row("DEFAULT", k, v)

    typer.secho(f"Printing config file: {config_path}", fg=typer.colors.YELLOW)
    console.print(table)


@app.command()
def add(
    instance_name: str | None = typer.Argument(None),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """
    Set the default instance.

    If no instance name is provided, lists available instances for selection.
    Terminated instances are not included in the list.

    Examples:
        remote config add                    # Select from list
        remote config add my-server          # Set specific instance
    """

    if instance_name is None:
        # No instance name provided. Fetch the list of currently running
        # instances (excluding terminated ones)

        instances = get_instances()

        # Get the instance ids for the instances
        ids = get_instance_ids(instances)

        # Get other details like name, type etc for these instances
        names, _, _, instance_types, _ = get_instance_info(instances)

        # Format table using rich
        table = Table(title="Select Instance")
        table.add_column("Number", justify="right")
        table.add_column("Name", style="cyan")
        table.add_column("InstanceId", style="green")
        table.add_column("Type")

        for i, (name, instance_id, it) in enumerate(
            zip(names, ids, instance_types, strict=True), 1
        ):
            table.add_row(str(i), name or "", instance_id, it or "")

        console.print(table)

        # Prompt the user to select an instance from the table
        instance_number = typer.prompt("Select a instance by number", type=int)

        # Validate the user input

        if 1 <= instance_number <= len(names):
            # If the input is valid, set the instance name to the selected one
            instance_name = names[instance_number - 1]
        else:
            # Invalid input. Display an error message and exit.
            typer.secho("Invalid number. No changes made", fg=typer.colors.YELLOW)

            return

    # If an instance name was directly provided or selected from the list, update the configuration file
    config_manager.set_instance_name(instance_name, config_path)
    typer.secho(f"Default instance set to {instance_name}", fg=typer.colors.GREEN)


@app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Config key to set"),
    value: str = typer.Argument(..., help="Value to set"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """
    Set a configuration value.

    Examples:
        remote config set instance_name my-server
        remote config set ssh_user ec2-user
        remote config set ssh_key_path ~/.ssh/my-key.pem
    """
    if key not in VALID_KEYS:
        typer.secho(f"Unknown config key: {key}", fg=typer.colors.RED)
        typer.secho(f"Valid keys: {', '.join(VALID_KEYS.keys())}", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    config_manager.set_value(key, value, config_path)
    typer.secho(f"Set {key} = {value}", fg=typer.colors.GREEN)


@app.command("get")
def get_value_cmd(
    key: str = typer.Argument(..., help="Config key to get"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """
    Get a configuration value.

    Returns just the value (useful for scripting).
    Supports environment variable overrides (REMOTE_<KEY>).

    Examples:
        remote config get instance_name
        INSTANCE=$(remote config get instance_name)
    """
    if key not in VALID_KEYS:
        typer.secho(f"Unknown config key: {key}", fg=typer.colors.RED)
        typer.secho(f"Valid keys: {', '.join(VALID_KEYS.keys())}", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    # Use a temporary ConfigManager if custom config path is provided
    if config_path != CONFIG_PATH:
        # For custom paths, read directly from file (no env var overrides)
        config = read_config(config_path)
        value = config.get("DEFAULT", key, fallback=None)
    else:
        # Use ConfigManager for default path (includes env var overrides and validation)
        value = config_manager.get_value(key)

    if value is None:
        raise typer.Exit(1)

    typer.echo(value)


@app.command("unset")
def unset_value(
    key: str = typer.Argument(..., help="Config key to remove"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """
    Remove a configuration value.

    Examples:
        remote config unset ssh_key_path
    """
    if not config_manager.remove_value(key, config_path):
        typer.secho(f"Key '{key}' not found in config", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    typer.secho(f"Removed {key}", fg=typer.colors.GREEN)


@app.command()
def init(
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """
    Initialize configuration with guided setup.

    Walks through common settings and creates a config file.

    Examples:
        remote config init
    """
    typer.secho("Remote.py Configuration Setup", fg=typer.colors.BLUE, bold=True)
    typer.echo()

    # Check if config exists
    if os.path.exists(config_path):
        if not typer.confirm("Config already exists. Overwrite?"):
            raise typer.Exit(0)

    # Guided prompts
    instance_name = typer.prompt("Default instance name (optional)", default="", show_default=False)
    ssh_user = typer.prompt("SSH username", default="ubuntu")
    ssh_key = typer.prompt("SSH key path (optional)", default="", show_default=False)

    # Write config
    config = configparser.ConfigParser()
    if instance_name:
        config.set("DEFAULT", "instance_name", instance_name)
    config.set("DEFAULT", "ssh_user", ssh_user)
    if ssh_key:
        config.set("DEFAULT", "ssh_key_path", ssh_key)

    write_config(config, config_path)
    typer.secho(f"\nConfig written to {config_path}", fg=typer.colors.GREEN)


@app.command()
def validate(
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """
    Validate configuration file using Pydantic validation.

    Checks that configured values are valid and accessible.
    Uses Pydantic schema to validate field formats and types.

    Examples:
        remote config validate
    """
    # Use Pydantic-based validation
    result = ConfigValidationResult.validate_config(config_path)

    # Build validation output content
    output_lines = []
    for error in result.errors:
        output_lines.append(f"[red]✗ ERROR:[/red] {error}")
    for warning in result.warnings:
        output_lines.append(f"[yellow]⚠ WARNING:[/yellow] {warning}")

    # Determine status and border style
    if not result.is_valid:
        output_lines.append("[red]✗ Configuration is invalid[/red]")
        border_style = "red"
    elif result.warnings:
        output_lines.append("[yellow]⚠ Configuration has warnings[/yellow]")
        border_style = "yellow"
    else:
        output_lines.append("[green]✓ Configuration is valid[/green]")
        border_style = "green"

    # Display as Rich panel
    panel_content = "\n".join(output_lines)
    panel = Panel(panel_content, title="Config Validation", border_style=border_style, expand=False)
    console.print(panel)

    if not result.is_valid:
        raise typer.Exit(1)


@app.command()
def keys() -> None:
    """
    List all valid configuration keys.

    Shows available keys and their descriptions.
    """
    table = Table(title="Valid Configuration Keys")
    table.add_column("Key", style="cyan")
    table.add_column("Description")

    for key, description in VALID_KEYS.items():
        table.add_row(key, description)

    console.print(table)
