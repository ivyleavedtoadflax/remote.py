# Remote.py

A python port of the [remote](https://github.com/wellcometrust/remote) tool for controlling remote instances on AWS.

# Getting started

The package is pip installable and can be installed directly from github. We recommend using pipx:

```
pipx install git+https://github.com/ivyleavedtoadflax/remote.py.git
```

# Usage

Add the name of your default instance to the config file

```
remotepy config add
```

Check that is was set

```
remotepy config show
```

Start the instance:

```
remotepy start
```

Connect to the instance with ssh

```
remotepy connect
```

Connect to the instance with ssh and port forwarding and verbosity

```
remotepy connect -p 1234:localhost:1234 -v
```

Stop the instance:

```
remotepy stop
```

Get the instance status:

```
remotepy status
```

To run commands on a different instance, pass the name as an argument:

```
remotepy status another_ec2_instance
```

## Configuration

RemotePy uses a simple configuration file to store your default instance and other settings.

### Config File Setup

The configuration is stored in `~/.config/remote.py/config.ini`

```bash
# Add default instance interactively
remotepy config add

# Show current configuration  
remotepy config show
```

That's it! The config file is the single source of truth for your settings.

# For development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and requires Python 3.12+.

## Setup

```bash
# Install dependencies
uv sync --dev

# Install pre-commit hooks (optional)
uv run pre-commit install
```

## Development Commands

```bash
# Run tests
uv run pytest

# Code formatting and linting
uv run ruff format .      # Format code
uv run ruff check .       # Lint code
uv run ruff check . --fix # Fix linting issues

# Build package
uv build
```

## Testing

The project includes comprehensive testing infrastructure:

### Running Tests
```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py
```

### Test Features
- **No AWS credentials required** - All AWS calls are mocked during testing
- **Test isolation** - Tests don't interfere with local configuration files
- **Comprehensive coverage** - Tests for configuration, AWS operations, and CLI commands
- **Issue #27 resolved** - Tests work without any local setup or environment variables

## CI/CD

The project includes automated CI/CD:
- **Tests** run automatically on all pushes
- **Code quality** checks (ruff linting/formatting) 
- **Manual publishing** workflow for PyPI releases
