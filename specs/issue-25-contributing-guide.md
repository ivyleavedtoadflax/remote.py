# Issue 25: Contributing Guide

**Status:** Not started
**Priority:** Low (v0.5.0)
**GitHub Issue:** #25 (partial)

## Problem

No contributing guide exists for new contributors. Development setup and contribution workflow are not documented.

## Solution

Create `CONTRIBUTING.md` with clear guidelines.

## Proposed Content

### CONTRIBUTING.md Structure

```markdown
# Contributing to Remote.py

## Development Setup

### Prerequisites
- Python 3.10+
- uv package manager

### Installation
git clone https://github.com/user/remote.py.git
cd remote.py
uv sync --dev

### Running Tests
uv run pytest
uv run pytest --cov  # With coverage

### Code Quality
uv run ruff check .
uv run ruff format .
uv run mypy remotepy/

## Making Changes

### Branch Naming
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation

### Commit Messages
Follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Test changes

### Pull Request Process
1. Create feature branch
2. Make changes
3. Run tests and linting
4. Submit PR with description
5. Address review feedback

## Code Style

- Use type hints for all functions
- Follow existing patterns in codebase
- Add tests for new functionality
- Update documentation as needed

## Testing

- All new features need tests
- Maintain 100% test coverage
- Mock AWS calls - no real credentials needed
```

## Additional Files

### .github/PULL_REQUEST_TEMPLATE.md

```markdown
## Description
<!-- What does this PR do? -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactoring

## Checklist
- [ ] Tests pass (`uv run pytest`)
- [ ] Types check (`uv run mypy remotepy/`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Documentation updated if needed
```

### .github/ISSUE_TEMPLATE/bug_report.md

```markdown
## Bug Description
<!-- Clear description of the bug -->

## Steps to Reproduce
1.
2.
3.

## Expected Behavior
<!-- What should happen -->

## Actual Behavior
<!-- What actually happens -->

## Environment
- OS:
- Python version:
- remote.py version:
```

## Acceptance Criteria

- [ ] Create CONTRIBUTING.md
- [ ] Create PR template
- [ ] Create issue templates (bug, feature)
- [ ] Verify editable install works with uv
- [ ] Add badges to README (tests, coverage, version)
