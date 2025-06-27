# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
```bash
uv run pytest            # Run all tests
uv run pytest -v         # Run tests with verbose output
uv run pytest tests/test_*.py  # Run specific test file
uv run pytest --cov      # Run tests with coverage report
```

### Code Quality
```bash
uv run ruff format .      # Format code
uv run ruff check .       # Lint code
uv run ruff check . --fix # Fix linting issues automatically
```

### Package Management
```bash
uv sync                   # Install dependencies from lock file
uv sync --dev             # Install with dev dependencies
uv add <package>          # Add new dependency
uv add --dev <package>    # Add dev dependency
uv remove <package>       # Remove dependency
```

### Building and Installation
```bash
uv build                  # Build package
uv pip install .          # Install locally
pipx install .            # Install globally with pipx
```

## Architecture Overview

RemotePy is a modular CLI tool for AWS resource management built with Typer and Boto3. The architecture follows a command-based pattern where each AWS service has its own module:

### Core Modules
- **`instance.py`**: EC2 instance lifecycle management (start/stop/connect/list/terminate/launch)
- **`ami.py`**: AMI creation and instance launching from images
- **`ecs.py`**: ECS cluster and service management, scaling operations
- **`volume.py`**: EBS volume listing and management
- **`snapshot.py`**: EBS snapshot creation and listing
- **`config.py`**: User configuration management (`~/.config/remote.py/config.ini`)
- **`utils.py`**: Shared AWS operations, boto3 client management, formatting utilities
- **`exceptions.py`**: Custom exception hierarchy for better error handling
- **`validation.py`**: Input validation utilities for AWS resource IDs and user input
- **`settings.py`**: Application settings and constants

### CLI Structure
The main app (`__main__.py`) orchestrates sub-applications using Typer's nested command structure:
- `remote [command]` - defaults to instance commands
- `remote [service] [action]` - explicit service targeting
- Each module defines its own Typer app with service-specific commands

### Key Patterns
- **Error Handling**: Custom exception hierarchy with user-friendly error messages for AWS operations
- **Input Validation**: Comprehensive validation for AWS resource IDs and user inputs
- **Boto3 Integration**: Centralized client creation in utils.py with standardized error handling
- **Configuration**: ConfigParser-based settings with automatic directory creation
- **Output Formatting**: Wasabi library for colorized tables and user feedback
- **Instance Targeting**: Commands accept optional instance names or use configured defaults
- **Safe Operations**: Bounds checking and defensive programming throughout

### Testing Architecture
- **100% test coverage target** with comprehensive test suite (227+ tests)
- **Factory pattern** for test data generation with immutable defaults
- **Property-based testing** using Hypothesis for edge case discovery
- **Mocked AWS calls** - no real AWS credentials required for testing
- **Test isolation** - tests don't interfere with local configuration

### Entry Point
The package installs as `remote` command (see pyproject.toml scripts section), with the instance module serving as the default command namespace.
