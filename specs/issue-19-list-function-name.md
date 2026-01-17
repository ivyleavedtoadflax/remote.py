# Issue 19: Function Name Shadows Builtin

**Status:** Not started
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

- [ ] Rename function to `list_instances`
- [ ] Keep CLI command name as "list"
- [ ] Update any internal references
- [ ] Verify type hints work correctly
