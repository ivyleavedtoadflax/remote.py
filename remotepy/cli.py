from remotepy.config import app as config_app
from remotepy.instance import app as app

app.add_typer(config_app, name="config")

if __name__ == "__main__":
    app()
