# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
