# Issue 33: v1.0.0 Release Preparation

**Status:** Not started
**Priority:** High
**Target Version:** v1.0.0

## Overview

Prepare the package for a stable v1.0.0 release. This involves finalizing the API, ensuring documentation is complete, and consolidating any breaking changes.

## Pre-Release Checklist

### 1. Breaking Changes to Consolidate

These should all happen in v1.0.0 to minimize disruption:

- [ ] **Issue 30**: Remove root-level instance commands (require `remote instance` prefix)
- [ ] **Issue 23**: Rename package from `remotepy` to `remote` (optional, evaluate impact)
- [ ] Finalize CLI command structure - no changes after v1.0.0

### 2. API Stability

- [ ] Review all public functions and ensure consistent signatures
- [ ] Document which functions are public API vs internal
- [ ] Add `__all__` exports to all modules
- [ ] Ensure all exceptions are properly exported

### 3. Documentation

- [ ] Complete README with all commands and examples
- [ ] Add CHANGELOG.md with version history
- [ ] Ensure all commands have complete `--help` text
- [ ] Add migration guide from v0.x to v1.0.0

### 4. Testing

- [ ] Ensure 100% test coverage on critical paths
- [ ] Add integration tests for common workflows
- [ ] Test on Python 3.10, 3.11, 3.12
- [ ] Test CLI output formatting in different terminal widths

### 5. Dependencies

- [ ] Pin major versions of dependencies
- [ ] Review and update minimum Python version if needed
- [ ] Audit dependencies for security issues
- [ ] Remove any unused dependencies

### 6. CI/CD

- [ ] Ensure all CI checks pass
- [ ] Set up automated PyPI publishing
- [ ] Add release workflow for GitHub releases
- [ ] Configure dependabot for security updates

### 7. Package Metadata

- [ ] Update version to 1.0.0
- [ ] Review and update pyproject.toml metadata
- [ ] Ensure license is correctly specified
- [ ] Add appropriate classifiers

## Versioning Policy

After v1.0.0:
- **MAJOR** (2.0.0): Breaking changes to CLI or public API
- **MINOR** (1.1.0): New features, non-breaking changes
- **PATCH** (1.0.1): Bug fixes, security patches

## Acceptance Criteria

- [ ] All breaking changes consolidated and documented
- [ ] Complete documentation
- [ ] All tests passing with good coverage
- [ ] Clean CI/CD pipeline
- [ ] Security audit complete
- [ ] CHANGELOG.md created
- [ ] Migration guide written
