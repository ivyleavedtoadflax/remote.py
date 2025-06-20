import configparser

import pytest
from typer.testing import CliRunner

from remotepy import config

runner = CliRunner()


@pytest.fixture(scope="function")
def test_config(tmpdir_factory):
    config_path = tmpdir_factory.mktemp("remote.py").join("config.ini")
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return config_path


def test_create_config_dir_existing(mocker):
    mocker.patch("os.path.exists", return_value=True)
    mock_makedirs = mocker.patch("os.makedirs")
    config.create_config_dir("dummy_path")
    mock_makedirs.assert_not_called()


def test_create_config_dir_not_existing(mocker):
    mocker.patch("os.path.exists", return_value=False)
    mock_makedirs = mocker.patch("os.makedirs")
    config.create_config_dir("dummy_path")
    mock_makedirs.assert_called_once()


def test_write_config(test_config, mocker):
    mocker.patch("builtins.open", mocker.mock_open())
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"
    config.write_config(cfg, test_config)


def test_add_no_instances(mocker):
    mocker.patch("remotepy.config.get_instances", return_value=[])
    result = runner.invoke(config.app, ["add"], input="1\n")
    assert "Invalid number. No changes made" in result.stdout
