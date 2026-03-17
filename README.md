# NETTUI

A terminal UI for managing systemd-networkd connections on Arch-based Linux systems, built with [Textual](https://textual.textualize.io/).

## Features

- **Interface browser** — list network interfaces with type, carrier status, and operational state
- **Profile management** — create, edit, delete, and activate `.network` profiles (DHCP or static with CIDR addresses)
- **Live detail panel** — view addresses, gateway, and real-time bandwidth with sparkline graphs
- **Profile activation** — apply a profile's settings to an interface with a single keypress; tracks which template is active
- **Network diagnostics** — run ping and traceroute from within the TUI
- **Settings** — configure bandwidth display units (bytes/bits) and diagnostic destinations (gateway, Cloudflare, custom IPs)

## Requirements

- Arch Linux (or any systemd-networkd based system)
- Python 3.12+
- `traceroute` package (for traceroute diagnostics)
- Write access to `/etc/systemd/network/` (run as root or add user to `systemd-network` group)

## Installation

```bash
pipx install uv   # if not already installed
uv sync
```

## Usage

```bash
uv run nettui
```

### Keybindings

| Key | Action |
|-----|--------|
| `n` | New profile |
| `e` | Edit selected profile |
| `d` | Delete selected profile |
| `a` | Activate selected profile |
| `r` | Refresh interfaces and profiles |
| `p` | Ping diagnostic |
| `t` | Traceroute diagnostic |
| `s` | Settings |
| `q` | Quit |

## Development

```bash
uv run textual run --dev src/nettui/app.py  # live CSS reload
uv run pytest                                # run tests
uv run ruff check .                          # lint
uv run ruff format .                         # format
```
