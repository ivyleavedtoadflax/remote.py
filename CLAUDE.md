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

### CLI Parameter Patterns

Commands use the following consistent patterns for parameters:

#### 1. Optional Arguments with Config Fallback
For instance-targeting commands where a default can be configured:
```python
instance_name: str | None = typer.Argument(None, help="Instance name")
```
Then resolve with: `resolve_instance_or_exit(instance_name)` which falls back to the configured default instance.

**Used in**: `instance.py` (status, start, stop, connect, exec, type, terminate), `ami.py` (create), `snapshot.py` (list), `volume.py` (list)

#### 2. Required Arguments
For commands where a value must always be provided:
```python
template_name: str = typer.Argument(..., help="Launch template name")
```
The `...` makes the argument required with no default.

**Used in**: `ami.py` (template-versions, template-info)

#### 3. Required Options
For commands needing multiple required values that aren't positional:
```python
volume_id: str = typer.Option(..., "--volume-id", "-v", help="Volume ID (required)")
name: str = typer.Option(..., "--name", "-n", help="Snapshot name (required)")
```

**Used in**: `snapshot.py` (create)

#### 4. Optional Arguments with Interactive Prompts
For commands where selection from available resources is needed:
```python
cluster_name: str | None = typer.Argument(None, help="Cluster name")
# ...
if not cluster_name:
    cluster_name = prompt_for_cluster_name()  # Shows selection menu
```

**Used in**: `ecs.py` (list-services, scale)

#### 5. Optional Options with Defaults
For optional configuration that has sensible defaults:
```python
version: str = typer.Option("$Latest", "-V", "--version", help="Template version")
yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt")
```

**Used in**: Most commands for flags like `--yes`, `--verbose`, `--timeout`

#### Guidelines for New Commands
1. Use **Pattern 1** for instance-targeting commands where config fallback makes sense
2. Use **Pattern 2** for required positional arguments (typically resource names)
3. Use **Pattern 3** when multiple required values are needed and order isn't intuitive
4. Use **Pattern 4** when the user needs to select from available AWS resources
5. Always provide clear help text describing the parameter purpose
6. Include `--yes`/`-y` option for commands that modify resources

### Testing Architecture
- **100% test coverage target** with comprehensive test suite (227+ tests)
- **Factory pattern** for test data generation with immutable defaults
- **Property-based testing** using Hypothesis for edge case discovery
- **Mocked AWS calls** - no real AWS credentials required for testing
- **Test isolation** - tests don't interfere with local configuration

### Entry Point
The package installs as `remote` command (see pyproject.toml scripts section), with the instance module serving as the default command namespace.
