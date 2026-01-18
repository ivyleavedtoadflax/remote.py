# Issue 43: Fix Rich Panel Width Globally

**Status:** COMPLETED
**Priority:** Medium
**Target Version:** v1.2.0
**Files:** Multiple files in `remotepy/`

## Problem

Rich Panels are expanding to fill the entire terminal width instead of fitting their content. This has been a recurring issue:

- Issue 36: `config validate` panel too wide (fixed)
- Issue 41: `instance cost` panel too wide
- Now: `instance status` panel too wide

Example from `remote instance status`:
```
╭────────────────────────────────────────────────────────────────────────────────────────── Instance Details ──────────────────────────────────────────────────────────────────────────────────────────╮
│ Instance ID:    i-0da650323b6167dbc                                                                                                                                                                  │
│ Name:           remote-py-test                                                                                                                                                                       │
...
```

The panel stretches across the full terminal (~200 chars) when content only needs ~60 chars.

## Root Cause

Rich's `Panel` class has `expand=True` by default, which causes it to fill the available terminal width. Each fix has addressed individual panels but the pattern keeps recurring.

## Solution

1. **Audit all Panel usage** across the codebase
2. **Set `expand=False`** on all Panels (or set a reasonable `width` parameter)
3. **Consider creating a helper** to ensure consistent Panel styling

## Locations to Check

Search for all `Panel(` usage in the codebase:

- `instance.py` - status command
- `config.py` - show, validate commands
- `ecs.py` - any panel output
- `ami.py` - any panel output
- Any other files using Rich Panel

## Fix Pattern

```python
# Before (bad - expands to terminal width)
Panel(content, title="Instance Details")

# After (good - fits content)
Panel(content, title="Instance Details", expand=False)
```

## Optional: Central Helper

Consider adding to `utils.py`:

```python
from rich.panel import Panel

def create_panel(content: str, title: str, **kwargs) -> Panel:
    """Create a Panel with consistent styling (non-expanding by default)."""
    return Panel(content, title=title, expand=False, **kwargs)
```

## Acceptance Criteria

- [x] Audit all `Panel(` usage in codebase
- [x] Fix all panels to use `expand=False` or appropriate width
- [x] Verify `instance status` panel fits content
- [x] Verify no other panels are overly wide
- [x] Add tests to verify panel width behavior
- [x] Consider helper function for consistent Panel creation (not needed for 4 usages)

## Testing

- Visual inspection of all commands that output panels
- Automated tests could check that panel output doesn't exceed reasonable width
