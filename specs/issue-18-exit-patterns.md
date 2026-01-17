# Issue 18: Standardize Exit Patterns

**Status:** COMPLETED
**Priority:** Medium
**Files:** Multiple files

## Problem

Inconsistent exit handling across the codebase:
- Some places use `typer.Exit()`
- Others use `sys.exit()`
- Some return early without explicit exit

## Solution

Use `raise typer.Exit(code)` consistently throughout all command handlers.

```python
# Preferred pattern
raise typer.Exit(0)  # Success
raise typer.Exit(1)  # Error
```

## Files to Audit

- `remotepy/instance.py`
- `remotepy/ami.py`
- `remotepy/ecs.py`
- `remotepy/snapshot.py`
- `remotepy/volume.py`
- `remotepy/config.py`

## Acceptance Criteria

- [x] Audit all exit points in command handlers
- [x] Replace `sys.exit()` with `raise typer.Exit()`
- [x] Ensure consistent exit codes (0=success, 1=error)
- [x] Update tests if needed
