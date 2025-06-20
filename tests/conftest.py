"""Shared test configuration and fixtures."""

import configparser
from unittest.mock import MagicMock, patch

import pytest

from remotepy.settings import Settings


@pytest.fixture(autouse=True)
def test_config():
    """Automatically use test configuration for all tests.

    This fixture ensures that tests don't depend on the user's local configuration
    and provides sensible defaults for testing.
    """
    test_settings = Settings(
        testing_mode=True,
        mock_aws_calls=True
    )

    # Create a mock config manager that returns test instance name
    mock_config_manager = MagicMock()
    mock_config_manager.get_instance_name.return_value = "test-instance"

    # Mock the global settings object and config manager
    with patch("remotepy.settings.settings", test_settings):
        with patch("remotepy.config.config_manager", mock_config_manager):
            yield test_settings


@pytest.fixture
def test_config_file(tmpdir):
    """Create a temporary config file for testing."""
    config_path = tmpdir.join("config.ini")
    cfg = configparser.ConfigParser()
    cfg["DEFAULT"] = {"instance_name": "test-instance"}

    with open(config_path, "w") as f:
        cfg.write(f)

    return str(config_path)


@pytest.fixture
def mock_aws_clients(mocker):
    """Mock all AWS clients used in the application."""
    # Mock EC2 client
    mock_ec2 = mocker.patch("remotepy.utils.ec2_client", autospec=True)
    mock_ec2.describe_instances.return_value = {"Reservations": []}

    # Mock ECS client
    mock_ecs = mocker.patch("remotepy.ecs.ecs_client", autospec=True)
    mock_ecs.list_clusters.return_value = {"clusterArns": []}

    return {
        "ec2": mock_ec2,
        "ecs": mock_ecs
    }
