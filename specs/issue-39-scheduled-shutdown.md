# Issue 39: Scheduled Instance Shutdown

**Status:** COMPLETED
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

### Approach: Remote `shutdown` Command via SSH

Send the Linux `shutdown` command directly to the instance. This is the simplest and most reliable approach:

- Runs on the instance itself, so it survives if the local machine disconnects
- Uses standard Linux functionality (`shutdown -h +N`)
- Instance handles its own shutdown timing
- Works even if the user closes their terminal

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

def parse_duration_to_minutes(duration_str: str) -> int:
    """Parse duration string like '3h', '30m', '1h30m' into minutes."""
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?'
    match = re.fullmatch(pattern, duration_str.strip().lower())

    if not match or not any(match.groups()):
        raise ValueError(f"Invalid duration format: {duration_str}")

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)

    return hours * 60 + minutes
```

### Scheduling via SSH

```python
def _schedule_stop(name: str | None, duration: str) -> None:
    """Schedule instance shutdown via SSH."""
    minutes = parse_duration_to_minutes(duration)
    instance = get_instance(name)

    # SSH to instance and schedule shutdown
    # shutdown -h +N schedules halt in N minutes
    ssh_command = f"sudo shutdown -h +{minutes}"

    run_ssh_command(instance, ssh_command)

    console.print(f"Instance '{name}' will shut down in {duration}")
```

### Cancelling Scheduled Shutdown

```python
def _cancel_scheduled_stop(name: str | None) -> None:
    """Cancel a scheduled shutdown via SSH."""
    instance = get_instance(name)

    run_ssh_command(instance, "sudo shutdown -c")

    console.print(f"Cancelled scheduled shutdown for '{name}'")
```

## Alternative Approaches Considered

1. **Detached local subprocess with sleep** - Lost if local machine disconnects or restarts
2. **AWS EventBridge Scheduler** - More complex, requires additional AWS permissions and Lambda/SSM setup
3. **System `at` command on instance** - Works, but `shutdown` is simpler and purpose-built
4. **Remote `shutdown` command** - **Chosen**: Simple, reliable, runs on instance itself

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

- [x] Add `--in` option to `remote instance stop` command
- [x] Add `--stop-in` option to `remote instance start` command
- [x] Implement duration string parsing (h, m, hm formats)
- [x] Implement SSH command to run `shutdown -h +N` on instance
- [x] Show confirmation message with calculated stop time
- [x] Add `--cancel` flag to cancel scheduled stop (runs `shutdown -c`)
- [x] Add tests for duration parsing
- [x] Add tests for SSH command generation
- [x] Update CLI help documentation

## Testing Notes

- Duration parsing should be thoroughly tested with property-based testing
- SSH command execution can be tested with mocking
- Ensure proper handling when instance is not reachable via SSH

## Notes

- Requires SSH access to the instance
- Instance must be configured to stop (not terminate) on OS shutdown
- The `shutdown` command is standard on Linux; may need adjustment for Windows instances
