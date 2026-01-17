import configparser
import os

import typer
from rich.console import Console
from rich.table import Table

from remotepy.settings import Settings
from remotepy.utils import get_instance_ids, get_instance_info, get_instances

app = typer.Typer()
console = Console(force_terminal=True, width=200)


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
        if config_path is None:
            config_path = str(Settings.get_config_path())

        # Reload config to get latest state
        self._file_config = None
        config = self.file_config

        # Ensure DEFAULT section exists
        if "DEFAULT" not in config:
            config.add_section("DEFAULT")

        config.set("DEFAULT", "instance_name", instance_name)
        write_config(config, config_path)


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
    Print the current config file
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
    Add a new default instance to the config file.

    This function allows you to add a new default instance either by providing the name directly or
    by selecting it from a list of currently running instances. Terminated instances are not included
    in this list. If a name is directly provided, the function checks if an instance with this name
    exists before setting it as the default.

    Arguments:
    config_path -- The path to the configuration file.
    instance_name -- The name of the instance to add. This is an optional argument.
                     If not provided, the function will prompt the user to select an instance from a list.

    Returns:
    None. But it modifies the configuration file with the new default instance.
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


if __name__ == "__main__":
    app()
