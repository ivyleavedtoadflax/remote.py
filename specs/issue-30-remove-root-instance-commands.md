# Issue 30: Remove Root-Level Instance Commands (Breaking Change)

**Status:** Not started
**Priority:** Low
**Target Version:** v1.0.0
**Files:** `remotepy/__main__.py`
**Depends On:** Issue 29 (Compartmentalize subcommands)

## Problem

After issue-29, instance commands are available at both the root level and under the `instance` subcommand:

```bash
# Current state - both work (confusing)
remote start my-server          # Root level
remote instance start my-server # Explicit subcommand

remote list                     # Root level
remote instance list            # Explicit subcommand
```

This creates a cluttered and confusing help output:

```
╭─ Commands ──────────────────────────────────────────────────────────────────╮
│ version                 Show version.                                       │
│ list                    List all instances with id, dns and status          │  <- duplicate
│ ls                      List all instances with id, dns and status          │  <- duplicate
│ status                  Get the status of an instance                       │  <- duplicate
│ start                   Start the instance                                  │  <- duplicate
│ stop                    Stop the instance                                   │  <- duplicate
│ connect                 Connect to the instance with ssh                    │  <- duplicate
│ type                                                                        │  <- duplicate
│ list-launch-templates   List all launch templates available...              │  <- duplicate
│ launch                  Launch an AWS EC2 instance...                       │  <- duplicate
│ terminate               Terminate the instance                              │  <- duplicate
│ instance                Manage EC2 instances                                │
│ ami                     Manage Amazon Machine Images                        │
│ config                  Manage configuration                                │
│ snapshot                Manage EBS snapshots                                │
│ volume                  Manage EBS volumes                                  │
│ ecs                     Manage ECS clusters and services                    │
╰─────────────────────────────────────────────────────────────────────────────╯
```

## Proposed Solution

Remove the root-level instance commands, requiring the `instance` prefix:

```bash
# After this change - only explicit subcommand works
remote instance start my-server
remote instance list
remote instance connect my-server
```

### Clean Help Output

```
╭─ Commands ──────────────────────────────────────────────────────────────────╮
│ version     Show version.                                                   │
│ instance    Manage EC2 instances                                            │
│ ami         Manage Amazon Machine Images                                    │
│ config      Manage configuration                                            │
│ snapshot    Manage EBS snapshots                                            │
│ volume      Manage EBS volumes                                              │
│ ecs         Manage ECS clusters and services                                │
╰─────────────────────────────────────────────────────────────────────────────╯
```

## Implementation

### Changes to `__main__.py`

Remove the loop that copies instance commands to root level:

```python
# REMOVE this block:
# Copy instance commands to root level for backwards compatibility
# This allows `remote start`, `remote stop`, etc. to work
for command in instance_app.registered_commands:
    if command.callback is not None:
        app.command(command.name, help=command.callback.__doc__)(command.callback)
```

### Final `__main__.py`

```python
import importlib.metadata

import typer

from remotepy.ami import app as ami_app
from remotepy.config import app as config_app
from remotepy.ecs import app as ecs_app
from remotepy.instance import app as instance_app
from remotepy.snapshot import app as snapshot_app
from remotepy.volume import app as volume_app

app = typer.Typer(
    name="remote",
    help="Remote.py - AWS EC2 instance management CLI",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show version."""
    typer.echo(importlib.metadata.version("remotepy"))


# Register service subcommands (no root-level instance commands)
app.add_typer(instance_app, name="instance", help="Manage EC2 instances")
app.add_typer(ami_app, name="ami", help="Manage Amazon Machine Images")
app.add_typer(config_app, name="config", help="Manage configuration")
app.add_typer(snapshot_app, name="snapshot", help="Manage EBS snapshots")
app.add_typer(volume_app, name="volume", help="Manage EBS volumes")
app.add_typer(ecs_app, name="ecs", help="Manage ECS clusters and services")

if __name__ == "__main__":
    app()
```

## Migration Guide

Users will need to update their scripts and muscle memory:

| Old Command | New Command |
|-------------|-------------|
| `remote start` | `remote instance start` |
| `remote stop` | `remote instance stop` |
| `remote connect` | `remote instance connect` |
| `remote list` | `remote instance list` |
| `remote ls` | `remote instance ls` |
| `remote status` | `remote instance status` |
| `remote type` | `remote instance type` |
| `remote launch` | `remote instance launch` |
| `remote terminate` | `remote instance terminate` |
| `remote list-launch-templates` | `remote instance list-launch-templates` |

## Test Updates

Update tests in `tests/test_main.py`:
- Remove `test_default_instance_commands_work`
- Update `test_both_command_paths_show_same_commands` to only test instance subcommand
- Verify root-level commands no longer exist

## Acceptance Criteria

- [ ] Remove root-level instance command registration from `__main__.py`
- [ ] Update `remote --help` to show clean output without duplicates
- [ ] Update tests to reflect new command structure
- [ ] Add migration note to CHANGELOG
- [ ] Update README with new command syntax
- [ ] Bump major version (breaking change)
