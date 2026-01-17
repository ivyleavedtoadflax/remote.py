# Issue 21: Replace wasabi with rich

**Status:** Not started
**Priority:** Medium
**Files:** Multiple files using wasabi

## Problem

The codebase currently uses `wasabi` for table formatting and colored output. While functional, `rich` provides:
- Better table formatting with borders, alignment options
- More consistent styling
- Better maintained and more widely used
- Native support for progress bars, panels, and other UI elements

## Current Usage

```python
import wasabi
msg = wasabi.Printer()
# Table formatting
table_data = [...]
print(wasabi.table(table_data, header=header, divider=True, aligns=aligns))
```

## Solution

Replace with `rich`:

```python
from rich.console import Console
from rich.table import Table

console = Console()

table = Table(title="Instances")
table.add_column("Name", style="cyan")
table.add_column("InstanceId", style="green")
table.add_column("Status")
table.add_column("Type")
table.add_column("DNS")
table.add_column("Launch Time")

for row in data:
    table.add_row(*row)

console.print(table)
```

## Files to Update

- `remotepy/utils.py` - Remove wasabi import, add rich
- `remotepy/instance.py` - Update table formatting in `list` command
- `remotepy/ami.py` - Update table formatting in `list` and `list-launch-templates`
- `remotepy/volume.py` - Update table formatting
- `remotepy/snapshot.py` - Update table formatting
- `pyproject.toml` - Replace wasabi dependency with rich

## Table Styling Guidelines

- Use borders for better readability
- Color code status columns (green=running, red=stopped, yellow=pending)
- Right-align numeric columns
- Truncate long DNS names with ellipsis if needed

## Acceptance Criteria

- [ ] Remove wasabi dependency from pyproject.toml
- [ ] Add rich dependency
- [ ] Update all table formatting to use rich.Table
- [ ] Add status color coding (running=green, stopped=red, etc.)
- [ ] Ensure all existing tests pass
- [ ] Update any tests that check table output format
