# Issue 29: Compartmentalize CLI into Consistent Subcommands

**Status:** COMPLETED
**Priority:** Medium
**Files:** `remotepy/__main__.py`, `remotepy/instance.py`

## Current Problems

### 1. Inconsistent Command Structure
Instance commands are at the root level while other services require prefixes:

```bash
# Instance commands (no prefix)
remote start
remote stop
remote connect
remote list

# Other services (require prefix)
remote ami create
remote ami list
remote snapshot list
remote volume list
remote ecs scale
```

### 2. Confusing for New Users
Users might expect consistency:
- Why is `remote list` for instances but `remote ami list` for AMIs?
- Why `remote start` but `remote ecs scale`?

### 3. Command Collision Risk
As more features are added, root-level commands could conflict:
- `remote list` - instances
- `remote config show` - config
- What if we add `remote list` for something else?

### 4. Difficult to Discover
Users running `remote --help` see a mix of direct commands and subcommand groups without clear organization.

## Proposed Solution

### Option A: Full Compartmentalization (Breaking Change)

Move all instance commands under `remote instance`:

```bash
# Before
remote start my-server
remote stop my-server
remote connect my-server
remote list

# After
remote instance start my-server
remote instance stop my-server
remote instance connect my-server
remote instance list
```

**Pros:**
- Fully consistent structure
- Clear namespace separation
- Scalable for future services

**Cons:**
- Breaking change for existing users
- More typing for common operations

### Option B: Aliases for Backwards Compatibility (Recommended)

Keep root-level commands but add `instance` prefix as alternative:

```bash
# Both work
remote start my-server          # Short form (default)
remote instance start my-server # Explicit form

remote list                     # Short form
remote instance list            # Explicit form
```

Implementation:

```python
# remotepy/__main__.py
from remotepy.instance import app as instance_app

# Instance commands are the default (short form)
# This preserves backwards compatibility
app = instance_app

# Also register as explicit subcommand
app.add_typer(instance_app, name="instance", help="Manage EC2 instances")
```

Or use command aliases:

```python
# remotepy/instance.py
@app.command("start")
@app.command("instance-start", hidden=True)  # Hidden alias
def start(instance_name: str | None = None) -> None:
    ...
```

### Option C: Progressive Migration

1. Add `instance` prefix as alternative (v0.4.0)
2. Show deprecation warning for root commands (v0.5.0)
3. Remove root commands (v1.0.0)

```python
@app.command()
def start(instance_name: str | None = None) -> None:
    """Start an instance. [Deprecated: use 'remote instance start']"""
    import warnings
    warnings.warn(
        "Direct 'remote start' is deprecated. Use 'remote instance start'",
        DeprecationWarning
    )
    # ... actual implementation
```

## Recommended Implementation (Option B)

### Updated __main__.py

```python
import typer

from remotepy.ami import app as ami_app
from remotepy.config import app as config_app
from remotepy.ecs import app as ecs_app
from remotepy.instance import app as instance_app
from remotepy.snapshot import app as snapshot_app
from remotepy.volume import app as volume_app

# Create main app
app = typer.Typer(
    name="remote",
    help="Remote.py - AWS EC2 instance management CLI",
    no_args_is_help=True,
)

# Instance commands at root level (backwards compatible)
# Copy instance commands to root
for command in instance_app.registered_commands:
    app.command(command.name)(command.callback)

# Register all service subcommands
app.add_typer(instance_app, name="instance", help="Manage EC2 instances")
app.add_typer(ami_app, name="ami", help="Manage Amazon Machine Images")
app.add_typer(config_app, name="config", help="Manage configuration")
app.add_typer(snapshot_app, name="snapshot", help="Manage EBS snapshots")
app.add_typer(volume_app, name="volume", help="Manage EBS volumes")
app.add_typer(ecs_app, name="ecs", help="Manage ECS clusters and services")
```

### Expected Help Output

```
$ remote --help

 Remote.py - AWS EC2 instance management CLI

╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ start        Start an EC2 instance                                           │
│ stop         Stop an EC2 instance                                            │
│ connect      Connect via SSH                                                 │
│ list         List instances                                                  │
│ ...                                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Service Commands ───────────────────────────────────────────────────────────╮
│ instance     Manage EC2 instances                                            │
│ ami          Manage Amazon Machine Images                                    │
│ config       Manage configuration                                            │
│ snapshot     Manage EBS snapshots                                            │
│ volume       Manage EBS volumes                                              │
│ ecs          Manage ECS clusters and services                                │
╰──────────────────────────────────────────────────────────────────────────────╯

$ remote instance --help

 Manage EC2 instances

╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ start        Start an EC2 instance                                           │
│ stop         Stop an EC2 instance                                            │
│ connect      Connect via SSH                                                 │
│ list         List instances                                                  │
│ status       Get instance status                                             │
│ type         View or change instance type                                    │
│ launch       Launch from template                                            │
│ terminate    Terminate an instance                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Migration Path

### Phase 1: v0.4.x (Current)
- Add `instance` subcommand group
- Keep root-level instance commands
- Document both forms in help

### Phase 2: v0.5.x
- Add deprecation warnings to root commands
- Update documentation to prefer `instance` prefix
- Add migration guide

### Phase 3: v1.0.0
- Remove root-level instance commands
- All services use consistent prefix

## Acceptance Criteria

- [ ] Add `remote instance` subcommand group
- [ ] Ensure `remote start` and `remote instance start` both work
- [ ] Add help text for instance subcommand group
- [ ] Update documentation with both command forms
- [ ] Add tests for both command paths
- [ ] Document migration path for future versions
