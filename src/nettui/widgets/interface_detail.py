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
from nettui.settings import GRAPH_AREA, SETTINGS

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

_GRAPH_HEIGHT = 4  # character rows tall

# ── Area chart (block eighths) ──
_EIGHTHS = " ▁▂▃▄▅▆▇█"


def _area_sparkline(values: list[float], width: int, height: int) -> list[str]:
    """Render a filled area sparkline using block-eighth characters."""
    if not values:
        return [" " * width] * height

    max_val = max(values) or 1.0
    data = values[-width:]
    total_sub = height * 8
    sub_heights = [round((v / max_val) * total_sub) for v in data]

    rows = []
    for row_idx in range(height - 1, -1, -1):
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


# ── Line graph (braille dots) ──
# Braille base: U+2800.  Dot numbering (column-major):
#   col 0: dots 0,1,2,6  (bits 0x01,0x02,0x04,0x40)
#   col 1: dots 3,4,5,7  (bits 0x08,0x10,0x20,0x80)
# Row 0 is top, row 3 is bottom within a character cell.
_BRAILLE_BASE = 0x2800
_DOT_LEFT = [0x40, 0x04, 0x02, 0x01]  # row 0(top)..row 3(bottom)
_DOT_RIGHT = [0x80, 0x20, 0x10, 0x08]


def _braille_line_graph(values: list[float], width: int, height: int) -> list[str]:
    """Render a line graph using braille characters.

    Each character cell is 2 data points wide and 4 dots tall.
    Returns `height` strings (top row first), each `width` chars wide.
    Total vertical resolution: height * 4 dots.
    """
    if not values:
        return [" " * width] * height

    # Each char holds 2 data points, so we can fit width*2 samples
    max_samples = width * 2
    data = values[-max_samples:]

    max_val = max(data) or 1.0
    total_dots = height * 4
    # Map each value to a dot row (0 = bottom, total_dots-1 = top)
    dot_positions = [round((v / max_val) * (total_dots - 1)) for v in data]

    # Build a height×width grid of braille code points
    grid = [[_BRAILLE_BASE] * width for _ in range(height)]

    # Right-align: offset so newest data appears at the right edge
    data_chars = (len(data) + 1) // 2  # chars needed for data
    col_offset = width - data_chars

    for i, dot_y in enumerate(dot_positions):
        col = col_offset + i // 2  # which character column
        is_right = i % 2  # left or right dot column within the char

        # dot_y=0 is bottom; convert to row/sub-row (row 0 = top char row)
        char_row = height - 1 - (dot_y // 4)
        sub_row = 3 - (dot_y % 4)  # 0=top dot, 3=bottom dot within cell

        if 0 <= char_row < height and 0 <= col < width:
            dots = _DOT_RIGHT if is_right else _DOT_LEFT
            grid[char_row][col] |= dots[sub_row]

    # Connect adjacent points with interpolated dots for smoother lines
    for i in range(len(dot_positions) - 1):
        y0 = dot_positions[i]
        y1 = dot_positions[i + 1]
        if abs(y1 - y0) <= 1:
            continue
        step = 1 if y1 > y0 else -1
        for y in range(y0 + step, y1, step):
            # Interpolate: place dot at fractional x position
            frac = (y - y0) / (y1 - y0)
            x = i + frac
            col = col_offset + int(x) // 2
            is_right = int(x) % 2
            char_row = height - 1 - (y // 4)
            sub_row = 3 - (y % 4)
            if 0 <= char_row < height and 0 <= col < width:
                dots = _DOT_RIGHT if is_right else _DOT_LEFT
                grid[char_row][col] |= dots[sub_row]

    rows = []
    for row in grid:
        pad = width - len(row)
        line = " " * pad + "".join(chr(cp) for cp in row)
        rows.append(line)
    return rows


def _render_graph(values: list[float], width: int, height: int) -> list[str]:
    """Dispatch to the configured graph style."""
    if SETTINGS.graph_style == GRAPH_AREA:
        return _area_sparkline(values, width, height)
    return _braille_line_graph(values, width, height)


def _fetch_live_state(iface_name: str) -> dict:
    """Fetch live address/route/DNS data via `ip` and `resolvectl`."""
    addresses: list[str] = []
    gateway = ""
    metric = ""
    dns: list[str] = []

    try:
        r = subprocess.run(
            ["ip", "-j", "addr", "show", iface_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            for entry in json.loads(r.stdout):
                for addr_info in entry.get("addr_info", []):
                    local = addr_info.get("local", "")
                    prefix = addr_info.get("prefixlen", "")
                    if local and not local.startswith("fe80:"):
                        addresses.append(f"{local}/{prefix}")
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["ip", "-j", "route", "show", "dev", iface_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            for route in json.loads(r.stdout):
                if route.get("dst") == "default" and "gateway" in route:
                    gateway = route["gateway"]
                    metric = str(route.get("metric", ""))
                    break
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["resolvectl", "dns", iface_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            # Output like: "Link 2 (eth0): 1.1.1.1 8.8.8.8"
            parts = r.stdout.strip().split(":", 1)
            if len(parts) == 2:
                dns = parts[1].split()
    except Exception:
        pass

    return {"addresses": addresses, "gateway": gateway, "metric": metric, "dns": dns}


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
        self._live: dict = {"addresses": [], "gateway": "", "metric": "", "dns": []}

    def compose(self) -> ComposeResult:
        yield Static("Select an interface to view details.", id="detail-content")

    def on_mount(self) -> None:
        if self._interface is not None:
            self.query_one("#detail-content", Static).update("Loading…")
            self.run_worker(self._load, thread=True)

    def load_interface(self, interface: InterfaceInfo) -> None:
        """Load and display details for a new interface."""
        self._interface = interface
        self._live = {"addresses": [], "gateway": "", "metric": "", "dns": []}
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
        if iface.alias:
            lines.append(_row("Alias", iface.alias, "italic"))
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

        if live["dns"]:
            lines.append(_row("DNS", live["dns"][0]))
            for srv in live["dns"][1:]:
                lines.append(_row("", srv))
        else:
            lines.append(_row("DNS", "—", "dim"))

        lines.append(_row("Metric", live["metric"] or "—"))

        self.query_one("#detail-content", Static).update(Text("\n").join(lines))

    def refresh_live(self) -> None:
        """Re-fetch live state (call after a networkd reload)."""
        if self._interface is not None:
            self.run_worker(self._load, thread=True)


class BandwidthGraphPanel(Widget):
    BORDER_TITLE = "Bandwidth"

    DEFAULT_CSS = """
    BandwidthGraphPanel {
        height: auto;
        min-height: 12;
        border: solid $primary;
        padding: 0 1;
    }

    BandwidthGraphPanel Static {
        height: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._iface_name: str | None = None
        self._prev_rx: int | None = None
        self._prev_tx: int | None = None
        self._prev_time: float | None = None
        self._bw_rx: float | None = None
        self._bw_tx: float | None = None
        self._bw_history: deque[tuple[float, float]] = deque(maxlen=30)

    def compose(self) -> ComposeResult:
        yield Static("", id="graph-content")

    def on_mount(self) -> None:
        self.set_interval(1.0, self._poll_bandwidth)

    def load_interface(self, iface_name: str) -> None:
        self._iface_name = iface_name
        self._prev_rx = self._prev_tx = self._prev_time = None
        self._bw_rx = self._bw_tx = None
        self._bw_history.clear()
        self._rebuild()

    def _poll_bandwidth(self) -> None:
        if self._iface_name is None:
            return
        try:
            rx = int((_SYS_NET / self._iface_name / "statistics" / "rx_bytes").read_text())
            tx = int((_SYS_NET / self._iface_name / "statistics" / "tx_bytes").read_text())
        except OSError:
            return

        now = time.monotonic()
        if self._prev_rx is not None and self._prev_time is not None:
            dt = now - self._prev_time
            if dt > 0:
                self._bw_rx = (rx - self._prev_rx) / dt
                self._bw_tx = (tx - self._prev_tx) / dt
                self._bw_history.append((self._bw_rx, self._bw_tx))
                self._rebuild()

        self._prev_rx = rx
        self._prev_tx = tx
        self._prev_time = now

    def _rebuild(self) -> None:
        lines: list[Text] = []

        if self._bw_rx is not None:
            lines.append(_row("↓ RX", _fmt_rate(self._bw_rx, SETTINGS.bw_unit), "green"))
            lines.append(_row("↑ TX", _fmt_rate(self._bw_tx, SETTINGS.bw_unit), "cyan"))
        else:
            lines.append(_row("↓ RX", "measuring…", "dim"))
            lines.append(_row("↑ TX", "measuring…", "dim"))

        lines.append(Text(""))

        prefix_len = 8
        graph_width = max(10, (self.content_size.width or 50) - prefix_len)
        indent = " " * prefix_len

        rx_history = [r for r, _ in self._bw_history]
        tx_history = [t for _, t in self._bw_history]

        for i, row_str in enumerate(_render_graph(rx_history, graph_width, _GRAPH_HEIGHT)):
            t = Text()
            t.append("  ↓ RX  " if i == 0 else indent, style="bold dim" if i == 0 else "")
            t.append(row_str, style="green")
            lines.append(t)

        lines.append(Text(""))

        for i, row_str in enumerate(_render_graph(tx_history, graph_width, _GRAPH_HEIGHT)):
            t = Text()
            t.append("  ↑ TX  " if i == 0 else indent, style="bold dim" if i == 0 else "")
            t.append(row_str, style="cyan")
            lines.append(t)

        self.query_one("#graph-content", Static).update(Text("\n").join(lines))
