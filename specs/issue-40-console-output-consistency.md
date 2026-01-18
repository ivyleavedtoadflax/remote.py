# Issue 40: Standardize Console Output Styles

**Status:** TODO
**Priority:** Low
**Target Version:** v1.2.0
**Files:** Multiple files in `remotepy/`

## Problem

Console output styles are inconsistent across commands. For example, `remote config show` and `remote config validate` use different formatting approaches.

## Solution

Audit all console output across the codebase and standardize around the style used by `remote config show`.

## Scope

Review and align output for:
- `config show` (reference style)
- `config validate`
- `instance status` / `instance list`
- `instance start` / `instance stop`
- `ami list` / `ami create`
- `ecs status` / `ecs scale`
- `volume list`
- `snapshot list` / `snapshot create`
- `template list` / `template show`
- Error messages and success confirmations

## Acceptance Criteria

- [ ] Document the target output style based on `config show`
- [ ] Audit all commands for style inconsistencies
- [ ] Update inconsistent outputs to match target style
- [ ] Add tests to verify output formatting
- [ ] Update any relevant documentation
