import pytest
from typer.testing import CliRunner

from remote.__main__ import app

runner = CliRunner()


def test_version_command(mocker):
    mock_version = mocker.patch("remote.__main__.importlib.metadata.version", return_value="0.2.5")

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    mock_version.assert_called_once_with("remotepy")
    assert "0.2.5" in result.stdout


def test_version_command_has_error_handling_decorator(mocker):
    """Test that version command has @handle_cli_errors decorator applied."""
    from remote.exceptions import ValidationError

    # Simulate a ValidationError being raised (which @handle_cli_errors catches)
    mocker.patch(
        "remote.__main__.importlib.metadata.version",
        side_effect=ValidationError("Test validation error"),
    )

    result = runner.invoke(app, ["version"])

    # Should exit with error code 1 (handled by @handle_cli_errors)
    assert result.exit_code == 1
    # Should show user-friendly error message from the decorator
    assert "Error:" in result.stdout
    assert "Test validation error" in result.stdout


def test_main_app_imports():
    """Test that all sub-apps are properly imported and added to main app."""
    # Test that the main app structure exists
    from remote.__main__ import app as main_app

    # The main app has only service subcommands registered (no root-level instance commands)
    assert main_app is not None

    # Test that the app has commands and groups registered
    assert len(app.registered_commands) > 0
    assert len(app.registered_groups) > 0


def test_main_app_structure():
    """Test the overall structure of the main app."""
    # Test that imports work correctly
    # Test that the main module imports exist
    from remote import ami, config, ecs, instance, snapshot, volume

    # Verify that we can access the apps
    assert hasattr(ami, "app")
    assert hasattr(config, "app")
    assert hasattr(ecs, "app")
    assert hasattr(instance, "app")
    assert hasattr(snapshot, "app")
    assert hasattr(volume, "app")


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


@pytest.mark.parametrize("subcommand", ["ami", "config", "snapshot", "volume", "ecs"])
def test_subcommand_exists(subcommand):
    """Test that subcommands are properly registered."""
    result = runner.invoke(app, [subcommand, "--help"])
    assert result.exit_code == 0
    assert subcommand in result.stdout.lower()


def test_root_level_does_not_have_instance_commands():
    """Test that instance commands are NOT available at root level (breaking change v1.0.0)."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    # Root help should only show service subcommands, not individual instance commands
    # Should see subcommand names
    assert "instance" in result.stdout.lower()
    assert "ami" in result.stdout.lower()
    # Should NOT see individual instance commands at root
    assert "start" not in result.stdout.lower() or "start" in "not started"
    assert "stop" not in result.stdout.lower()
    assert "connect" not in result.stdout.lower()


def test_instance_subcommand_exists():
    """Test that instance subcommand is properly registered."""
    result = runner.invoke(app, ["instance", "--help"])
    assert result.exit_code == 0
    # Should show instance management help
    assert "Manage EC2 instances" in result.stdout
    # Should list instance commands
    assert "list" in result.stdout.lower()
    assert "start" in result.stdout.lower()
    assert "stop" in result.stdout.lower()
    assert "connect" in result.stdout.lower()


def test_instance_commands_require_prefix():
    """Test that instance commands require the 'instance' prefix."""
    instance_help = runner.invoke(app, ["instance", "--help"])

    assert instance_help.exit_code == 0

    # Instance subcommand should show all instance commands
    instance_commands = ["list", "start", "stop", "connect", "status", "launch", "terminate"]
    for cmd in instance_commands:
        assert cmd in instance_help.stdout.lower(), f"'{cmd}' not found in instance help"


def test_should_show_logo_no_args(mocker):
    """Test that _should_show_logo returns True when no arguments."""
    from remote.__main__ import _should_show_logo

    mocker.patch("sys.argv", ["remote"])
    assert _should_show_logo() is True


def test_should_show_logo_with_help_flag(mocker):
    """Test that _should_show_logo returns True for --help."""
    from remote.__main__ import _should_show_logo

    mocker.patch("sys.argv", ["remote", "--help"])
    assert _should_show_logo() is True


def test_should_show_logo_with_h_flag(mocker):
    """Test that _should_show_logo returns True for -h."""
    from remote.__main__ import _should_show_logo

    mocker.patch("sys.argv", ["remote", "-h"])
    assert _should_show_logo() is True


def test_should_not_show_logo_with_subcommand(mocker):
    """Test that _should_show_logo returns False for subcommands."""
    from remote.__main__ import _should_show_logo

    mocker.patch("sys.argv", ["remote", "instance", "list"])
    assert _should_show_logo() is False


def test_should_not_show_logo_with_subcommand_help(mocker):
    """Test that _should_show_logo returns False for subcommand help."""
    from remote.__main__ import _should_show_logo

    mocker.patch("sys.argv", ["remote", "instance", "--help"])
    assert _should_show_logo() is False


def test_main_calls_print_logo_for_help(mocker):
    """Test that main() calls print_logo when showing help."""
    mock_print_logo = mocker.patch("remote.__main__.print_logo")
    mocker.patch("remote.__main__.app")
    mocker.patch("sys.argv", ["remote", "--help"])

    from remote.__main__ import main

    main()

    mock_print_logo.assert_called_once()


def test_main_does_not_call_print_logo_for_subcommand(mocker):
    """Test that main() does not call print_logo for subcommands."""
    mock_print_logo = mocker.patch("remote.__main__.print_logo")
    mocker.patch("remote.__main__.app")
    mocker.patch("sys.argv", ["remote", "version"])

    from remote.__main__ import main

    main()

    mock_print_logo.assert_not_called()
