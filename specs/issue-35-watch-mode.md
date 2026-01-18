# Issue 35: Add Built-in Watch Mode

**Status:** COMPLETED
**Priority:** Medium
**Target Version:** v1.1.0
**Files:** `remotepy/__main__.py`, `remotepy/instance.py`

## Problem

Using `watch remote status` produces garbled output with visible ANSI escape codes:

```
^[3m                                            Instance Status                                            ^[0m
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃^[1m ^[0m^[1mName          ^[0m^[1m ^[0m┃^[1m ^[0m^[1mInstanceId         ^[0m...
```

This happens because Rich outputs ANSI escape codes for colors and formatting, but when piped through `watch`, the terminal doesn't properly interpret these codes. While `watch --color` can help in some cases, it doesn't fully resolve the issue with Rich's advanced formatting.

## Solution

Add a built-in `--watch` / `-w` flag to commands that benefit from continuous monitoring:

1. `remote status --watch` - Monitor instance status
2. `remote ecs status --watch` - Monitor ECS service status (future)

The watch mode should:
- Clear the screen and redraw on each refresh
- Handle Rich output properly within the same terminal session
- Support configurable refresh interval via `--interval` / `-i` flag (default: 2 seconds)
- Support graceful exit via Ctrl+C

## Proposed Implementation

### CLI Changes

```python
@instance_app.command()
def status(
    name: Annotated[str | None, typer.Argument(help="Instance name")] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Watch mode - refresh continuously")] = False,
    interval: Annotated[int, typer.Option("--interval", "-i", help="Refresh interval in seconds")] = 2,
) -> None:
    """Get the status of an EC2 instance."""
    if watch:
        _watch_status(name, interval)
    else:
        _get_status(name)
```

### Watch Implementation

```python
import time
from rich.live import Live
from rich.console import Console

def _watch_status(name: str | None, interval: int) -> None:
    """Watch instance status with live updates."""
    console = Console()

    try:
        with Live(console=console, refresh_per_second=1/interval, screen=True) as live:
            while True:
                table = _build_status_table(name)
                live.update(table)
                time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\nWatch mode stopped.")
```

## Alternative Approaches Considered

1. **Detect piped output and disable colors** - Would work for `watch` but loses the formatting benefits
2. **Document using `watch --color`** - Doesn't fully solve Rich's advanced formatting issues
3. **Use Rich's Live display** - Chosen approach, provides best UX

## Acceptance Criteria

- [x] Add `--watch` / `-w` flag to `remote status` command
- [x] Add `--interval` / `-i` flag with default of 2 seconds
- [x] Use Rich's Live display for smooth updates
- [x] Handle Ctrl+C gracefully
- [x] Add tests for watch mode functionality
- [x] Update CLI help documentation

## Testing Notes

Watch mode is inherently interactive, so tests should:
- Mock the time.sleep to avoid slow tests
- Test that the watch loop can be interrupted
- Test that status table is built correctly
- Test interval validation (positive integers only)
