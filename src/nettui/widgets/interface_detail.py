from __future__ import annotations

import json
import subprocess
import time
from collections import deque
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from nettui.models import InterfaceInfo
from nettui.settings import SETTINGS

_SYS_NET = Path("/sys/class/net")

_STATE_COLOURS = {
    "routable": "green",
    "degraded": "yellow",
    "no-carrier": "red",
    "off": "red",
    "dormant": "yellow",
    "carrier": "cyan",
    "unknown": "white",
}

# 9 levels: empty through full block (8 sub-pixel steps per character row)
_EIGHTHS = " ▁▂▃▄▅▆▇█"
_GRAPH_HEIGHT = 3  # character rows tall; ×8 sub-pixels = 24 effective levels


def _multirow_sparkline(values: list[float], width: int, height: int) -> list[str]:
    """
    Render a filled area sparkline across multiple character rows.

    Returns `height` strings (top row first), each `width` chars wide.
    Each character row contributes 8 vertical sub-pixel levels via _EIGHTHS,
    giving `height * 8` total effective resolution levels.
    """
    if not values:
        return [" " * width] * height

    max_val = max(values) or 1.0
    data = values[-width:]
    total_sub = height * 8
    sub_heights = [round((v / max_val) * total_sub) for v in data]

    rows = []
    for row_idx in range(height - 1, -1, -1):  # highest value row first
        row_floor = row_idx * 8
        chars = []
        for sh in sub_heights:
            if sh <= row_floor:
                chars.append(" ")
            elif sh >= row_floor + 8:
                chars.append("█")
            else:
                chars.append(_EIGHTHS[sh - row_floor])
        rows.append(" " * (width - len(chars)) + "".join(chars))

    return rows


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


def _fmt_rate(bps: float, unit: str = "bytes") -> str:
    """Format a bytes/sec value as a human-readable rate string.

    unit="bytes": binary tiers (B, KB, MB, GB) using 1024 boundaries.
    unit="bits":  decimal tiers (b, Kb, Mb, Gb) using 1000 boundaries,
                  per networking convention.
    """
    if unit == "bits":
        b = bps * 8
        if b >= 1_000_000_000:
            return f"{b / 1_000_000_000:.1f} Gb/s"
        if b >= 1_000_000:
            return f"{b / 1_000_000:.1f} Mb/s"
        if b >= 1_000:
            return f"{b / 1_000:.1f} Kb/s"
        return f"{b:.0f} b/s"
    # bytes — binary (IEC) boundaries
    if bps >= 1_073_741_824:
        return f"{bps / 1_073_741_824:.1f} GB/s"
    if bps >= 1_048_576:
        return f"{bps / 1_048_576:.1f} MB/s"
    if bps >= 1_024:
        return f"{bps / 1_024:.1f} KB/s"
    return f"{bps:.0f} B/s"


def _row(label: str, value: str, value_style: str = "") -> Text:
    t = Text()
    t.append(f"  {label:<14}", style="bold dim")
    t.append(value, style=value_style)
    return t


class InterfaceDetailPanel(Widget):
    BORDER_TITLE = "Details"

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

    def __init__(self, interface: InterfaceInfo | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._interface = interface
        self._live: dict = {"addresses": [], "gateway": ""}
        self._prev_rx: int | None = None
        self._prev_tx: int | None = None
        self._prev_time: float | None = None
        self._bw_rx: float | None = None
        self._bw_tx: float | None = None
        # Rolling 60-second history: (rx_bytes_per_sec, tx_bytes_per_sec)
        self._bw_history: deque[tuple[float, float]] = deque(maxlen=60)

    def compose(self) -> ComposeResult:
        yield Static("Select an interface to view details.", id="detail-content")

    def on_mount(self) -> None:
        if self._interface is not None:
            self.query_one("#detail-content", Static).update("Loading…")
            self.run_worker(self._load, thread=True)
        self.set_interval(1.0, self._poll_bandwidth)

    def load_interface(self, interface: InterfaceInfo) -> None:
        """Load and display details for a new interface."""
        self._interface = interface
        self._live = {"addresses": [], "gateway": ""}
        self._prev_rx = self._prev_tx = self._prev_time = None
        self._bw_rx = self._bw_tx = None
        self._bw_history.clear()
        self.query_one("#detail-content", Static).update("Loading…")
        self.run_worker(self._load, thread=True)

    def _load(self) -> None:
        if self._interface is None:
            return
        live = _fetch_live_state(self._interface.name)
        self.app.call_from_thread(self._update_display, live)

    def _update_display(self, live: dict) -> None:
        self._live = live
        self._rebuild_display()

    def _poll_bandwidth(self) -> None:
        """Sample sysfs byte counters and update the bandwidth display once per second."""
        if self._interface is None:
            return
        name = self._interface.name
        try:
            rx = int((_SYS_NET / name / "statistics" / "rx_bytes").read_text())
            tx = int((_SYS_NET / name / "statistics" / "tx_bytes").read_text())
        except OSError:
            return

        now = time.monotonic()
        if self._prev_rx is not None and self._prev_time is not None:
            dt = now - self._prev_time
            if dt > 0:
                self._bw_rx = (rx - self._prev_rx) / dt
                self._bw_tx = (tx - self._prev_tx) / dt
                self._bw_history.append((self._bw_rx, self._bw_tx))
                self._rebuild_display()

        self._prev_rx = rx
        self._prev_tx = tx
        self._prev_time = now

    def _rebuild_display(self) -> None:
        if self._interface is None:
            return
        iface = self._interface
        live = self._live
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
        lines.append(Text(""))

        lines.append(Text("  Bandwidth", style="bold"))
        lines.append(Text("  " + "─" * 28, style="dim"))
        if self._bw_rx is not None:
            lines.append(_row("↓ RX", _fmt_rate(self._bw_rx, SETTINGS.bw_unit), "green"))
            lines.append(_row("↑ TX", _fmt_rate(self._bw_tx, SETTINGS.bw_unit), "cyan"))
        else:
            lines.append(_row("↓ RX", "measuring…", "dim"))
            lines.append(_row("↑ TX", "measuring…", "dim"))

        lines.append(Text(""))
        lines.append(Text("  Bandwidth Graph  (1 min)", style="bold"))
        lines.append(Text("  " + "─" * 28, style="dim"))

        # 8-char prefix "  ↓ RX  "; continuation rows indent by the same amount
        prefix_len = 8
        graph_width = max(10, (self.content_size.width or 63) - prefix_len)
        indent = " " * prefix_len

        rx_history = [r for r, _ in self._bw_history]
        tx_history = [t for _, t in self._bw_history]

        for i, row_str in enumerate(_multirow_sparkline(rx_history, graph_width, _GRAPH_HEIGHT)):
            t = Text()
            t.append("  ↓ RX  " if i == 0 else indent, style="bold dim" if i == 0 else "")
            t.append(row_str, style="green")
            lines.append(t)

        lines.append(Text(""))

        for i, row_str in enumerate(_multirow_sparkline(tx_history, graph_width, _GRAPH_HEIGHT)):
            t = Text()
            t.append("  ↑ TX  " if i == 0 else indent, style="bold dim" if i == 0 else "")
            t.append(row_str, style="cyan")
            lines.append(t)

        self.query_one("#detail-content", Static).update(Text("\n").join(lines))

    def refresh_live(self) -> None:
        """Re-fetch live state (call after a networkd reload)."""
        if self._interface is not None:
            self.run_worker(self._load, thread=True)
