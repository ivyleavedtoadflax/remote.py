# Issue 45: v1.1.0 Release Preparation

**Status:** TODO
**Priority:** High
**Target Version:** v1.1.0

## Overview

Prepare the package for v1.1.0 release. This is a minor release with new features and bug fixes.

## Features Included in v1.1.0

### New Features
- **Issue 35**: Built-in watch mode (`--watch` flag for status command)
- **Issue 39**: Scheduled instance shutdown (`--in` flag for stop, `--stop-in` for start)
- **Issue 40**: Standardized console output styles

### Bug Fixes
- **Issue 41**: Fixed instance cost display (EU region location names)
- **Issue 43**: Fixed Rich Panel width (pending)

### Improvements
- **Issue 42**: Clarified `instance ls` vs `instance status` purposes

## Pre-Release Checklist

### 1. Code Complete
- [ ] Issue 43 (Panel width fix) completed
- [ ] All tests passing
- [ ] No known critical bugs

### 2. Documentation
- [ ] Update CHANGELOG.md with v1.1.0 changes
- [ ] Review and update README if needed
- [ ] Ensure new commands have complete `--help` text
- [ ] Document new `--watch`, `--in`, `--stop-in`, `--cost` flags

### 3. Testing
- [ ] Run full test suite
- [ ] Manual testing of new features:
  - [ ] `remote instance status --watch`
  - [ ] `remote instance stop --in 1h`
  - [ ] `remote instance start --stop-in 2h`
  - [ ] `remote instance ls --cost`
- [ ] Verify pricing works in EU regions
- [ ] Test Panel widths don't exceed terminal

### 4. Version Bump
- [ ] Update version in `pyproject.toml` to 1.1.0
- [ ] Create git tag `v1.1.0`
- [ ] Create GitHub release with changelog

### 5. CHANGELOG Entry

```markdown
## [1.1.0] - YYYY-MM-DD

### Added
- Built-in watch mode for status command (`--watch` / `-w` flag)
- Scheduled instance shutdown (`remote instance stop --in 3h`)
- Auto-stop on start (`remote instance start --stop-in 2h`)
- Cost information in instance list (`--cost` / `-c` flag)

### Fixed
- Fixed pricing lookup for EU regions (incorrect location names)
- Fixed Rich Panel expanding to full terminal width

### Changed
- Standardized console output styles across all commands
- Clarified distinction between `instance ls` and `instance status`
```

## Acceptance Criteria

- [ ] All included issues completed
- [ ] CHANGELOG.md updated
- [ ] Version bumped to 1.1.0
- [ ] All tests passing
- [ ] Manual testing completed
- [ ] Git tag created
- [ ] GitHub release published
