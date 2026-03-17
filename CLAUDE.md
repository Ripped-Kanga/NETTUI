# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NETTUI is a Python TUI application built with the [Textual](https://textual.textualize.io/) framework for managing network connections on Arch-based Linux systems (e.g., Omarchy). It targets **systemd-networkd** as the backend for network configuration.

Core user-facing features:
- Interface selection with live detail panel (carrier, state, addresses, gateway)
- Connection profile creation, editing, deletion, and activation
- Real-time bandwidth monitoring with sparkline graphs
- Network diagnostics (ping, traceroute) via keybinds
- Configurable settings (bandwidth units, ping/traceroute destinations)

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

- **`src/nettui/app.py`** — `NettuiApp(App)` entry point; mounts the interface list screen
- **`src/nettui/screens/`** — `Screen` subclasses:
  - `interface_list.py` — main 3-panel view (interface table, profile table with active label, detail panel)
  - `connection_editor.py` — profile create/edit form
  - `diagnostic_screen.py` — streams ping/traceroute output to a RichLog
  - `settings_screen.py` — bandwidth units, ping/traceroute destination config
  - `confirm_dialog.py` — reusable yes/no modal
- **`src/nettui/widgets/`** — reusable Textual `Widget` subclasses (interface table, profile table, detail panel, network form, status bar)
- **`src/nettui/networkd/`** — backend module that reads/writes systemd-networkd `.network` files under `/etc/systemd/network/`; no Textual imports here. Uses a hand-written INI parser (`parser._parse_ini`) instead of `configparser` to correctly handle repeated keys (`Address=`, `DNS=`)
- **`src/nettui/models.py`** — plain dataclasses (`NetworkProfile`, `InterfaceInfo`, `ProfileValidationError`)
- **`src/nettui/settings.py`** — runtime `Settings` dataclass for user preferences (bandwidth units, diagnostic destinations)

The `networkd/` layer is kept framework-agnostic so it can be tested without a running TUI. Screens call into `networkd/` to load and persist profiles; they never write config files directly.

## Profile Activation (Managed Files)

When a user activates a profile, NETTUI copies its settings into a dedicated managed file named `00-nettui-<iface>.network`. This file contains an `[X-Nettui]` section with `AppliedFrom=<source-filename>` to track which template profile was applied. The `00-` prefix ensures it takes precedence in networkd's alphabetical ordering.

Template profiles (user-created `.network` files) are kept separate from the managed active file. The profile list filters out managed files (those with `applied_from` set) so users only see their templates. The active profile label above the profile table shows which template is currently applied.

## systemd-networkd Conventions

Config files live in `/etc/systemd/network/`. Writing them requires root or membership in the `systemd-network` group. The app should warn clearly when it lacks write permission rather than silently failing.

Reload after writing: `networkctl reload` (or `systemd-networkd.service` restart if reload is unsupported on the running version).

## Textual Patterns

- Use CSS in `.tcss` files co-located with their screen/widget, loaded via `CSS_PATH` on the class.
- Prefer `reactive` attributes and `watch_*` methods for state that drives UI updates.
- Use `App.push_screen` / `App.pop_screen` for navigation between screens.
- Long-running operations (file I/O, `networkctl`) must run in a `worker` thread via `self.run_worker` to avoid blocking the event loop.
