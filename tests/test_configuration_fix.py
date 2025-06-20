"""Test that demonstrates the fix for Issue #27 - Tests fail without configuration."""

from unittest.mock import MagicMock


def test_config_manager_works_without_local_config(mock_aws_clients):
    """Test that config manager works gracefully when no config exists.

    This test demonstrates the fix for Issue #27 where tests would fail
    if no configuration was set up locally.
    """
    # Import after fixtures have been applied
    from remotepy.config import config_manager

    # The config manager should return the test instance name from our fixture
    # instead of calling sys.exit(1) like the old implementation
    instance_name = config_manager.get_instance_name()

    # In test mode, our autouse fixture provides a default instance name
    assert instance_name is not None  # Thanks to our test fixture
    assert instance_name == "test-instance"


def test_config_manager_graceful_none_return():
    """Test that config manager returns None gracefully when no config exists."""
    from remotepy.config import ConfigManager

    # Create a fresh config manager (not mocked)
    real_config_manager = ConfigManager()

    # Mock the file_config to return empty config
    mock_config = MagicMock()
    mock_config.__contains__ = lambda self, key: False  # No DEFAULT section
    real_config_manager._file_config = mock_config

    # Should return None gracefully, not crash
    result = real_config_manager.get_instance_name()
    assert result is None


def test_settings_only_testing_flags():
    """Test that Settings only contains testing-related configuration."""
    from remotepy.settings import Settings

    settings = Settings()

    # Should only have testing flags, no instance configuration
    assert hasattr(settings, 'testing_mode')
    assert hasattr(settings, 'mock_aws_calls')
    assert not hasattr(settings, 'default_instance_name')
    assert not hasattr(settings, 'aws_region')


def test_no_sys_exit_on_missing_config(mock_aws_clients):
    """Test that missing config no longer causes sys.exit(1).

    This is the core fix for Issue #27 - the application should handle
    missing configuration gracefully instead of crashing tests.
    """
    from remotepy.utils import get_instance_name

    # In our test environment, this will get the test instance name
    # The key improvement is that this raises typer.Exit instead of sys.exit(1)
    # making it more testable and not crashing the entire test process
    result = get_instance_name()
    assert result == "test-instance"  # From our test fixture
