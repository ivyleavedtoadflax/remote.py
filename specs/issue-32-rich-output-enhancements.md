# Issue 32: Enhance Output with Rich Formatting

**Status:** Not started
**Priority:** Medium
**Target Version:** v1.0.0
**Files:** `remotepy/ecs.py`, `remotepy/config.py`, `remotepy/instance.py`

## Overview

Keep `typer.secho()` for simple messages but enhance specific areas with Rich formatting for better UX. This is not a blanket replacement - just targeted improvements.

## Areas to Enhance

### 1. ECS Cluster/Service Selection (ecs.py)

**Current:** Numbered list with plain text
```
1. arn:aws:ecs:us-east-1:123456789:cluster/prod
2. arn:aws:ecs:us-east-1:123456789:cluster/staging
```

**Proposed:** Rich table with extracted names
```
┏━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Number ┃ Cluster      ┃ ARN                                     ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1      │ prod         │ arn:aws:ecs:us-east-1:123456789:cluster │
│ 2      │ staging      │ arn:aws:ecs:us-east-1:123456789:cluster │
└────────┴──────────────┴─────────────────────────────────────────┘
```

### 2. Config Validation Output (config.py)

**Current:** Sequential error/warning messages
```
ERROR: Invalid instance_name format
WARNING: ssh_key path does not exist
Config has warnings but is usable
```

**Proposed:** Rich panel with grouped output
```
╭─────────────────── Config Validation ───────────────────╮
│ ✗ ERROR: Invalid instance_name format                   │
│ ⚠ WARNING: ssh_key path does not exist                  │
├─────────────────────────────────────────────────────────┤
│ Status: Has warnings but usable                         │
╰─────────────────────────────────────────────────────────╯
```

### 3. Config Show Output (config.py)

**Current:** Raw config file content

**Proposed:** Rich table with key-value pairs
```
╭──────────────────── Configuration ────────────────────╮
│ Key                    │ Value                        │
├────────────────────────┼──────────────────────────────┤
│ default_instance       │ my-server                    │
│ default_launch_template│ web-template                 │
│ ssh_key                │ ~/.ssh/my-key.pem            │
╰────────────────────────┴──────────────────────────────╯
```

### 4. Instance Launch Summary (instance.py, ami.py)

**Current:** Multiple separate messages

**Proposed:** Summary panel after launch
```
╭───────────────── Instance Launched ─────────────────╮
│ Instance ID: i-0123456789abcdef0                    │
│ Name:        my-new-server                          │
│ Template:    web-template                           │
│ Type:        t3.medium                              │
╰─────────────────────────────────────────────────────╯
```

## Acceptance Criteria

- [ ] Add Rich table for ECS cluster selection
- [ ] Add Rich table for ECS service selection
- [ ] Add Rich panel for config validation results
- [ ] Add Rich table for config show command
- [ ] Add Rich panel for instance launch summary
- [ ] Keep typer.secho for simple success/error/info messages
- [ ] Update tests as needed
