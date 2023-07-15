from remotepy.ami import app as ami_app
from remotepy.config import app as config_app
from remotepy.instance import app as app
from remotepy.snapshot import app as snapshot_app
from remotepy.volume import app as volume_app

# This means that the instance app is the default app, so we don't need to run
# remote instance, we can just run remote

app.add_typer(ami_app, name="ami")
app.add_typer(config_app, name="config")
app.add_typer(snapshot_app, name="snapshot")
app.add_typer(volume_app, name="volume")

if __name__ == "__main__":
    app()
