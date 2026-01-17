# Remote.py Specs

## Instructions

0. Checkout main
1. Pick an issue from the recommended order below
2. Read the linked spec file for details
3. Checkout a branch a branch
4. Implement the fix
5. Run tests: `uv run pytest`
6. Run type check: `uv run mypy remotepy/`
7. Run linter: `uv run ruff check . && uv run ruff format .`
8. Update spec file status to COMPLETED
9. Commit with descriptive message
10. Push to branch
11. Wait for CI/CD to pass
12. Merge to main
13. Quit

## Recommended Order

Issues should be completed in this order to minimize conflicts and maximize efficiency:

### Phase 1: Critical Bug Fixes
Complete these first - they fix real bugs that affect users.

| Order | ID | Issue | Spec |
|-------|-----|-------|------|
| 1 | 13 | Logic bug in get_instance_by_name() | [issue-13](./issue-13-get-instance-by-name-bug.md) |
| 2 | 14 | SSH subprocess error handling | [issue-14](./issue-14-ssh-error-handling.md) |
| 3 | 15 | Unvalidated array index in AMI launch | [issue-15](./issue-15-ami-array-index.md) |

### Phase 2: Foundation Changes
These establish patterns that other issues will follow.

| Order | ID | Issue | Rationale | Spec |
|-------|-----|-------|-----------|------|
| 4 | 16 | Deprecated datetime API | Simple fix, no dependencies | [issue-16](./issue-16-datetime-deprecation.md) |
| 5 | 18 | Standardize exit patterns | Sets patterns for error handling | [issue-18](./issue-18-exit-patterns.md) |
| 6 | 19 | Function shadows builtin | Simple rename, reduces warnings | [issue-19](./issue-19-list-function-name.md) |

### Phase 3: UI/UX Overhaul
Replace wasabi with rich first, then build on it.

| Order | ID | Issue | Rationale | Spec |
|-------|-----|-------|-----------|------|
| 7 | 21 | Replace wasabi with rich | Enables better UI for all subsequent changes | [issue-21](./issue-21-replace-wasabi-with-rich.md) |
| 8 | 17 | Inconsistent output in config.py | Benefits from rich tables | [issue-17](./issue-17-config-output.md) |

### Phase 4: CLI Structure
Reorganize CLI before adding new commands.

| Order | ID | Issue | Rationale | Spec |
|-------|-----|-------|-----------|------|
| 9 | 29 | Compartmentalize subcommands | Must be done before help improvements | [issue-29](./issue-29-subcommand-structure.md) |
| 10 | 28 | Improve CLI help documentation | Depends on command structure being finalized | [issue-28](./issue-28-cli-help.md) |

### Phase 5: Feature Improvements
New features that depend on foundation work.

| Order | ID | Issue | Rationale | Spec |
|-------|-----|-------|-----------|------|
| 11 | 27 | Improve config workflow | New config commands | [issue-27](./issue-27-config-workflow.md) |
| 12 | 26 | Improve template workflow | New template commands | [issue-26](./issue-26-template-workflow.md) |

### Phase 6: Testing
Can be done in parallel with other work.

| Order | ID | Issue | Rationale | Spec |
|-------|-----|-------|-----------|------|
| -- | 20 | Test coverage edge cases | Independent, can run in parallel | [issue-20](./issue-20-test-coverage.md) |

---

## Issue Index by Priority

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
| 26 | Improve template workflow | [issue-26-template-workflow.md](./issue-26-template-workflow.md) |
| 27 | Improve config workflow | [issue-27-config-workflow.md](./issue-27-config-workflow.md) |
| 28 | Improve CLI help documentation | [issue-28-cli-help.md](./issue-28-cli-help.md) |
| 29 | Compartmentalize subcommands | [issue-29-subcommand-structure.md](./issue-29-subcommand-structure.md) |

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
