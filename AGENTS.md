# AGENTS Instructions

This repository implements a Telegram → Discord bridge. Use this file as a checklist when contributing.

## Environment

- Use **Python 3.12+**.
- Install dependencies with `pip install -r requirements.txt`.

## Code Style

- Format Python code with [Black](https://github.com/psf/black) (configured for Python 3.12).
- `pylint` enforces a **150 character** line length (`.pylintrc`).
- Prefer **double quotes** for strings.
- Provide **triple-quoted docstrings** for modules, classes and functions.
- Add **type hints** to public interfaces.
- Group imports into standard library, third-party, and local sections.

## Repository Layout

- `forwarder.py` — CLI entry point for running the bridge.
- `bridge/` — core logic including Discord, Telegram and utility modules.
- `api/` — management API components.
- `core/` — shared utilities (e.g., `SingletonMeta`).
- `tests/` — pytest test suite and fixtures.

## Working with the Codebase

1. Make your changes.
1. Run lint and formatting:

   ```bash
   pre-commit run --files <file1> [<file2> ...]
   ```

1. Execute tests:

   ```bash
   pytest
   ```

1. Commit with a concise message (e.g., `fix: adjust history backend`).
1. Do **not** amend or rewrite existing commits on the main branch.

## Additional Notes

- Use `rg` (ripgrep) for code searches.
- Copy `config-example.yml` to `config.yml` for local runs.
- Start the bridge with `python forwarder.py --start` (add `--background` to run as a daemon).
- Respect existing architecture and keep tests up to date when modifying or adding features.
