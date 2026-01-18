import configparser
import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from remote.settings import Settings
from remote.utils import get_instance_ids, get_instance_info, get_instances

app = typer.Typer()
console = Console(force_terminal=True, width=200)

# Valid configuration keys with descriptions
VALID_KEYS: dict[str, str] = {
    "instance_name": "Default EC2 instance name",
    "ssh_user": "SSH username (default: ubuntu)",
    "ssh_key_path": "Path to SSH private key",
    "aws_region": "AWS region override",
    "default_launch_template": "Default launch template name",
}


class ConfigManager:
    """Configuration manager for config file operations."""

    def __init__(self) -> None:
        self._file_config: configparser.ConfigParser | None = None

    @property
    def file_config(self) -> configparser.ConfigParser:
        """Lazy load file configuration."""
        if self._file_config is None:
            self._file_config = configparser.ConfigParser()
            config_path = Settings.get_config_path()
            if config_path.exists():
                self._file_config.read(config_path)
        return self._file_config

    def get_instance_name(self) -> str | None:
        """Get default instance name from config file."""
        try:
            if "DEFAULT" in self.file_config and "instance_name" in self.file_config["DEFAULT"]:
                return self.file_config["DEFAULT"]["instance_name"]
        except (configparser.Error, OSError, PermissionError) as e:
            # Config file might be corrupted or inaccessible
            # Log the specific error but don't crash the application
            typer.secho(f"Warning: Could not read config file: {e}", fg=typer.colors.YELLOW)
        except (KeyError, TypeError, AttributeError):
            # Handle malformed config structure
            typer.secho("Warning: Config file structure is invalid", fg=typer.colors.YELLOW)
        except Exception as e:
            # Handle any other unexpected errors
            typer.secho(f"Warning: Unexpected error reading config: {e}", fg=typer.colors.YELLOW)

        # No configuration found
        return None

    def set_instance_name(self, instance_name: str, config_path: str | None = None) -> None:
        """Set default instance name in config file."""
        self.set_value("instance_name", instance_name, config_path)

    def get_value(self, key: str) -> str | None:
        """Get a config value by key."""
        try:
            if "DEFAULT" in self.file_config and key in self.file_config["DEFAULT"]:
                return self.file_config["DEFAULT"][key]
        except (configparser.Error, OSError, PermissionError) as e:
            typer.secho(f"Warning: Could not read config file: {e}", fg=typer.colors.YELLOW)
        except (KeyError, TypeError, AttributeError):
            typer.secho("Warning: Config file structure is invalid", fg=typer.colors.YELLOW)
        except Exception as e:
            typer.secho(f"Warning: Unexpected error reading config: {e}", fg=typer.colors.YELLOW)
        return None

    def set_value(self, key: str, value: str, config_path: str | None = None) -> None:
        """Set a config value by key."""
        if config_path is None:
            config_path = str(Settings.get_config_path())

        # Reload config to get latest state
        self._file_config = None
        config = self.file_config

        # Ensure DEFAULT section exists
        if "DEFAULT" not in config:
            config.add_section("DEFAULT")

        config.set("DEFAULT", key, value)
        write_config(config, config_path)

    def remove_value(self, key: str, config_path: str | None = None) -> bool:
        """Remove a config value by key. Returns True if key existed."""
        if config_path is None:
            config_path = str(Settings.get_config_path())

        # Reload config to get latest state
        self._file_config = None
        config = self.file_config

        if "DEFAULT" not in config or key not in config["DEFAULT"]:
            return False

        config.remove_option("DEFAULT", key)
        write_config(config, config_path)
        return True


# Global config manager instance
config_manager = ConfigManager()

# Default config path for CLI commands
CONFIG_PATH = str(Settings.get_config_path())


def read_config(config_path: str) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(config_path)

    return cfg


def create_config_dir(config_path: str) -> None:
    # check whether the config path exists, and create if not.

    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
        typer.secho(f"Created config directory: {os.path.dirname(config_path)}", fg="green")


def write_config(cfg: configparser.ConfigParser, config_path: str) -> configparser.ConfigParser:
    create_config_dir(config_path)

    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return cfg


@app.command()
def show(config_path: str = typer.Option(CONFIG_PATH, "--config", "-c")) -> None:
    """
    Show current configuration settings.

    Displays all settings from the config file in a table format.
    """

    # Print out the config file
    cfg = read_config(config_path=config_path)
    default_section = cfg["DEFAULT"]

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
            zip(names, ids, instance_types, strict=False), 1
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
def get_value(
    key: str = typer.Argument(..., help="Config key to get"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
) -> None:
    """
    Get a configuration value.

    Returns just the value (useful for scripting).

    Examples:
        remote config get instance_name
        INSTANCE=$(remote config get instance_name)
    """
    # Reload config with specified path
    cfg = read_config(config_path)
    value = cfg.get("DEFAULT", key, fallback=None)

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
    cfg = read_config(config_path)

    if "DEFAULT" not in cfg or key not in cfg["DEFAULT"]:
        typer.secho(f"Key '{key}' not found in config", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    cfg.remove_option("DEFAULT", key)
    write_config(cfg, config_path)
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
    Validate configuration file.

    Checks that configured values are valid and accessible.

    Examples:
        remote config validate
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not os.path.exists(config_path):
        typer.secho(f"Config file not found: {config_path}", fg=typer.colors.RED)
        raise typer.Exit(1)

    cfg = read_config(config_path)

    # Check for unknown keys
    for key in cfg["DEFAULT"]:
        if key not in VALID_KEYS:
            warnings.append(f"Unknown config key: {key}")

    # Check SSH key exists
    ssh_key = cfg.get("DEFAULT", "ssh_key_path", fallback=None)
    if ssh_key and not os.path.exists(os.path.expanduser(ssh_key)):
        errors.append(f"SSH key not found: {ssh_key}")

    # Build validation output content
    output_lines = []
    for error in errors:
        output_lines.append(f"[red]✗ ERROR:[/red] {error}")
    for warning in warnings:
        output_lines.append(f"[yellow]⚠ WARNING:[/yellow] {warning}")

    # Determine status
    if errors:
        status = "[red]Status: Invalid - errors must be fixed[/red]"
        border_style = "red"
    elif warnings:
        status = "[yellow]Status: Has warnings but usable[/yellow]"
        border_style = "yellow"
    else:
        output_lines.append("[green]✓ All checks passed[/green]")
        status = "[green]Status: Valid[/green]"
        border_style = "green"

    # Add status line
    if output_lines:
        output_lines.append("")
    output_lines.append(status)

    # Display as Rich panel
    panel_content = "\n".join(output_lines)
    panel = Panel(panel_content, title="Config Validation", border_style=border_style)
    console.print(panel)

    if errors:
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


if __name__ == "__main__":
    app()
