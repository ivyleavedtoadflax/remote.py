import configparser

import pytest
from remotepy.cli import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(scope="function")
def test_config(tmpdir_factory):
    config_path = tmpdir_factory.mktemp("remote.py").join("config.ini")
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return config_path


def test_add_default_instance_name(test_config):
    result = runner.invoke(app, ["config", "add", "foobar", "-c", test_config])
    assert result.exit_code == 0
    assert "Default instance set to foobar" in result.stdout


def test_dont_update_default_instance_name(test_config):
    result = runner.invoke(app, ["config", "add", "-c", test_config])
    assert result.exit_code == 0
    assert "No changes made" in result.stdout


def test_get_status_with_config(test_config):
    result = runner.invoke(app, ["config", "show", "-c", test_config])
    assert result.exit_code == 0
    assert "DEFAULT" in result.stdout
    assert "instance_name" in result.stdout
    assert "test" in result.stdout
