import configparser
import os

import typer
import wasabi

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".config", "remote.py/", "config.ini"
)

app = typer.Typer()


def read_config(config_path):
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)

    return cfg


def write_config(cfg, config_path):
    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return cfg


cfg = read_config(config_path=CONFIG_PATH)


@app.command()
def show(config_path: str = typer.Option(CONFIG_PATH, "--config", "-c")):
    """
    List all the configuration options
    """

    # Print out the config file
    cfg = read_config(config_path=config_path)
    default_section = cfg["DEFAULT"]

    header = ["Section", "Name", "Value"]
    aligns = ["l", "l"]
    data = [["DEFAULT", k, v] for k, v in default_section.items()]
    formatter = wasabi.table(data, header=header, divider=True, aligns=aligns)

    typer.secho(f"Printing config file: {config_path}", fg=typer.colors.YELLOW)
    typer.secho(formatter, fg=typer.colors.YELLOW)


@app.command()
def add(
    instance_name: str = typer.Argument(None, help="Instance name"),
    config_path: str = typer.Option(CONFIG_PATH, "--config", "-c"),
):
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
        write_config(cfg, config_path)
        typer.secho(f"Default instance set to {instance_name}", fg=typer.colors.GREEN)
    else:
        typer.secho("No changes made", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
