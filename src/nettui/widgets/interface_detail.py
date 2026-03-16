from __future__ import annotations

import json
import subprocess

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from nettui.models import InterfaceInfo

_STATE_COLOURS = {
    "routable": "green",
    "degraded": "yellow",
    "no-carrier": "red",
    "off": "red",
    "dormant": "yellow",
    "carrier": "cyan",
    "unknown": "white",
}


def _fetch_live_state(iface_name: str) -> dict:
    """Fetch live address/route data via `ip`."""
    addresses: list[str] = []
    gateway = ""

    try:
        r = subprocess.run(
            ["ip", "-j", "addr", "show", iface_name],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            for entry in json.loads(r.stdout):
                for addr_info in entry.get("addr_info", []):
                    local = addr_info.get("local", "")
                    prefix = addr_info.get("prefixlen", "")
                    if local:
                        addresses.append(f"{local}/{prefix}")
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["ip", "-j", "route", "show", "dev", iface_name],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            for route in json.loads(r.stdout):
                if route.get("dst") == "default" and "gateway" in route:
                    gateway = route["gateway"]
                    break
    except Exception:
        pass

    return {"addresses": addresses, "gateway": gateway}


def _row(label: str, value: str, value_style: str = "") -> Text:
    t = Text()
    t.append(f"  {label:<14}", style="bold dim")
    t.append(value, style=value_style)
    return t


class InterfaceDetailPanel(Widget):
    DEFAULT_CSS = """
    InterfaceDetailPanel {
        height: 1fr;
        border: solid $primary;
        padding: 1 2;
        overflow-y: auto;
    }

    InterfaceDetailPanel Static {
        height: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._interface: InterfaceInfo | None = None

    def compose(self) -> ComposeResult:
        yield Static("Select an interface to view details.", id="detail-content")

    def load_interface(self, interface: InterfaceInfo) -> None:
        """Load and display details for a new interface."""
        self._interface = interface
        self.query_one("#detail-content", Static).update("Loading…")
        self.run_worker(self._load, thread=True)

    def _load(self) -> None:
        if self._interface is None:
            return
        live = _fetch_live_state(self._interface.name)
        self.app.call_from_thread(self._update_display, live)

    def _update_display(self, live: dict) -> None:
        if self._interface is None:
            return
        iface = self._interface
        state_colour = _STATE_COLOURS.get(iface.operational_state, "white")
        carrier_text = ("● Up", "green") if iface.carrier else ("○ Down", "red")

        lines: list[Text] = []

        lines.append(Text("  Interface", style="bold"))
        lines.append(Text("  " + "─" * 28, style="dim"))
        lines.append(_row("Name", iface.name))
        lines.append(_row("Type", iface.type))
        lines.append(_row("MAC", iface.mac_address or "—"))
        lines.append(_row("Carrier", carrier_text[0], carrier_text[1]))
        lines.append(_row("State", iface.operational_state, state_colour))
        lines.append(_row("Profiles", str(len(iface.linked_profiles))))
        lines.append(Text(""))

        lines.append(Text("  Live Network State", style="bold"))
        lines.append(Text("  " + "─" * 28, style="dim"))

        if live["addresses"]:
            lines.append(_row("Addresses", live["addresses"][0]))
            for addr in live["addresses"][1:]:
                lines.append(_row("", addr))
        else:
            lines.append(_row("Addresses", "none", "dim"))

        lines.append(_row("Gateway", live["gateway"] or "—"))

        self.query_one("#detail-content", Static).update(Text("\n").join(lines))

    def refresh_live(self) -> None:
        """Re-fetch live state (call after a networkd reload)."""
        if self._interface is not None:
            self.run_worker(self._load, thread=True)
