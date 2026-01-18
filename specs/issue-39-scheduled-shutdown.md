# Issue 39: Scheduled Instance Shutdown

**Status:** TODO
**Priority:** Medium
**Target Version:** v1.2.0
**Files:** `remotepy/instance.py`, `remotepy/utils.py`

## Problem

Users often want to start an instance for a limited time (e.g., running a training job, testing something) and forget to stop it, leading to unnecessary AWS charges. There's no way to schedule an automatic shutdown when starting or while an instance is running.

## Solution

Add a scheduled shutdown feature that allows users to specify when an instance should automatically stop:

1. `remote instance stop --in 3h` - Stop the instance in 3 hours
2. `remote instance stop --in 30m` - Stop the instance in 30 minutes
3. `remote instance stop --in 1h30m` - Stop in 1 hour 30 minutes
4. `remote instance start --stop-in 2h` - Start now, automatically stop in 2 hours

The feature should:
- Parse human-readable duration strings (e.g., "3h", "30m", "1h30m")
- Show confirmation of when the instance will stop
- Optionally show a countdown or scheduled time in `remote status`

## Proposed Implementation

### Approach: Background Process with `at` or Python Scheduler

Use a lightweight background approach:

```python
@instance_app.command()
def stop(
    name: Annotated[str | None, typer.Argument(help="Instance name")] = None,
    in_duration: Annotated[str | None, typer.Option("--in", help="Stop after duration (e.g., 3h, 30m)")] = None,
) -> None:
    """Stop an EC2 instance."""
    if in_duration:
        _schedule_stop(name, in_duration)
    else:
        _stop_instance(name)
```

### Duration Parsing

```python
import re
from datetime import timedelta

def parse_duration(duration_str: str) -> timedelta:
    """Parse duration string like '3h', '30m', '1h30m' into timedelta."""
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?'
    match = re.fullmatch(pattern, duration_str.strip().lower())

    if not match or not any(match.groups()):
        raise ValueError(f"Invalid duration format: {duration_str}")

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)

    return timedelta(hours=hours, minutes=minutes)
```

### Scheduling Options

**Option A: Subprocess with sleep (simple)**
```python
def _schedule_stop(name: str | None, duration: str) -> None:
    """Schedule instance stop after duration."""
    delta = parse_duration(duration)
    seconds = int(delta.total_seconds())
    instance_id = get_instance_id(name)

    # Spawn detached background process
    subprocess.Popen(
        ["sh", "-c", f"sleep {seconds} && remote instance stop {instance_id}"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
```

**Option B: AWS EventBridge (more robust)**
```python
def _schedule_stop_eventbridge(instance_id: str, duration: str) -> None:
    """Use EventBridge to schedule stop."""
    # Create one-time scheduled rule that triggers Lambda/SSM to stop instance
```

## Alternative Approaches Considered

1. **AWS EventBridge Scheduler** - More robust, survives machine shutdown, but adds AWS dependency complexity
2. **System `at` command** - Unix-specific, requires atd daemon
3. **Detached subprocess with sleep** - Simple, portable, but lost if machine restarts
4. **Separate daemon process** - Overkill for simple use case

Recommend starting with Option A (subprocess) for simplicity, with potential future enhancement to EventBridge.

## CLI Examples

```bash
# Schedule stop for running instance
$ remote instance stop --in 3h
Instance 'dev-box' will stop in 3 hours (at 17:30 UTC)

# Start with auto-stop
$ remote instance start --stop-in 2h
Starting instance 'dev-box'...
Instance will automatically stop in 2 hours (at 14:00 UTC)

# Check status shows scheduled stop
$ remote status
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Name           ┃ Status    ┃ Scheduled Stop    ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ dev-box        │ running   │ in 2h 45m         │
└────────────────┴───────────┴───────────────────┘
```

## Acceptance Criteria

- [ ] Add `--in` option to `remote instance stop` command
- [ ] Add `--stop-in` option to `remote instance start` command
- [ ] Implement duration string parsing (h, m, hm formats)
- [ ] Implement background scheduling mechanism
- [ ] Show confirmation message with calculated stop time
- [ ] Add `--cancel` flag to cancel scheduled stop
- [ ] Add tests for duration parsing
- [ ] Add tests for scheduling logic
- [ ] Update CLI help documentation

## Testing Notes

- Duration parsing should be thoroughly tested with property-based testing
- Background process spawning can be tested with mocking
- Integration tests should verify the scheduled stop works end-to-end

## Future Enhancements

- Show scheduled stop time in `remote status` output
- Persist scheduled stops to survive CLI restarts (file-based or EventBridge)
- Add `remote instance scheduled` command to list all scheduled operations
