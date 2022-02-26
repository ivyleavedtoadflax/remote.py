import configparser

import pytest
from remotepy.config import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture()
def test_config(tmp_path):
    d = tmp_path / "remotepy"
    d.mkdir()
    config_path = d / "config.ini"
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return config_path


def test_add_default_instance_name(test_config):
    result = runner.invoke(app, ["foobar"])
    assert result.exit_code == 0
    assert "Default instance set to foobar" in result.stdout


def test_dont_update_default_instance_name(test_config):
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "No changes made" in result.stdout
