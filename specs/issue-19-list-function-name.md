# Issue 19: Function Name Shadows Builtin

**Status:** COMPLETED
**Priority:** Low
**File:** `remotepy/instance.py`

## Problem

Function named `list` shadows Python builtin. While it works due to Typer's command registration, it's a code smell and can cause issues with type hints.

## Solution

Rename function internally while keeping CLI command name:

```python
# Before
@app.command()
def list():
    ...

# After
@app.command(name="list")
def list_instances():
    ...
```

## Acceptance Criteria

- [x] Rename function to `list_instances`
- [x] Keep CLI command name as "list"
- [x] Update any internal references
- [x] Verify type hints work correctly
