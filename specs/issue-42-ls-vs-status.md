# Issue 42: Clarify instance ls vs status Commands

**Status:** TODO
**Priority:** Low
**Target Version:** v1.2.0
**Files:** `remotepy/instance.py`

## Problem

There is potential overlap between `instance ls` and `instance status` commands. It's unclear if both are needed or if they serve distinct purposes.

## Current Understanding

- **`instance ls`**: Lists all instances (or filtered set) with summary info
- **`instance status`**: Shows status of a specific instance (the configured default or named instance)

## Questions to Resolve

1. What information does each command show?
2. Is there meaningful overlap?
3. Should `status` be a detailed view of a single instance while `ls` is a summary of multiple?
4. Would users benefit from consolidating these, or do they serve distinct workflows?

## Proposed Distinction

**`instance ls`** - List/summary view:
- Shows all instances (or filtered)
- Summary columns: Name, ID, Type, Status, Uptime, (optionally Cost)
- Good for "what instances do I have?"

**`instance status`** - Detail view:
- Shows detailed info about one specific instance
- More fields: IP addresses, security groups, key pair, launch time, tags, etc.
- Good for "tell me everything about this instance"

## Acceptance Criteria

- [ ] Audit current output of both commands
- [ ] Document the distinct purpose of each command
- [ ] Ensure minimal overlap in default output
- [ ] Update help text to clarify when to use each
- [ ] Consider if `status` should show more detail than `ls` (or vice versa)
- [ ] Consolidate if redundant, or differentiate if both are useful
