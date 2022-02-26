import configparser

import pytest
from remotepy.instance import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(scope="session")
def test_config(tmpdir_factory):
    config_path = tmpdir_factory.mktemp("remote.py").join("config.ini")
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return config_path


def test_instance_status_when_not_found(test_config):
    result = runner.invoke(app, ["status", "test"])

    # Expect a 1 exit code as we sys.exit(1)

    assert result.exit_code == 1
    assert "Instance test not found" in result.stdout
