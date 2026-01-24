# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-01-22

### Added
- **Security group management**: IP whitelisting commands (`instance add-ip` / `instance remove-ip`) with CIDR notation support
- **Volume resize**: New `volume resize` command for EBS volume management
- **File transfer**: Built-in `instance copy` and `instance sync` commands for file transfers via rsync/scp
- **Cumulative cost tracking**: Track and display cumulative instance costs over time
- **Cache clearing**: Mechanism to clear AWS client caches (`--clear-cache` flag)
- **Dynamic region lookup**: Region location names fetched via AWS SSM for accurate pricing
- **SSH timeout configuration**: Configurable timeout for SSH connect command (`--timeout` flag)
- **Remote execution**: `instance exec` command to run commands on remote instances
- **Connect enhancements**: `--start` / `--no-start` flags to auto-start stopped instances
- **Consistency improvements**: Added `--yes` flag to `ami create`, `snapshot create`, `instance type`, and `instance launch` commands

### Changed
- Exclude terminated instances by default in `instance list` command
- Standardized error handling with `@handle_cli_errors` decorator across all modules
- Consolidated SSH configuration into reusable `SSHConfig` class
- Extracted shared utilities: `create_table()`, `resolve_instance_or_exit()`, `get_status_style()`
- Standardized table column styling across CLI
- Moved timing constants to `settings.py` for centralized configuration
- Improved CLI parameter patterns with consistent argument/option usage
- Refactored ECS module with cleaner command names and selection helpers

### Fixed
- AMI pagination for large AMI counts (>1000 images)
- SSH key path validation before connect/exec commands
- Instance type format validation in type command
- Empty DNS validation in connect command
- Exit code semantics (correct codes for non-success scenarios)
- Mutual exclusivity validation for conflicting flags
- ECS scale command validation for desired_count parameter
- Debug logging for silent failure cases in pricing module
- ConfigManager test isolation for local config files

### Documentation
- Added docstring examples to ECS scale and volume list commands
- Documented CLI parameter patterns in CLAUDE.md

## [1.1.0] - 2026-01-18

### Added
- Built-in watch mode for status command (`--watch` / `-w` flag)
- Scheduled instance shutdown (`remote instance stop --in 3h`)
- Auto-stop on start (`remote instance start --stop-in 2h`)
- Cost information in instance list (`--cost` / `-c` flag)
- AWS API contract validation tests for response format verification

### Fixed
- Fixed pricing lookup for EU regions (incorrect location names)
- Fixed Rich Panel expanding to full terminal width

### Changed
- Standardized console output styles across all commands
- Clarified distinction between `instance ls` and `instance status`

## [1.0.0] - 2026-01-18

### Breaking Changes

- **Removed root-level instance commands**: Instance commands now require the `instance` prefix
  - `remote start` -> `remote instance start`
  - `remote stop` -> `remote instance stop`
  - `remote connect` -> `remote instance connect`
  - `remote list` -> `remote instance list`
  - `remote ls` -> `remote instance ls`
  - `remote status` -> `remote instance status`
  - `remote launch` -> `remote instance launch`
  - `remote terminate` -> `remote instance terminate`

### Added

- **Rich output enhancements**: Improved UI with Rich tables and panels
  - ECS cluster/service selection displays in formatted tables
  - Config validation results shown in colored panels
  - Instance launch summary displayed in panels
- **SSH key configuration**: Connect command now reads `ssh_key` from config when `--key` not provided
- **Security policy**: Added SECURITY.md with security measures and reporting process
- **Instance pricing**: Display hourly and monthly cost estimates for instances
- **Template workflow improvements**: New commands for managing launch templates
- **Config workflow improvements**: Enhanced configuration management commands
- **Comprehensive test coverage**: 317+ tests with hypothesis-based property testing

### Changed

- Replaced wasabi with Rich for all output formatting
- Standardized exit patterns across all modules
- Improved CLI help documentation with better descriptions
- Compartmentalized subcommands under service prefixes
- Updated development status to Production/Stable

### Fixed

- Logic bug in `get_instance_by_name()` that could return wrong instance
- SSH subprocess error handling improvements
- Unvalidated array index in AMI launch
- Deprecated datetime API usage
- Function shadowing builtin `list`

### Security

- Completed comprehensive security review
- No critical or high severity issues
- All dependencies audited with pip-audit
- Static analysis with bandit (only low-severity informational findings)

## [0.3.0] - 2026-01-17

### Added

- `--key` / `-k` option for `connect` command to specify SSH private key file
- CI/CD pipelines with GitHub Actions for testing and publishing
- Comprehensive test suite with 227+ tests and 85%+ coverage

### Changed

- **BREAKING**: Minimum Python version is now 3.10 (was 3.8.1)
- Migrated from Poetry to uv package manager
- Replaced flake8/black with Ruff for linting and formatting
- Comprehensive test suite improvements with factory pattern and enhanced organization

### Removed

- Poetry lock file and configuration (replaced by uv)
- tox.ini (testing now handled by CI/CD)

## [0.2.5] - 2025-06-25

### Added

- Custom exception hierarchy for better error classification (`InstanceNotFoundError`, `AWSServiceError`, `ValidationError`, etc.)
- Input validation utilities for AWS resource IDs (instance IDs, volume IDs, snapshot IDs)
- Safe array access utilities with proper bounds checking
- Comprehensive test coverage achieving 100% for ami.py and validation modules (227 tests total)
- Detailed error messages with actionable information for common AWS errors
- Enhanced AWS SDK error handling with user-friendly messages

### Changed

- Replaced unsafe array access patterns with bounds checking throughout codebase
- Replaced generic Exception handling with specific AWS exceptions for better error handling
- Consolidated error handling patterns across all modules for consistency
- Improved error messages to provide more helpful feedback to users
- Updated pre-commit configuration to auto-fix linting issues

### Fixed

- Test failures in `test_get_launch_template_id` with correct module path mocking
- Import statements in test files after function relocation
- Exception handling in config.py to catch all exception types gracefully
- Ruff formatting issues in test files

## [0.2.2] - 2023-07-26

### Added

- Add `remote version` command #39
- Add `remote terminate` command #38
- Add `remote launch` command to create instances from launch templates #22

### Changed

- Split CLI into modules #33
- Use poetry instead of Makefile for dependency management #34

## [0.1.8] - 2022-09-20
### Added
- Add `Launch Time` to `remotepy list` command output table.
