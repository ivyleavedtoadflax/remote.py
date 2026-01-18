# Issue 42: Clarify instance ls vs status Commands

**Status:** COMPLETED
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

- [x] Audit current output of both commands
- [x] Document the distinct purpose of each command
- [x] Ensure minimal overlap in default output
- [x] Update help text to clarify when to use each
- [x] Consider if `status` should show more detail than `ls` (or vice versa)
- [x] Consolidate if redundant, or differentiate if both are useful

## Implementation Summary

The commands were already serving distinct purposes, but the distinction has been enhanced:

**`instance ls`** - Summary/list view:
- Lists ALL instances in a table format
- Shows: Name, ID, DNS, Status, Type, Launch Time
- Optional `--cost` flag adds: Uptime, $/hr, Estimated Cost
- Use case: "What instances do I have?"

**`instance status`** - Detail view of ONE instance:
- Shows comprehensive details about a specific instance
- Network: Public/Private IP, DNS
- Configuration: Key Pair, Security Groups, Launch Time, AZ
- Health Status (for running instances): System Status, Instance Status, Reachability
- Tags: All tags (except Name)
- Use case: "Tell me everything about this instance"

Help text updated to clearly indicate when to use each command and cross-reference the other command.
