# Issue 40: Standardize Console Output Styles

**Status:** COMPLETED
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

- [x] Document the target output style based on `config show`
- [x] Audit all commands for style inconsistencies
- [x] Update inconsistent outputs to match target style
- [x] Add tests to verify output formatting
- [x] Update any relevant documentation

## Changes Made

1. **ECS `list_clusters`**: Changed from simple `typer.secho` line-by-line output to Rich Table with columns for cluster name and ARN
2. **ECS `list_services`**: Changed from simple `typer.secho` line-by-line output to Rich Table with columns for service name and ARN
3. **ECS `prompt_for_cluster_name`**: Changed `typer.echo` to `typer.secho` with yellow color for consistency
4. **ECS `prompt_for_services_name`**: Changed `typer.echo` to `typer.secho` with yellow color for consistency

All list commands now use Rich Tables consistently with:
- Title describing the content
- Consistent column styling (cyan for names, dim for ARNs, green for IDs)
- Status-based coloring for state columns
