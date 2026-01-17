# Issue 23: Rename Package to `remote`

**Status:** Not started
**Priority:** Low (v0.5.0)
**GitHub Issue:** #26

## Problem

Current package folder is `remotepy` but the CLI command is `remote`. This inconsistency can be confusing.

## Current State

```
remote.py/
├── remotepy/          # Package directory
│   ├── __init__.py
│   ├── __main__.py
│   ├── instance.py
│   └── ...
├── tests/
└── pyproject.toml     # Entry point: remote = "remotepy.__main__:app"
```

## Proposed State

```
remote.py/
├── remote/            # Renamed package directory
│   ├── __init__.py
│   ├── __main__.py
│   ├── instance.py
│   └── ...
├── tests/
└── pyproject.toml     # Entry point: remote = "remote.__main__:app"
```

## Migration Steps

1. Rename `remotepy/` to `remote/`
2. Update all imports in source files
3. Update all imports in test files
4. Update `pyproject.toml` entry points
5. Update `CLAUDE.md` references
6. Update any documentation

## Risks

- **Breaking change** for existing users
- May conflict with other packages named `remote`
- Requires updating all imports across codebase

## Script to Update Imports

```bash
# Find and replace imports
find . -name "*.py" -exec sed -i 's/from remotepy/from remote/g' {} \;
find . -name "*.py" -exec sed -i 's/import remotepy/import remote/g' {} \;
```

## Acceptance Criteria

- [ ] Rename `remotepy/` directory to `remote/`
- [ ] Update all imports in source files
- [ ] Update all imports in test files
- [ ] Update pyproject.toml entry points
- [ ] Update CLAUDE.md and documentation
- [ ] All tests pass after rename
- [ ] Package installs and runs correctly
