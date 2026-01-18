# Remote.py Plan

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
| 17 | 33 | v1.0.0 release preparation | Final checklist | [issue-33](./issue-33-v1-release-preparation.md) | COMPLETED |

### Phase 8: Post-v1.0.0 Enhancements
Features and improvements for future releases.

| Order | ID | Issue | Rationale | Spec | Status |
|-------|-----|-------|-----------|------|--------|
| 18 | 35 | Built-in watch mode | Fix garbled output when using `watch` command with Rich | [issue-35](./issue-35-watch-mode.md) | COMPLETED |
| 19 | 36 | Config validate panel too wide | Panel stretches beyond console width; also redundant "All checks passed" and "Status: Valid" | [issue-36](./issue-36-config-validate-output.md) | TODO |
| 20 | 37 | Pricing API region fallback | Pricing API only works in us-east-1; fallback to us-east-1 pricing for other regions | [issue-37](./issue-37-pricing-region-fallback.md) | TODO |
| 21 | 38 | Instance cost command | Add command to show estimated cost of instance based on uptime | [issue-38](./issue-38-instance-cost-command.md) | TODO |
