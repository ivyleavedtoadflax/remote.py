
from typer.testing import CliRunner

from remotepy.__main__ import app

runner = CliRunner()


def test_version_command(mocker):
    mock_version = mocker.patch(
        "remotepy.__main__.importlib.metadata.version",
        return_value="0.2.5"
    )

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    mock_version.assert_called_once_with("remotepy")
    assert "0.2.5" in result.stdout


def test_main_app_imports():
    """Test that all sub-apps are properly imported and added to main app."""
    # Test that the main app structure exists
    from remotepy.__main__ import app as main_app
    from remotepy.instance import app as instance_app

    # The main app should be the same as instance app (enhanced with sub-apps)
    assert main_app is instance_app

    # Test that the app has commands and groups registered
    assert len(app.registered_commands) > 0
    assert len(app.registered_groups) > 0


def test_main_app_structure():
    """Test the overall structure of the main app."""
    # Test that imports work correctly
    # Test that the main module imports exist
    from remotepy import ami, config, ecs, instance, snapshot, volume

    # Verify that we can access the apps
    assert hasattr(ami, 'app')
    assert hasattr(config, 'app')
    assert hasattr(ecs, 'app')
    assert hasattr(instance, 'app')
    assert hasattr(snapshot, 'app')
    assert hasattr(volume, 'app')


def test_help_shows_subcommands():
    """Test that help output shows all available subcommands."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "ami" in result.stdout
    assert "config" in result.stdout
    assert "snapshot" in result.stdout
    assert "volume" in result.stdout
    assert "ecs" in result.stdout
    assert "version" in result.stdout


def test_ami_subcommand_exists():
    """Test that ami subcommand is properly registered."""
    result = runner.invoke(app, ["ami", "--help"])
    assert result.exit_code == 0
    assert "ami" in result.stdout.lower()


def test_config_subcommand_exists():
    """Test that config subcommand is properly registered."""
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "config" in result.stdout.lower()


def test_snapshot_subcommand_exists():
    """Test that snapshot subcommand is properly registered."""
    result = runner.invoke(app, ["snapshot", "--help"])
    assert result.exit_code == 0
    assert "snapshot" in result.stdout.lower()


def test_volume_subcommand_exists():
    """Test that volume subcommand is properly registered."""
    result = runner.invoke(app, ["volume", "--help"])
    assert result.exit_code == 0
    assert "volume" in result.stdout.lower()


def test_ecs_subcommand_exists():
    """Test that ecs subcommand is properly registered."""
    result = runner.invoke(app, ["ecs", "--help"])
    assert result.exit_code == 0
    assert "ecs" in result.stdout.lower()


def test_default_instance_commands_work():
    """Test that instance commands work as default commands."""
    # Test that we can call instance commands directly without 'instance' prefix
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    # Should see instance commands in the main help
    assert "list" in result.stdout or "List" in result.stdout
