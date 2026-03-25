from __future__ import annotations

import json
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "nettui"
_ALIASES_FILE = _CONFIG_DIR / "aliases.json"


def load_aliases() -> dict[str, str]:
    """Load interface aliases from config file. Returns {iface_name: alias}."""
    try:
        return json.loads(_ALIASES_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_alias(iface_name: str, alias: str) -> None:
    """Save or update an alias for an interface. Removes it if alias is empty."""
    aliases = load_aliases()
    if alias:
        aliases[iface_name] = alias
    else:
        aliases.pop(iface_name, None)
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ALIASES_FILE.write_text(json.dumps(aliases, indent=2), encoding="utf-8")
