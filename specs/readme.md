# Remote.py Specs

## Instructions

1. Pick an issue from the list below
2. Read the linked spec file for details
3. Implement the fix
4. Run tests: `uv run pytest`
5. Run type check: `uv run mypy remotepy/`
6. Run linter: `uv run ruff check . && uv run ruff format .`
7. Commit with descriptive message
8. Push to branch
9. Update spec file status to COMPLETED

## Issue Index

### High Priority

| ID | Issue | Spec |
|----|-------|------|
| 13 | Logic bug in get_instance_by_name() | [issue-13-get-instance-by-name-bug.md](./issue-13-get-instance-by-name-bug.md) |
| 14 | SSH subprocess error handling | [issue-14-ssh-error-handling.md](./issue-14-ssh-error-handling.md) |
| 15 | Unvalidated array index in AMI launch | [issue-15-ami-array-index.md](./issue-15-ami-array-index.md) |

### Medium Priority

| ID | Issue | Spec |
|----|-------|------|
| 16 | Deprecated datetime API | [issue-16-datetime-deprecation.md](./issue-16-datetime-deprecation.md) |
| 17 | Inconsistent output in config.py | [issue-17-config-output.md](./issue-17-config-output.md) |
| 18 | Standardize exit patterns | [issue-18-exit-patterns.md](./issue-18-exit-patterns.md) |
| 21 | Replace wasabi with rich | [issue-21-replace-wasabi-with-rich.md](./issue-21-replace-wasabi-with-rich.md) |

### Low Priority

| ID | Issue | Spec |
|----|-------|------|
| 19 | Function shadows builtin | [issue-19-list-function-name.md](./issue-19-list-function-name.md) |
| 20 | Test coverage edge cases | [issue-20-test-coverage.md](./issue-20-test-coverage.md) |

### Future (v0.5.0+)

| ID | Issue | Spec |
|----|-------|------|
| 22 | Add instance pricing | [issue-22-instance-pricing.md](./issue-22-instance-pricing.md) |
| 23 | Rename package to `remote` | [issue-23-rename-package.md](./issue-23-rename-package.md) |
| 24 | Pydantic config validation | [issue-24-pydantic-config.md](./issue-24-pydantic-config.md) |
| 25 | Contributing guide | [issue-25-contributing-guide.md](./issue-25-contributing-guide.md) |
