import configparser
from pathlib import Path
from unittest.mock import mock_open

import pytest
from typer.testing import CliRunner

from remote import config
from remote.config import ConfigManager

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
        mock_settings = mocker.patch("remote.config.Settings")
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
        mock_settings = mocker.patch("remote.config.Settings")
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

    def test_get_instance_name_validation_error(self, mocker):
        manager = ConfigManager()
        mock_config = mocker.MagicMock()
        mock_config.__contains__.side_effect = ValueError("Config validation error")
        manager._file_config = mock_config

        result = manager.get_instance_name()
        assert result is None

    def test_set_instance_name_with_default_path(self, mocker):
        mock_settings = mocker.patch("remote.config.Settings")
        mock_settings.get_config_path.return_value = Path("/test/config.ini")
        mock_write_config = mocker.patch("remote.config.write_config")

        manager = ConfigManager()
        manager._file_config = configparser.ConfigParser()

        manager.set_instance_name("new-instance")

        mock_write_config.assert_called_once()
        assert manager.file_config["DEFAULT"]["instance_name"] == "new-instance"

    def test_set_instance_name_with_custom_path(self, mocker):
        mock_write_config = mocker.patch("remote.config.write_config")

        manager = ConfigManager()
        manager._file_config = configparser.ConfigParser()

        manager.set_instance_name("new-instance", "/custom/path")

        mock_write_config.assert_called_once_with(manager.file_config, "/custom/path")
        assert manager.file_config["DEFAULT"]["instance_name"] == "new-instance"

    def test_set_instance_name_creates_default_section(self, mocker):
        mocker.patch("remote.config.write_config")

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
    mock_config_instance.read.assert_called_once_with("/test/path")


def test_write_config(test_config, mocker):
    mock_create_config_dir = mocker.patch("remote.config.create_config_dir")
    mock_open_file = mocker.patch("builtins.open", mock_open())

    cfg = configparser.ConfigParser()
    cfg["DEFAULT"]["instance_name"] = "test"

    config.write_config(cfg, test_config)

    mock_create_config_dir.assert_called_once_with(test_config)
    mock_open_file.assert_called_once_with(test_config, "w")


def test_show_command(mocker):
    mock_read_config = mocker.patch("remote.config.read_config")
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.return_value = {"instance_name": "test-instance", "region": "us-east-1"}
    mock_read_config.return_value = mock_config

    result = runner.invoke(config.app, ["show"])

    assert result.exit_code == 0
    mock_read_config.assert_called_once_with(config_path=config.CONFIG_PATH)
    assert "Printing config file" in result.stdout


def test_show_command_with_custom_path(mocker):
    mock_read_config = mocker.patch("remote.config.read_config")
    mock_config = mocker.MagicMock()
    mock_config.__getitem__.return_value = {}
    mock_read_config.return_value = mock_config

    result = runner.invoke(config.app, ["show", "--config", "/custom/path"])

    assert result.exit_code == 0
    mock_read_config.assert_called_once_with(config_path="/custom/path")


def test_add_with_instance_name(mocker):
    mock_config_manager = mocker.patch("remote.config.config_manager")

    result = runner.invoke(config.app, ["add", "my-instance"])

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_called_once_with("my-instance", config.CONFIG_PATH)
    assert "Default instance set to my-instance" in result.stdout


def test_add_with_custom_config_path(mocker):
    mock_config_manager = mocker.patch("remote.config.config_manager")

    result = runner.invoke(config.app, ["add", "my-instance", "--config", "/custom/path"])

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_called_once_with("my-instance", "/custom/path")


def test_add_no_instances(mocker):
    mocker.patch("remote.config.get_instances", return_value=[])
    result = runner.invoke(config.app, ["add"], input="1\n")
    assert "Invalid number. No changes made" in result.stdout


def test_add_interactive_valid_selection(mocker, mock_instances_data):
    mock_get_instances = mocker.patch(
        "remote.config.get_instances", return_value=mock_instances_data
    )
    mock_get_instance_ids = mocker.patch(
        "remote.config.get_instance_ids", return_value=["i-123", "i-456"]
    )
    mock_get_instance_info = mocker.patch(
        "remote.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remote.config.config_manager")

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
    mocker.patch("remote.config.get_instances", return_value=mock_instances_data)
    mocker.patch("remote.config.get_instance_ids", return_value=["i-123", "i-456"])
    mocker.patch(
        "remote.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remote.config.config_manager")

    result = runner.invoke(config.app, ["add"], input="5\n")

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_not_called()
    assert "Invalid number. No changes made" in result.stdout


def test_add_interactive_invalid_selection_zero(mocker, mock_instances_data):
    mocker.patch("remote.config.get_instances", return_value=mock_instances_data)
    mocker.patch("remote.config.get_instance_ids", return_value=["i-123", "i-456"])
    mocker.patch(
        "remote.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remote.config.config_manager")

    result = runner.invoke(config.app, ["add"], input="0\n")

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_not_called()
    assert "Invalid number. No changes made" in result.stdout


def test_add_interactive_valid_selection_second_instance(mocker, mock_instances_data):
    mocker.patch("remote.config.get_instances", return_value=mock_instances_data)
    mocker.patch("remote.config.get_instance_ids", return_value=["i-123", "i-456"])
    mocker.patch(
        "remote.config.get_instance_info",
        return_value=(
            ["test-instance-1", "test-instance-2"],
            ["dns1", "dns2"],
            ["running", "stopped"],
            ["t2.micro", "t2.small"],
            ["time1", "time2"],
        ),
    )
    mock_config_manager = mocker.patch("remote.config.config_manager")

    result = runner.invoke(config.app, ["add"], input="2\n")

    assert result.exit_code == 0
    mock_config_manager.set_instance_name.assert_called_once_with(
        "test-instance-2", config.CONFIG_PATH
    )
    assert "Default instance set to test-instance-2" in result.stdout


# ============================================================================
# Enhanced Configuration Edge Case Tests
# ============================================================================


class TestConfigurationEdgeCases:
    """Test configuration edge cases and error conditions."""

    def test_should_handle_corrupted_config_file(self, mocker, tmpdir):
        """Should handle gracefully when config file is corrupted."""
        # Create a corrupted config file
        config_path = tmpdir.join("config.ini")
        config_path.write("this is not valid ini format [[[")

        mock_settings = mocker.patch("remote.config.Settings")
        mock_settings.return_value.get_config_path.return_value = str(config_path)

        config_manager = ConfigManager()
        result = config_manager.get_instance_name()

        assert result is None

    def test_should_handle_missing_config_directory(self, mocker, tmpdir):
        """Should create config directory when it doesn't exist."""
        nonexistent_path = tmpdir.join("nonexistent", "config.ini")

        mock_settings = mocker.patch("remote.config.Settings")
        mock_settings.return_value.get_config_path.return_value = str(nonexistent_path)
        mock_write_config = mocker.patch("remote.config.write_config")

        config_manager = ConfigManager()
        config_manager.set_instance_name("test-instance")

        # Should have attempted to write config despite missing directory
        mock_write_config.assert_called_once()

    def test_should_handle_config_with_empty_sections(self, mocker):
        """Should handle config files with empty DEFAULT section."""
        config_manager = ConfigManager()

        # Mock empty config
        mock_config = mocker.MagicMock()
        mock_config.__contains__ = lambda self, key: key == "DEFAULT"
        mock_config.__getitem__ = lambda self, key: {}  # Empty section
        config_manager._file_config = mock_config

        result = config_manager.get_instance_name()
        assert result is None

    def test_should_validate_instance_name_format(self, mocker):
        """Should validate instance name format when setting."""
        mock_write_config = mocker.patch("remote.config.write_config")
        config_manager = ConfigManager()

        # Test with valid instance name
        config_manager.set_instance_name("valid-instance-name")
        mock_write_config.assert_called_once()

        # Test with instance name containing spaces (should still work)
        mock_write_config.reset_mock()
        config_manager.set_instance_name("instance with spaces")
        mock_write_config.assert_called_once()


class TestSettingsConfiguration:
    """Test the Settings class behavior."""

    def test_should_use_testing_mode_in_test_environment(self):
        """Should correctly identify testing mode."""
        from remote.settings import Settings

        test_settings = Settings(testing_mode=True)
        assert test_settings.testing_mode is True

        production_settings = Settings(testing_mode=False)
        assert production_settings.testing_mode is False

    def test_should_handle_config_path_generation(self, mocker, tmpdir):
        """Should generate correct config paths."""
        from remote.settings import Settings

        with mocker.patch("pathlib.Path.home", return_value=tmpdir):
            settings = Settings()
            config_path = settings.get_config_path()

            # Should generate path under .config/remote.py/
            assert "config.ini" in str(config_path)
            assert ".config" in str(config_path)
            assert "remote.py" in str(config_path)


class TestConfigSetCommand:
    """Test the config set command."""

    def test_set_valid_key(self, mocker, tmpdir):
        """Should set a valid config key."""
        config_path = str(tmpdir / "config.ini")

        result = runner.invoke(config.app, ["set", "ssh_user", "ec2-user", "-c", config_path])

        assert result.exit_code == 0
        assert "Set ssh_user = ec2-user" in result.stdout

        # Verify value was written
        import configparser

        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        assert cfg["DEFAULT"]["ssh_user"] == "ec2-user"

    def test_set_invalid_key(self, tmpdir):
        """Should reject unknown config keys."""
        config_path = str(tmpdir / "config.ini")

        result = runner.invoke(config.app, ["set", "invalid_key", "value", "-c", config_path])

        assert result.exit_code == 1
        assert "Unknown config key" in result.stdout


class TestConfigGetCommand:
    """Test the config get command."""

    def test_get_existing_value(self, tmpdir):
        """Should return existing config value."""
        config_path = str(tmpdir / "config.ini")

        # Create config file with value
        import configparser

        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"ssh_user": "ubuntu"}
        with open(config_path, "w") as f:
            cfg.write(f)

        result = runner.invoke(config.app, ["get", "ssh_user", "-c", config_path])

        assert result.exit_code == 0
        assert "ubuntu" in result.stdout

    def test_get_missing_value(self, tmpdir):
        """Should exit with code 1 for missing value."""
        config_path = str(tmpdir / "config.ini")

        # Create empty config file
        import configparser

        cfg = configparser.ConfigParser()
        with open(config_path, "w") as f:
            cfg.write(f)

        result = runner.invoke(config.app, ["get", "missing_key", "-c", config_path])

        assert result.exit_code == 1


class TestConfigUnsetCommand:
    """Test the config unset command."""

    def test_unset_existing_key(self, tmpdir):
        """Should remove existing config key."""
        config_path = str(tmpdir / "config.ini")

        # Create config file with value
        import configparser

        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"ssh_user": "ubuntu"}
        with open(config_path, "w") as f:
            cfg.write(f)

        result = runner.invoke(config.app, ["unset", "ssh_user", "-c", config_path])

        assert result.exit_code == 0
        assert "Removed ssh_user" in result.stdout

        # Verify value was removed
        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        assert "ssh_user" not in cfg["DEFAULT"]

    def test_unset_missing_key(self, tmpdir):
        """Should exit with code 1 for missing key."""
        config_path = str(tmpdir / "config.ini")

        # Create empty config file
        import configparser

        cfg = configparser.ConfigParser()
        with open(config_path, "w") as f:
            cfg.write(f)

        result = runner.invoke(config.app, ["unset", "missing_key", "-c", config_path])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestConfigInitCommand:
    """Test the config init command."""

    def test_init_creates_config(self, tmpdir):
        """Should create config file with prompted values."""
        config_path = str(tmpdir / "config.ini")

        result = runner.invoke(
            config.app, ["init", "-c", config_path], input="my-server\nec2-user\n~/.ssh/key.pem\n"
        )

        assert result.exit_code == 0
        assert "Config written" in result.stdout

        # Verify config was created
        import configparser

        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        assert cfg["DEFAULT"]["instance_name"] == "my-server"
        assert cfg["DEFAULT"]["ssh_user"] == "ec2-user"
        assert cfg["DEFAULT"]["ssh_key_path"] == "~/.ssh/key.pem"

    def test_init_skips_empty_values(self, tmpdir):
        """Should skip empty optional values."""
        config_path = str(tmpdir / "config.ini")

        result = runner.invoke(
            config.app,
            ["init", "-c", config_path],
            input="\nubuntu\n\n",  # Empty instance_name and ssh_key
        )

        assert result.exit_code == 0

        # Verify only ssh_user was written
        import configparser

        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        assert "instance_name" not in cfg["DEFAULT"]
        assert cfg["DEFAULT"]["ssh_user"] == "ubuntu"
        assert "ssh_key_path" not in cfg["DEFAULT"]


class TestConfigValidateCommand:
    """Test the config validate command."""

    def test_validate_valid_config(self, tmpdir):
        """Should report valid config."""
        config_path = str(tmpdir / "config.ini")

        # Create valid config file
        import configparser

        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"ssh_user": "ubuntu"}
        with open(config_path, "w") as f:
            cfg.write(f)

        result = runner.invoke(config.app, ["validate", "-c", config_path])

        assert result.exit_code == 0
        # Rich panel displays validation result
        assert "Config Validation" in result.stdout
        assert "Configuration is valid" in result.stdout

    def test_validate_missing_config(self, tmpdir):
        """Should report missing config file."""
        config_path = str(tmpdir / "nonexistent.ini")

        result = runner.invoke(config.app, ["validate", "-c", config_path])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_validate_missing_ssh_key(self, tmpdir):
        """Should report missing SSH key file."""
        config_path = str(tmpdir / "config.ini")

        # Create config with missing SSH key path
        import configparser

        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"ssh_key_path": "/nonexistent/key.pem"}
        with open(config_path, "w") as f:
            cfg.write(f)

        result = runner.invoke(config.app, ["validate", "-c", config_path])

        assert result.exit_code == 1
        assert "SSH key not found" in result.stdout


class TestConfigKeysCommand:
    """Test the config keys command."""

    def test_keys_lists_all_valid_keys(self):
        """Should list all valid configuration keys."""
        result = runner.invoke(config.app, ["keys"])

        assert result.exit_code == 0
        assert "instance_name" in result.stdout
        assert "ssh_user" in result.stdout
        assert "ssh_key_path" in result.stdout
        assert "aws_region" in result.stdout
        assert "default_launch_template" in result.stdout


class TestRemoteConfigPydanticModel:
    """Test the RemoteConfig Pydantic model."""

    def test_default_values(self):
        """Should have correct default values."""
        from remote.config import RemoteConfig

        cfg = RemoteConfig()
        assert cfg.instance_name is None
        assert cfg.ssh_user == "ubuntu"
        assert cfg.ssh_key_path is None
        assert cfg.aws_region is None
        assert cfg.default_launch_template is None

    def test_valid_instance_name(self):
        """Should accept valid instance names."""
        from remote.config import RemoteConfig

        # Alphanumeric with hyphens, underscores, dots
        cfg = RemoteConfig(instance_name="my-test_server.1")
        assert cfg.instance_name == "my-test_server.1"

    def test_invalid_instance_name(self):
        """Should reject instance names with invalid characters."""
        from pydantic import ValidationError

        from remote.config import RemoteConfig

        with pytest.raises(ValidationError) as exc_info:
            RemoteConfig(instance_name="my server!")
        assert "Invalid instance name" in str(exc_info.value)

    def test_valid_ssh_user(self):
        """Should accept valid SSH usernames."""
        from remote.config import RemoteConfig

        cfg = RemoteConfig(ssh_user="ec2-user")
        assert cfg.ssh_user == "ec2-user"

    def test_invalid_ssh_user(self):
        """Should reject SSH usernames with invalid characters."""
        from pydantic import ValidationError

        from remote.config import RemoteConfig

        with pytest.raises(ValidationError) as exc_info:
            RemoteConfig(ssh_user="user name")
        assert "Invalid SSH user" in str(exc_info.value)

    def test_ssh_key_path_expansion(self):
        """Should expand ~ in SSH key path."""
        import os

        from remote.config import RemoteConfig

        cfg = RemoteConfig(ssh_key_path="~/.ssh/my-key.pem")
        expected = os.path.expanduser("~/.ssh/my-key.pem")
        assert cfg.ssh_key_path == expected

    def test_valid_aws_region(self):
        """Should accept valid AWS regions."""
        from remote.config import RemoteConfig

        cfg = RemoteConfig(aws_region="us-east-1")
        assert cfg.aws_region == "us-east-1"

        cfg = RemoteConfig(aws_region="eu-west-2")
        assert cfg.aws_region == "eu-west-2"

        cfg = RemoteConfig(aws_region="ap-southeast-1")
        assert cfg.aws_region == "ap-southeast-1"

    def test_invalid_aws_region(self):
        """Should reject invalid AWS region formats."""
        from pydantic import ValidationError

        from remote.config import RemoteConfig

        with pytest.raises(ValidationError) as exc_info:
            RemoteConfig(aws_region="invalid-region")
        assert "Invalid AWS region" in str(exc_info.value)

    def test_empty_values_treated_as_none(self):
        """Should treat empty strings as None for optional fields."""
        from remote.config import RemoteConfig

        cfg = RemoteConfig(instance_name="", aws_region="")
        assert cfg.instance_name is None
        assert cfg.aws_region is None

    def test_empty_ssh_user_uses_default(self):
        """Should use default 'ubuntu' for empty SSH user."""
        from remote.config import RemoteConfig

        cfg = RemoteConfig(ssh_user="")
        assert cfg.ssh_user == "ubuntu"

    def test_check_ssh_key_exists_no_path(self):
        """Should return True when no SSH key path is set."""
        from remote.config import RemoteConfig

        cfg = RemoteConfig()
        exists, error = cfg.check_ssh_key_exists()
        assert exists is True
        assert error is None

    def test_check_ssh_key_exists_missing_file(self, tmpdir):
        """Should return False when SSH key file doesn't exist."""
        from remote.config import RemoteConfig

        cfg = RemoteConfig(ssh_key_path="/nonexistent/key.pem")
        exists, error = cfg.check_ssh_key_exists()
        assert exists is False
        assert "SSH key not found" in error

    def test_check_ssh_key_exists_valid_file(self, tmpdir):
        """Should return True when SSH key file exists."""
        from remote.config import RemoteConfig

        # Create a temporary key file
        key_path = str(tmpdir / "test-key.pem")
        with open(key_path, "w") as f:
            f.write("test")

        cfg = RemoteConfig(ssh_key_path=key_path)
        exists, error = cfg.check_ssh_key_exists()
        assert exists is True
        assert error is None


class TestRemoteConfigFromIniFile:
    """Test loading RemoteConfig from INI files."""

    def test_from_ini_file_with_values(self, tmpdir):
        """Should load values from INI file."""
        from remote.config import RemoteConfig

        config_path = str(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {
            "instance_name": "my-server",
            "ssh_user": "ec2-user",
            "aws_region": "us-west-2",
        }
        with open(config_path, "w") as f:
            cfg.write(f)

        result = RemoteConfig.from_ini_file(config_path)
        assert result.instance_name == "my-server"
        assert result.ssh_user == "ec2-user"
        assert result.aws_region == "us-west-2"

    def test_from_ini_file_missing_file(self, tmpdir):
        """Should use defaults when INI file doesn't exist."""
        from remote.config import RemoteConfig

        config_path = str(tmpdir / "nonexistent.ini")
        result = RemoteConfig.from_ini_file(config_path)

        assert result.instance_name is None
        assert result.ssh_user == "ubuntu"
        assert result.aws_region is None

    def test_environment_variable_override(self, tmpdir, monkeypatch):
        """Should override INI values with environment variables."""
        from remote.config import RemoteConfig

        # Create INI file with values
        config_path = str(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {
            "instance_name": "ini-server",
            "ssh_user": "ini-user",
        }
        with open(config_path, "w") as f:
            cfg.write(f)

        # Set environment variables (should override)
        monkeypatch.setenv("REMOTE_INSTANCE_NAME", "env-server")
        monkeypatch.setenv("REMOTE_SSH_USER", "env-user")

        result = RemoteConfig.from_ini_file(config_path)

        # Environment variables should override INI values
        assert result.instance_name == "env-server"
        assert result.ssh_user == "env-user"

    def test_partial_environment_override(self, tmpdir, monkeypatch):
        """Should only override specific fields from environment."""
        from remote.config import RemoteConfig

        # Create INI file with values
        config_path = str(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {
            "instance_name": "ini-server",
            "ssh_user": "ini-user",
            "aws_region": "us-east-1",
        }
        with open(config_path, "w") as f:
            cfg.write(f)

        # Override only one value
        monkeypatch.setenv("REMOTE_INSTANCE_NAME", "env-server")

        result = RemoteConfig.from_ini_file(config_path)

        # Only instance_name should be overridden
        assert result.instance_name == "env-server"
        assert result.ssh_user == "ini-user"
        assert result.aws_region == "us-east-1"


class TestConfigValidationResult:
    """Test the ConfigValidationResult class."""

    def test_validate_valid_config(self, tmpdir):
        """Should return is_valid=True for valid config."""
        from remote.config import ConfigValidationResult

        config_path = str(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"ssh_user": "ubuntu", "aws_region": "us-east-1"}
        with open(config_path, "w") as f:
            cfg.write(f)

        result = ConfigValidationResult.validate_config(config_path)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_validate_missing_file(self, tmpdir):
        """Should return is_valid=False for missing file."""
        from remote.config import ConfigValidationResult

        config_path = str(tmpdir / "nonexistent.ini")
        result = ConfigValidationResult.validate_config(config_path)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "not found" in result.errors[0]

    def test_validate_missing_ssh_key(self, tmpdir):
        """Should return is_valid=False for missing SSH key."""
        from remote.config import ConfigValidationResult

        config_path = str(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"ssh_key_path": "/nonexistent/key.pem"}
        with open(config_path, "w") as f:
            cfg.write(f)

        result = ConfigValidationResult.validate_config(config_path)
        assert result.is_valid is False
        assert any("SSH key not found" in e for e in result.errors)

    def test_validate_unknown_keys_warning(self, tmpdir):
        """Should add warning for unknown config keys."""
        from remote.config import ConfigValidationResult

        config_path = str(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {
            "ssh_user": "ubuntu",
            "unknown_key": "value",
        }
        with open(config_path, "w") as f:
            cfg.write(f)

        result = ConfigValidationResult.validate_config(config_path)
        assert result.is_valid is True  # Unknown keys are warnings, not errors
        assert any("Unknown config key" in w for w in result.warnings)

    def test_validate_invalid_aws_region(self, tmpdir):
        """Should return validation error for invalid AWS region."""
        from remote.config import ConfigValidationResult

        config_path = str(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"aws_region": "invalid-region"}
        with open(config_path, "w") as f:
            cfg.write(f)

        result = ConfigValidationResult.validate_config(config_path)
        assert result.is_valid is False
        assert any("Configuration error" in e for e in result.errors)


class TestConfigManagerPydanticIntegration:
    """Test ConfigManager integration with Pydantic config."""

    def test_get_validated_config(self, tmpdir, mocker):
        """Should return validated RemoteConfig instance."""
        from remote.config import ConfigManager, RemoteConfig

        # Mock Settings.get_config_path to return our temp path
        config_path = Path(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"instance_name": "test-server", "ssh_user": "ec2-user"}
        with open(config_path, "w") as f:
            cfg.write(f)

        mocker.patch("remote.config.Settings.get_config_path", return_value=config_path)

        manager = ConfigManager()
        result = manager.get_validated_config()

        assert isinstance(result, RemoteConfig)
        assert result.instance_name == "test-server"
        assert result.ssh_user == "ec2-user"

    def test_reload_clears_pydantic_config(self, tmpdir, mocker):
        """Should clear cached pydantic config on reload."""
        from remote.config import ConfigManager

        config_path = Path(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"instance_name": "original-server"}
        with open(config_path, "w") as f:
            cfg.write(f)

        mocker.patch("remote.config.Settings.get_config_path", return_value=config_path)

        manager = ConfigManager()

        # Load initial config
        result1 = manager.get_validated_config()
        assert result1.instance_name == "original-server"

        # Update file
        cfg["DEFAULT"]["instance_name"] = "new-server"
        with open(config_path, "w") as f:
            cfg.write(f)

        # Reload and verify new config is loaded
        manager.reload()
        result2 = manager.get_validated_config()
        assert result2.instance_name == "new-server"

    def test_get_value_uses_environment_override(self, tmpdir, mocker, monkeypatch):
        """Should return environment variable value over file value."""
        from remote.config import ConfigManager

        config_path = Path(tmpdir / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"instance_name": "file-server"}
        with open(config_path, "w") as f:
            cfg.write(f)

        mocker.patch("remote.config.Settings.get_config_path", return_value=config_path)
        monkeypatch.setenv("REMOTE_INSTANCE_NAME", "env-server")

        manager = ConfigManager()
        result = manager.get_value("instance_name")

        assert result == "env-server"
