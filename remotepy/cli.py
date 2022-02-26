import typer

from remotepy.config import app as config_app
from remotepy.instance import app as instance_app

app = typer.Typer()
app.add_typer(instance_app, name="instance")
app.add_typer(config_app, name="config")

if __name__ == "__main__":
    app()
