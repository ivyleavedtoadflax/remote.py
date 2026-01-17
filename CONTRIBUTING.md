# Contributing to Remote.py

Thank you for your interest in contributing to Remote.py! This guide will help you get started with development and explain our contribution workflow.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/ivyleavedtoadflax/remote.py.git
cd remote.py

# Install dependencies including dev tools
uv sync --dev

# Install pre-commit hooks (recommended)
uv run pre-commit install
```

### Verify Setup

```bash
# Run tests to verify everything works
uv run pytest

# Check that the CLI works
uv run remote --help
```

## Development Commands

### Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py

# Run tests with coverage report
uv run pytest --cov

# Generate HTML coverage report
uv run pytest --cov --cov-report=html
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Fix linting issues automatically
uv run ruff check . --fix

# Type checking
uv run mypy remotepy/
```

## Making Changes

### Branch Naming

Use descriptive branch names with a prefix indicating the type of change:

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions or changes

Examples:
- `feature/add-instance-pricing`
- `fix/ssh-connection-timeout`
- `docs/update-readme`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring (no functional change)
- `test:` Test additions or modifications
- `chore:` Maintenance tasks

Examples:
```
feat: Add instance pricing to list output
fix: Handle SSH connection timeout gracefully
docs: Update installation instructions
refactor: Extract validation logic to separate module
test: Add edge cases for pagination handling
```

### Pull Request Process

1. **Create a feature branch** from `main`
2. **Make your changes** following the code style guidelines
3. **Write or update tests** for your changes
4. **Run the full test suite**: `uv run pytest`
5. **Run linting and formatting**: `uv run ruff check . && uv run ruff format .`
6. **Run type checking**: `uv run mypy remotepy/`
7. **Submit a pull request** with a clear description
8. **Address review feedback** promptly

## Code Style

### General Guidelines

- Use type hints for all function parameters and return values
- Follow existing patterns in the codebase
- Keep functions focused and single-purpose
- Write docstrings for public functions and classes
- Prefer explicit over implicit code

### Type Hints

```python
# Good
def get_instance_by_name(name: str) -> dict[str, Any] | None:
    ...

# Avoid
def get_instance_by_name(name):
    ...
```

### Error Handling

- Use the custom exception hierarchy in `remotepy/exceptions.py`
- Provide user-friendly error messages
- Include suggestions for fixing common issues

### Testing

- All new features need tests
- Target 100% test coverage for new code
- Mock AWS calls - no real credentials needed
- Use the factory pattern for test data (see `tests/factories.py`)
- Test both success and error paths

## Testing Guidelines

### Test Structure

```python
def test_function_does_expected_behavior(mock_aws_client):
    """Test that function handles the happy path correctly."""
    # Arrange
    mock_aws_client.describe_instances.return_value = {...}

    # Act
    result = function_under_test()

    # Assert
    assert result == expected_value
```

### Mocking AWS Calls

All AWS API calls should be mocked in tests. See existing tests for examples:

```python
@pytest.fixture
def mock_ec2_client(mocker):
    mock = mocker.patch("remotepy.utils.get_ec2_client")
    return mock.return_value
```

### Property-Based Testing

We use [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_handles_arbitrary_input(text):
    # Test should pass for any string input
    result = validate_input(text)
    assert isinstance(result, bool)
```

## Architecture Overview

The codebase follows a modular design:

- **`remotepy/__main__.py`** - CLI entry point and command routing
- **`remotepy/instance.py`** - EC2 instance operations
- **`remotepy/ami.py`** - AMI creation and launching
- **`remotepy/ecs.py`** - ECS cluster and service management
- **`remotepy/config.py`** - Configuration management
- **`remotepy/utils.py`** - Shared utilities and AWS client management
- **`remotepy/exceptions.py`** - Custom exception hierarchy
- **`remotepy/validation.py`** - Input validation utilities

## Questions?

If you have questions about contributing, please:

1. Check existing issues and pull requests
2. Open a new issue with your question
3. Tag it with the `question` label

We appreciate your contributions!
