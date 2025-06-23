import configparser
from pathlib import Path
from unittest.mock import mock_open

import pytest
from typer.testing import CliRunner

from remotepy import config
from remotepy.config import ConfigManager

runner = CliRunner()


@pytest.fixture(scope="function")
def test_config(tmpdir_factory):
    config_path = tmpdir_factory.mktemp("remote.py").join("config.ini")
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    with open(config_path, "w") as configfile:
        cfg.write(configfile)

    return config_path


@pytest.fixture
def mock_instances_data():
    return [
        {
            "Instances": [
                {
                    "InstanceId": "i-0123456789abcdef0",
                    "InstanceType": "t2.micro",
                    "Tags": [{"Key": "Name", "Value": "test-instance-1"}],
                    "State": {"Name": "running"},
                    "LaunchTime": "2023-07-15T00:00:00Z",
                    "PublicDnsName": "example1.com",
                }
            ]
        },
        {
            "Instances": [
                {
                    "InstanceId": "i-0123456789abcdef1",
                    "InstanceType": "t2.small",
                    "Tags": [{"Key": "Name", "Value": "test-instance-2"}],
                    "State": {"Name": "stopped"},
                    "LaunchTime": "2023-07-16T00:00:00Z",
                    "PublicDnsName": "example2.com",
                }
            ]
        },
    ]


class TestConfigManager:
    def test_init(self):
        manager = ConfigManager()
        assert manager._file_config is None

    def test_file_config_loads_existing_file(self, mocker):
        mock_settings = mocker.patch("remotepy.config.Settings")
        mock_path = mocker.MagicMock()
        mock_path.exists.return_value = True
        mock_settings.get_config_path.return_value = mock_path

        mock_config = mocker.patch("configparser.ConfigParser")
        mock_config_instance = mock_config.return_value

        manager = ConfigManager()
        result = manager.file_config

        assert result == mock_config_instance
        mock_config_instance.read.assert_called_once_with(mock_path)

    def test_file_config_nonexistent_file(self, mocker):
        mock_settings = mocker.patch("remotepy.config.Settings")
        mock_path = mocker.MagicMock()
        mock_path.exists.return_value = False
        mock_settings.get_config_path.return_value = mock_path

        mock_config = mocker.patch("configparser.ConfigParser")
        mock_config_instance = mock_config.return_value

        manager = ConfigManager()
        result = manager.file_config

        assert result == mock_config_instance
        mock_config_instance.read.assert_not_called()

    def test_get_instance_name_success(self, mocker):
        manager = ConfigManager()
        mock_config = mocker.MagicMock()
        mock_config.__contains__ = lambda self, key: key == "DEFAULT"
        mock_config.__getitem__ = lambda self, key: {"instance_name": "test-instance"}
        manager._file_config = mock_config

        result = manager.get_instance_name()
        assert result == "test-instance"

    def test_get_instance_name_no_default_section(self, mocker):
        manager = ConfigManager()
        mock_config = mocker.MagicMock()
        mock_config.__contains__ = lambda self, key: False
        manager._file_config = mock_config

        result = manager.get_instance_name()
        assert result is None

    def test_get_instance_name_no_instance_name_key(self, mocker):
        manager = ConfigManager()
        mock_config = mocker.MagicMock()
        mock_config.__contains__ = lambda self, key: key == "DEFAULT"
        mock_config.__getitem__ = lambda self, key: {}
        manager._file_config = mock_config

        result = manager.get_instance_name()
        assert result is None

    def test_get_instance_name_exception(self, mocker):
        manager = ConfigManager()
        mock_config = mocker.MagicMock()
        mock_config.__contains__.side_effect = Exception("Config error")
        manager._file_config = mock_config

        result = manager.get_instance_name()
        assert result is None

    def test_set_instance_name_with_default_path(self, mocker):
        mock_settings = mocker.patch("remotepy.config.Settings")
        mock_settings.get_config_path.return_value = Path("/test/config.ini")
        mock_write_config = mocker.patch("remotepy.config.write_config")

        manager = ConfigManager()
        manager._file_config = configparser.ConfigParser()

        manager.set_instance_name("new-instance")

        mock_write_config.assert_called_once()
        assert manager.file_config["DEFAULT"]["instance_name"] == "new-instance"

    def test_set_instance_name_with_custom_path(self, mocker):
        mock_write_config = mocker.patch("remotepy.config.write_config")

        manager = ConfigManager()
        manager._file_config = configparser.ConfigParser()

        manager.set_instance_name("new-instance", "/custom/path")

        mock_write_config.assert_called_once_with(manager.file_config, "/custom/path")
        assert manager.file_config["DEFAULT"]["instance_name"] == "new-instance"

    def test_set_instance_name_creates_default_section(self, mocker):
        mocker.patch("remotepy.config.write_config")

        manager = ConfigManager()
        manager._file_config = configparser.ConfigParser()
        # Ensure no DEFAULT section exists initially

        manager.set_instance_name("new-instance", "/test/path")

        assert "DEFAULT" in manager.file_config
        assert manager.file_config["DEFAULT"]["instance_name"] == "new-instance"


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


def test_read_config(mocker):
    mock_config = mocker.patch("configparser.ConfigParser")
    mock_config_instance = mock_config.return_value

    result = config.read_config("/test/path")

    assert result == mock_config_instance
    mock_config_instance.read.assert_called_once_with(config.CONFIG_PATH)


def test_write_config(test_config, mocker):
    mock_create_config_dir = mocker.patch("remotepy.config.create_config_dir")
    mock_open_file = mocker.patch("builtins.open", mock_open())

    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    result = config.write_config(cfg, test_config)

    assert result == cfg
    mock_create_config_dir.assert_called_once_with(test_config)
    mock_open_file.assert_called_once_with(test_config, "w")


def test_show_command(mocker):
    mock_read_config = mocker.patch("remotepy.config.read_config")
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.return_value = {"instance_name": "test-instance", "region": "us-east-1"}
    mock_read_config.return_value = mock_config

    result = runner.invoke(config.app, ["show"])

    assert result.exit_code == 0
    mock_read_config.assert_called_once_with(config_path=config.CONFIG_PATH)
    assert "Printing config file" in result.stdout


def test_show_command_with_custom_path(mocker):
    mock_read_config = mocker.patch("remotepy.config.read_config")
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.return_value = {}
    mock_read_config.return_value = mock_config

    result = runner.invoke(config.app, ["show", "--config", "/custom/path"])

    assert result.exit_code == 0
    mock_read_config.assert_called_once_with(config_path="/custom/path")


def test_add_with_instance_name(mocker):
    mock_config_manager = mocker.patch("remotepy.config.config_manager")

    result = runner.invoke(config.app, ["add", "my-instance"])

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_called_once_with("my-instance", config.CONFIG_PATH)
    assert "Default instance set to my-instance" in result.stdout


def test_add_with_custom_config_path(mocker):
    mock_config_manager = mocker.patch("remotepy.config.config_manager")

    result = runner.invoke(config.app, ["add", "my-instance", "--config", "/custom/path"])

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_called_once_with("my-instance", "/custom/path")


def test_add_no_instances(mocker):
    mocker.patch("remotepy.config.get_instances", return_value=[])
    result = runner.invoke(config.app, ["add"], input="1\n")
    assert "Invalid number. No changes made" in result.stdout


def test_add_interactive_valid_selection(mocker, mock_instances_data):
    mock_get_instances = mocker.patch(
        "remotepy.config.get_instances", return_value=mock_instances_data
    )
    mock_get_instance_ids = mocker.patch(
        "remotepy.config.get_instance_ids", return_value=["i-123", "i-456"]
    )
    mock_get_instance_info = mocker.patch(
        "remotepy.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remotepy.config.config_manager")

    result = runner.invoke(config.app, ["add"], input="1\n")

    assert result.exit_code == 0
    mock_get_instances.assert_called_once()
    mock_get_instance_ids.assert_called_once_with(mock_instances_data)
    mock_get_instance_info.assert_called_once_with(mock_instances_data)
    mock_config_manager.set_instance_name.assert_called_once_with(
        "test-instance-1", config.CONFIG_PATH
    )
    assert "Default instance set to test-instance-1" in result.stdout


def test_add_interactive_invalid_selection_too_high(mocker, mock_instances_data):
    mocker.patch("remotepy.config.get_instances", return_value=mock_instances_data)
    mocker.patch("remotepy.config.get_instance_ids", return_value=["i-123", "i-456"])
    mocker.patch(
        "remotepy.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remotepy.config.config_manager")

    result = runner.invoke(config.app, ["add"], input="5\n")

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_not_called()
    assert "Invalid number. No changes made" in result.stdout


def test_add_interactive_invalid_selection_zero(mocker, mock_instances_data):
    mocker.patch("remotepy.config.get_instances", return_value=mock_instances_data)
    mocker.patch("remotepy.config.get_instance_ids", return_value=["i-123", "i-456"])
    mocker.patch(
        "remotepy.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remotepy.config.config_manager")

    result = runner.invoke(config.app, ["add"], input="0\n")

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_not_called()
    assert "Invalid number. No changes made" in result.stdout


def test_add_interactive_valid_selection_second_instance(mocker, mock_instances_data):
    mocker.patch("remotepy.config.get_instances", return_value=mock_instances_data)
    mocker.patch("remotepy.config.get_instance_ids", return_value=["i-123", "i-456"])
    mocker.patch(
        "remotepy.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remotepy.config.config_manager")

    result = runner.invoke(config.app, ["add"], input="2\n")

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_called_once_with(
        "test-instance-2", config.CONFIG_PATH
    )
    assert "Default instance set to test-instance-2" in result.stdout
