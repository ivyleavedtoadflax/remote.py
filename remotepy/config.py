import configparser
import os

import typer

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".config", "remote.py/", "config.ini"
)

app = typer.Typer()


def read_config(config_path=CONFIG_PATH):
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)

    return cfg


def write_config(cfg, config_path=CONFIG_PATH):
    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return cfg


cfg = read_config()


@app.command()
def add(instance_name: str = typer.Argument(None, help="Instance name")):
    """
    Add a new default instance to the configuration file
    """

    # Check whether the instance_name is already set in the config

    if not instance_name:

        if cfg["DEFAULT"].get("instance_name"):
            typer.secho(
                f"Default instance already set as {cfg['DEFAULT']['instance_name']}",
                fg=typer.colors.YELLOW,
            )

            # Ask if the user still wants to change the instance name

            add_new = typer.confirm("Do you want to add a new default instance?")

            if add_new:
                instance_name = typer.prompt("Instance name")

        # If not default exists in the config, then prompt for instance name

        else:
            typer.secho("No default instance found", fg=typer.colors.YELLOW)
            instance_name = typer.prompt("Set the default instance name")

    # If the instance_name has been set, then add it to the config

    if instance_name:
        cfg.set("DEFAULT", "instance_name", instance_name)
        write_config(cfg)
        typer.secho(f"Default instance set to {instance_name}", fg=typer.colors.GREEN)
    else:
        typer.secho("No changes made", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
