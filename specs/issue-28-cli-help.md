# Issue 28: Improve CLI Help Documentation

**Status:** COMPLETED
**Priority:** Medium
**Files:** `remotepy/__main__.py`, `remotepy/instance.py`, `remotepy/ami.py`, `remotepy/ecs.py`, `remotepy/config.py`, `remotepy/snapshot.py`, `remotepy/volume.py`

## Current Problems

### 1. No App-Level Description
Running `remote --help` shows no description of what the tool does.

```
$ remote --help
Usage: remote [OPTIONS] COMMAND [ARGS]...

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### 2. No Descriptions for Subcommand Groups
The `ami`, `config`, `snapshot`, `volume`, and `ecs` subcommand groups have no descriptions.

```
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ ami                                                                          │
│ config                                                                       │
│ snapshot                                                                     │
│ volume                                                                       │
│ ecs                                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### 3. Empty Command Descriptions
Some commands like `type` have no description at all.

### 4. Inconsistent Help Text
- Some commands have detailed docstrings, others are minimal
- Mixed capitalization and formatting styles
- Some commands don't explain required vs optional arguments

### 5. No Examples in Help
Complex commands like `launch` don't show usage examples.

## Proposed Improvements

### 1. Add App-Level Description and Help Text

```python
# remotepy/__main__.py
app = typer.Typer(
    name="remote",
    help="Remote.py - AWS EC2 instance management CLI",
    epilog="Run 'remote COMMAND --help' for more information on a command.",
    no_args_is_help=True,
)
```

### 2. Add Descriptions to All Subcommand Groups

```python
# remotepy/__main__.py
app.add_typer(
    ami_app,
    name="ami",
    help="Manage Amazon Machine Images (AMIs)"
)
app.add_typer(
    config_app,
    name="config",
    help="Manage remote.py configuration"
)
app.add_typer(
    snapshot_app,
    name="snapshot",
    help="Manage EBS snapshots"
)
app.add_typer(
    volume_app,
    name="volume",
    help="Manage EBS volumes"
)
app.add_typer(
    ecs_app,
    name="ecs",
    help="Manage ECS clusters and services"
)
```

### 3. Improve Command Docstrings

Add consistent, informative docstrings to all commands:

```python
@app.command()
def start(
    instance_name: str | None = typer.Argument(None, help="Instance name (uses default if not specified)"),
) -> None:
    """
    Start an EC2 instance.

    If no instance name is provided, uses the default instance from config.
    The command waits for the instance to reach 'running' state.

    Examples:
        remote start                  # Start default instance
        remote start my-server        # Start specific instance
    """
```

### 4. Add Rich Markup for Examples (if using rich)

```python
@app.command()
def connect(
    instance_name: str | None = typer.Argument(None),
) -> None:
    """
    Connect to an EC2 instance via SSH.

    [bold]Examples:[/bold]
        [dim]$[/dim] remote connect
        [dim]$[/dim] remote connect my-server
        [dim]$[/dim] remote connect my-server -u ec2-user
    """
```

### 5. Standardize Help Format

All command docstrings should follow this pattern:

```
Brief one-line description.

Detailed explanation if needed (optional).

Examples:
    command example 1
    command example 2

Notes:
    Additional information (optional).
```

### 6. Add Missing Descriptions

Fix all commands with missing or empty descriptions:

```python
# remotepy/instance.py
@app.command()
def type(
    instance_name: str | None = typer.Argument(None, help="Instance name"),
    new_type: str | None = typer.Option(None, "--type", "-t", help="New instance type"),
) -> None:
    """
    View or change an instance's type.

    Without --type, displays the current instance type.
    With --type, changes the instance type (instance must be stopped).

    Examples:
        remote type                   # Show default instance type
        remote type my-server         # Show specific instance type
        remote type -t t3.large       # Change default instance type
    """
```

## Expected Output After Changes

```
$ remote --help

 Remote.py - AWS EC2 instance management CLI

 Usage: remote [OPTIONS] COMMAND [ARGS]...

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell.         │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Instance Commands ──────────────────────────────────────────────────────────╮
│ start        Start an EC2 instance                                           │
│ stop         Stop an EC2 instance                                            │
│ connect      Connect to an instance via SSH                                  │
│ list         List all instances                                              │
│ status       Get instance status                                             │
│ type         View or change instance type                                    │
│ launch       Launch a new instance from template                             │
│ terminate    Terminate an instance                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Subcommands ────────────────────────────────────────────────────────────────╮
│ ami          Manage Amazon Machine Images (AMIs)                             │
│ config       Manage remote.py configuration                                  │
│ snapshot     Manage EBS snapshots                                            │
│ volume       Manage EBS volumes                                              │
│ ecs          Manage ECS clusters and services                                │
╰──────────────────────────────────────────────────────────────────────────────╯

 Run 'remote COMMAND --help' for more information on a command.
```

## Acceptance Criteria

- [x] Add app-level description to main Typer app
- [x] Add help text to all subcommand group registrations
- [x] Add/improve descriptions for all commands
- [x] Add examples to complex commands (launch, connect, ami create)
- [x] Standardize docstring format across all commands
- [x] Fix the empty `type` command description
- [x] Add epilog with usage hint
- [x] Test all --help outputs for consistency
