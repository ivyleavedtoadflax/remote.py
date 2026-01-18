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
9. Atomic commit with descriptive messages
10. Push to branch
11. Fix any high priority security issues
12. Create a PR
13. Merge to main
14. Quit

## Recommended Order

Issues should be completed in this order to minimize conflicts and maximize efficiency:

### Phase 1: Critical Bug Fixes
Complete these first - they fix real bugs that affect users.

| Order | ID | Issue | Spec | Status |
|-------|-----|-------|------|--------|
| 1 | 13 | Logic bug in get_instance_by_name() | [issue-13](./issue-13-get-instance-by-name-bug.md) | COMPLETED |
| 2 | 14 | SSH subprocess error handling | [issue-14](./issue-14-ssh-error-handling.md) | COMPLETED |
| 3 | 15 | Unvalidated array index in AMI launch | [issue-15](./issue-15-ami-array-index.md) | COMPLETED |

### Phase 2: Foundation Changes
These establish patterns that other issues will follow.

| Order | ID | Issue | Rationale | Spec | Status |
|-------|-----|-------|-----------|------|--------|
| 4 | 16 | Deprecated datetime API | Simple fix, no dependencies | [issue-16](./issue-16-datetime-deprecation.md) | COMPLETED |
| 5 | 18 | Standardize exit patterns | Sets patterns for error handling | [issue-18](./issue-18-exit-patterns.md) | COMPLETED |
| 6 | 19 | Function shadows builtin | Simple rename, reduces warnings | [issue-19](./issue-19-list-function-name.md) | COMPLETED |

### Phase 3: UI/UX Overhaul
Replace wasabi with rich first, then build on it.

| Order | ID | Issue | Rationale | Spec | Status |
|-------|-----|-------|-----------|------|--------|
| 7 | 21 | Replace wasabi with rich | Enables better UI for all subsequent changes | [issue-21](./issue-21-replace-wasabi-with-rich.md) | COMPLETED |
| 8 | 17 | Inconsistent output in config.py | Benefits from rich tables | [issue-17](./issue-17-config-output.md) | COMPLETED |

### Phase 4: CLI Structure
Reorganize CLI before adding new commands.

| Order | ID | Issue | Rationale | Spec | Status |
|-------|-----|-------|-----------|------|--------|
| 9 | 29 | Compartmentalize subcommands | Must be done before help improvements | [issue-29](./issue-29-subcommand-structure.md) | COMPLETED |
| 10 | 28 | Improve CLI help documentation | Depends on command structure being finalized | [issue-28](./issue-28-cli-help.md) | COMPLETED |

### Phase 5: Feature Improvements
New features that depend on foundation work.

| Order | ID | Issue | Rationale | Spec | Status |
|-------|-----|-------|-----------|------|--------|
| 11 | 27 | Improve config workflow | New config commands | [issue-27](./issue-27-config-workflow.md) | COMPLETED |
| 12 | 26 | Improve template workflow | New template commands | [issue-26](./issue-26-template-workflow.md) | COMPLETED |

### Phase 6: Testing
Can be done in parallel with other work.

| Order | ID | Issue | Rationale | Spec | Status |
|-------|-----|-------|-----------|------|--------|
| -- | 20 | Test coverage edge cases | Independent, can run in parallel | [issue-20](./issue-20-test-coverage.md) | COMPLETED |

### Phase 7: v1.0.0 Release
Final polish and release preparation.

| Order | ID | Issue | Rationale | Spec | Status |
|-------|-----|-------|-----------|------|--------|
| 13 | 31 | SSH key config not used by connect | Config should flow to connect | [issue-31](./issue-31-ssh-key-config.md) | COMPLETED |
| 14 | 32 | Rich output enhancements | Better UX for tables and panels | [issue-32](./issue-32-rich-output-enhancements.md) | COMPLETED |
| 15 | 34 | Security review | Required before v1.0.0 | [issue-34](./issue-34-security-review.md) | COMPLETED |
| 16 | 30 | Remove root-level instance commands | Breaking change for v1.0.0 | [issue-30](./issue-30-remove-root-instance-commands.md) | COMPLETED |
| 17 | 33 | v1.0.0 release preparation | Final checklist | [issue-33](./issue-33-v1-release-preparation.md) | Not started |

---

## Issue Index by Priority

### High Priority

| ID | Issue | Spec | Status |
|----|-------|------|--------|
| 13 | Logic bug in get_instance_by_name() | [issue-13-get-instance-by-name-bug.md](./issue-13-get-instance-by-name-bug.md) | COMPLETED |
| 14 | SSH subprocess error handling | [issue-14-ssh-error-handling.md](./issue-14-ssh-error-handling.md) | COMPLETED |
| 15 | Unvalidated array index in AMI launch | [issue-15-ami-array-index.md](./issue-15-ami-array-index.md) | COMPLETED |
| 33 | v1.0.0 release preparation | [issue-33-v1-release-preparation.md](./issue-33-v1-release-preparation.md) | Not started |
| 34 | Security review | [issue-34-security-review.md](./issue-34-security-review.md) | COMPLETED |

### Medium Priority

| ID | Issue | Spec | Status |
|----|-------|------|--------|
| 16 | Deprecated datetime API | [issue-16-datetime-deprecation.md](./issue-16-datetime-deprecation.md) | COMPLETED |
| 17 | Inconsistent output in config.py | [issue-17-config-output.md](./issue-17-config-output.md) | COMPLETED |
| 18 | Standardize exit patterns | [issue-18-exit-patterns.md](./issue-18-exit-patterns.md) | COMPLETED |
| 21 | Replace wasabi with rich | [issue-21-replace-wasabi-with-rich.md](./issue-21-replace-wasabi-with-rich.md) | COMPLETED |
| 26 | Improve template workflow | [issue-26-template-workflow.md](./issue-26-template-workflow.md) | COMPLETED |
| 27 | Improve config workflow | [issue-27-config-workflow.md](./issue-27-config-workflow.md) | COMPLETED |
| 28 | Improve CLI help documentation | [issue-28-cli-help.md](./issue-28-cli-help.md) | COMPLETED |
| 29 | Compartmentalize subcommands | [issue-29-subcommand-structure.md](./issue-29-subcommand-structure.md) | COMPLETED |
| 31 | SSH key config not used by connect | [issue-31-ssh-key-config.md](./issue-31-ssh-key-config.md) | COMPLETED |
| 32 | Rich output enhancements | [issue-32-rich-output-enhancements.md](./issue-32-rich-output-enhancements.md) | COMPLETED |

### Low Priority

| ID | Issue | Spec | Status |
|----|-------|------|--------|
| 19 | Function shadows builtin | [issue-19-list-function-name.md](./issue-19-list-function-name.md) | COMPLETED |
| 20 | Test coverage edge cases | [issue-20-test-coverage.md](./issue-20-test-coverage.md) | COMPLETED |
| 22 | Add instance pricing | [issue-22-instance-pricing.md](./issue-22-instance-pricing.md) | COMPLETED |
| 23 | Rename package to `remote` | [issue-23-rename-package.md](./issue-23-rename-package.md) | Not started |
| 24 | Pydantic config validation | [issue-24-pydantic-config.md](./issue-24-pydantic-config.md) | Not started |
| 25 | Contributing guide | [issue-25-contributing-guide.md](./issue-25-contributing-guide.md) | COMPLETED |
| 30 | Remove root-level instance commands | [issue-30-remove-root-instance-commands.md](./issue-30-remove-root-instance-commands.md) | COMPLETED |
