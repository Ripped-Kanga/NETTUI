# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NETTUI is a Python TUI application built with the [Textual](https://textual.textualize.io/) framework for managing network connections on Arch-based Linux systems (e.g., Omarchy). It targets **systemd-networkd** as the backend for network configuration.

Core user-facing features:
- Interface selection (list and select network interfaces)
- Connection profile creation and selection
- Editing network connection details (IP, DNS, gateway, DHCP, etc.)

## Development Setup

This project uses `uv` for dependency management. On Arch/Omarchy, install it first via `pipx install uv` (system Python has no pip). Then:

```bash
uv sync
uv run nettui            # run the app
uv run textual run --dev src/nettui/app.py  # live CSS reload during development
uv run pytest            # run all tests
uv run pytest tests/test_parser.py  # run a single test file
uv run ruff check .      # lint
uv run ruff format .     # format
```

Dependencies belong in `pyproject.toml`. Core runtime dependencies: `textual`. Dev dependencies: `pytest`, `ruff`, `pytest-asyncio`, `textual-dev`.

## Architecture

The app is structured around Textual's component model:

- **`src/nettui/app.py`** — `NettuiApp(App)` entry point; mounts top-level screens
- **`src/nettui/screens/`** — one `Screen` subclass per major view (interface list, profile list, connection editor)
- **`src/nettui/widgets/`** — reusable Textual `Widget` subclasses for forms, tables, etc.
- **`src/nettui/networkd/`** — backend module that reads/writes systemd-networkd `.network` files under `/etc/systemd/network/`; no Textual imports here. Uses a hand-written INI parser (`parser._parse_ini`) instead of `configparser` to correctly handle repeated keys (`Address=`, `DNS=`)
- **`src/nettui/models.py`** — plain dataclasses representing a connection profile (interface, addresses, DNS, gateway, DHCP flag, etc.)

The `networkd/` layer is kept framework-agnostic so it can be tested without a running TUI. Screens call into `networkd/` to load and persist profiles; they never write config files directly.

## systemd-networkd Conventions

Config files live in `/etc/systemd/network/`. Writing them requires root or membership in the `systemd-network` group. The app should warn clearly when it lacks write permission rather than silently failing.

Reload after writing: `networkctl reload` (or `systemd-networkd.service` restart if reload is unsupported on the running version).

## Textual Patterns

- Use CSS in `.tcss` files co-located with their screen/widget, loaded via `CSS_PATH` on the class.
- Prefer `reactive` attributes and `watch_*` methods for state that drives UI updates.
- Use `App.push_screen` / `App.pop_screen` for navigation between screens.
- Long-running operations (file I/O, `networkctl`) must run in a `worker` thread via `self.run_worker` to avoid blocking the event loop.
