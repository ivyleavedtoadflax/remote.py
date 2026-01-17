# Issue 26: Improve Launch Template Workflow

**Status:** COMPLETED
**Priority:** Medium
**Files:** `remotepy/ami.py`, `remotepy/instance.py`, `remotepy/config.py`

## Current Problems

### 1. Duplicate Code
`list_launch_templates()` is duplicated in both `ami.py` and `instance.py`.

### 2. No Default Template
Users must specify or interactively select a template every time they launch.

### 3. Limited Template Information
Current listing only shows:
- LaunchTemplateId
- LaunchTemplateName
- LatestVersionNumber

Missing useful info:
- Instance type
- AMI ID
- Key pair name
- Security groups

### 4. Clunky Interactive Selection
Current flow:
```
$ remote ami launch
Please specify a launch template
Available launch templates:
Number  LaunchTemplateId  LaunchTemplateName  Version
1       lt-abc123         web-server          3
2       lt-def456         db-server           1
Select a launch template by number: _
```

### 5. No Filtering
Can't filter templates by name pattern.

### 6. No Version Management
Can't view version history or see what changed.

## Proposed Improvements

### 1. Move to utils.py (DRY)

```python
# remotepy/utils.py
def get_launch_templates(name_filter: str | None = None) -> list[dict]:
    """Get launch templates, optionally filtered by name pattern."""
    templates = get_ec2_client().describe_launch_templates()["LaunchTemplates"]
    if name_filter:
        templates = [t for t in templates if name_filter.lower() in t["LaunchTemplateName"].lower()]
    return templates
```

### 2. Add Default Template to Config

```ini
# ~/.config/remote.py/config.ini
[DEFAULT]
instance_name = my-dev-server
default_launch_template = web-server
```

```python
# remotepy/ami.py
@app.command()
def launch(
    launch_template: str | None = typer.Option(None, help="Launch template (uses default if not specified)"),
):
    if not launch_template:
        launch_template = config_manager.get_default_template()
    if not launch_template:
        # Fall back to interactive selection
        ...
```

### 3. Enhanced Template Listing

```python
@app.command("list-templates")
def list_templates(
    filter: str | None = typer.Option(None, "-f", "--filter", help="Filter by name"),
    details: bool = typer.Option(False, "-d", "--details", help="Show template details"),
):
    """List launch templates with optional filtering and details."""
```

Output with `--details`:
```
Name: web-server (lt-abc123)
Version: 3 (Latest)
Instance Type: t3.micro
AMI: ami-0123456789abcdef0
Key Pair: my-key
Security Groups: sg-web, sg-default
Created: 2024-01-15

Name: db-server (lt-def456)
...
```

### 4. Better Interactive Selection

Use numbered menu with arrow key selection (if rich is adopted):

```python
from rich.prompt import Prompt

templates = get_launch_templates()
choices = [f"{t['LaunchTemplateName']} ({t['LaunchTemplateId']})" for t in templates]
selected = Prompt.ask("Select template", choices=choices)
```

Or simpler approach with fuzzy matching:
```
$ remote ami launch
Template (tab to autocomplete): web<TAB>
Template: web-server
```

### 5. Template Version Commands

```bash
# List versions
$ remote ami template-versions web-server
Version  Created     Description
3        2024-01-15  Added monitoring
2        2024-01-10  Updated AMI
1        2024-01-01  Initial version

# Show version diff (future)
$ remote ami template-diff web-server 2 3
```

### 6. Set Default Template Command

```bash
$ remote config set-template web-server
Default launch template set to: web-server

$ remote ami launch
Using default template: web-server
Instance name [web-server-a1b2c3]: _
```

## New Commands Summary

| Command | Description |
|---------|-------------|
| `remote ami list-templates` | List templates (with filter/details options) |
| `remote ami template-versions <name>` | Show version history |
| `remote ami template-info <name>` | Show detailed template info |
| `remote config set-template <name>` | Set default template |

## Acceptance Criteria

- [x] Move `list_launch_templates()` to utils.py (remove duplication)
- [x] Add `default_launch_template` config option
- [x] Add `--filter` option to template listing
- [x] Add `--details` option to show instance type, AMI, etc.
- [x] Add `template-versions` command
- [x] Add `template-info` command
- [x] Add `config set-template` command (via generic `config set default_launch_template <name>`)
- [x] Update launch to use default template if configured
- [x] Add tests for new functionality
