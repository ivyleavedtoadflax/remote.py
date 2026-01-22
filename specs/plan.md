# Remote.py Release Plan

This document outlines the planned releases to address open GitHub issues, prioritizing duplication reduction and user experience improvements.

## Open Issues

| ID | Issue | Priority | Status |
|----|-------|----------|--------|

## Completed Issues

| ID | Issue | Priority | Status |
|----|-------|----------|--------|
| [#296](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/296) | Add IP whitelisting for instance security groups on connect | High | COMPLETED |
| [#182](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/182) | Duplicate SSH key fallback logic in instance.py | Low | COMPLETED |
| [#220](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/220) | Duplicate SSH configuration retrieval calls | Medium | COMPLETED |
| [#191](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/191) | Consolidate hardcoded SSH default username to settings constant | Low | COMPLETED |
| [#193](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/193) | Consolidate SSH timeout magic numbers to constants | Low | COMPLETED |
| [#253](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/253) | Subprocess timeout inconsistency in instance.py SSH operations | Medium | COMPLETED |
| [#214](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/214) | Simplify dual configuration access pattern in config.py | Medium | COMPLETED |
| [#243](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/243) | Duplicate config key validation blocks in config.py | Low | COMPLETED |
| [#245](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/245) | Module-level helper functions in config.py could be ConfigManager methods | Low | COMPLETED |
| [#248](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/248) | Duplicate instance name validation in config.py and validation.py | Low | COMPLETED |
| [#189](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/189) | Resolve circular import pattern between config and utils modules | Medium | COMPLETED |
| [#239](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/239) | Duplicated user selection/prompt logic in ECS module | Medium | COMPLETED |
| [#252](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/252) | Private ARN extraction function in ecs.py should be shared utility | Low | COMPLETED |
| [#211](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/211) | Move timing constants from instance.py to settings.py | Low | COMPLETED |
| [#200](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/200) | Hard-coded AWS region to location mapping in pricing.py | Medium | COMPLETED |
| [#225](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/225) | Hardcoded console width in utils.py | Low | COMPLETED |
| [#199](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/199) | Inconsistent output methods: mixing console.print() and typer.secho() | Medium | COMPLETED |
| [#221](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/221) | Inconsistent table output styling across commands | Medium | COMPLETED |
| [#223](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/223) | Pricing module falls back silently without user notification | Medium | COMPLETED |
| [#263](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/263) | instance exec parses command as instance name when no instance specified | Medium | COMPLETED |
| [#286](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/286) | Simplify test suite by consolidating redundant tests | Medium | COMPLETED |
| [#183](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/183) | Ambiguous return type in is_instance_running() - returns bool \| None | Medium | COMPLETED |
| [#184](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/184) | Ambiguous return type in _build_status_table() - returns Panel \| str | Low | COMPLETED |
| [#231](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/231) | Ambiguous API contract in safe_get_array_item() | Low | COMPLETED |
| [#250](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/250) | Missing instance type format validation in type change command | Medium | CLOSED (duplicate of #192) |
| [#222](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/222) | Missing test coverage for edge cases and error paths | Medium | CLOSED (duplicate of #213) |
| [#180](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/180) | Inconsistent command naming: plain 'ls' vs 'ls-*' patterns | Low | CLOSED (by design) |
| [#237](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/237) | Inconsistent optional parameter handling across CLI commands | Medium | COMPLETED |
| [#238](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/238) | Inconsistent AWS response validation across API calls | Medium | COMPLETED |
| [#244](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/244) | Inconsistent resolve_instance vs resolve_instance_or_exit usage | Low | COMPLETED |
| [#251](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/251) | Mixed pathlib.Path and os.path usage in config module | Low | COMPLETED |
| [#254](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/254) | Inconsistent leading/trailing whitespace validation across inputs | Low | COMPLETED |
| [#224](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/224) | Unused exception fields in MultipleInstancesFoundError | Low | COMPLETED |
| [#236](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/236) | Unused TYPE_CHECKING imports in utils.py and ecs.py | Low | CLOSED (already resolved) |
| [#249](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/249) | Redundant str() conversions on values already strings from AWS API | Low | COMPLETED |
| [#165](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/165) | Add exception handling for resolve_instance in create command | Medium | CLOSED (already resolved) |
| [#192](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/192) | Add validation for instance type format in type change command | Medium | COMPLETED |
| [#201](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/201) | Complex argument fallback logic in exec_command is non-intuitive | Medium | COMPLETED |
| [#203](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/203) | No validation for concurrent shutdown operations | Low | COMPLETED |
| [#209](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/209) | Standardize validation result handling patterns | Medium | COMPLETED |
| [#233](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/233) | Missing validation for SSH key path before connect/exec commands | Medium | COMPLETED |
| [#259](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/259) | Missing pagination in list_amis() could fail with large AMI counts | Medium | COMPLETED |
| [#266](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/266) | Fix ConfigManager test isolation - tests read real config instead of mocked values | Medium | COMPLETED |
| [#202](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/202) | Test coverage gap: Private functions in instance.py not tested in isolation | Medium | COMPLETED |
| [#213](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/213) | Add comprehensive tests for edge cases and error paths | Medium | COMPLETED |
| [#255](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/255) | Missing test coverage for uncovered code paths | Medium | COMPLETED |
| [#265](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/265) | Review test suite for unnecessary bloat and duplication | Medium | COMPLETED |
| [#190](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/190) | Add debug logging for silent failure cases | Medium | COMPLETED |
| [#198](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/198) | Missing docstring examples in ecs scale and volume list commands | Medium | COMPLETED |
| [#204](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/204) | Feature: Track Cumulative Instance Costs Over Time | Low | COMPLETED |
| [#212](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/212) | Add cache clearing mechanism for AWS clients in utils.py | Low | COMPLETED |
| [#264](https://github.com/ivyleavedtoadflax/remote.py-sandbox/issues/264) | Add built-in file transfer commands (instance copy/sync) | Medium | COMPLETED |
