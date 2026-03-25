from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from nettui.settings import (
    DEST_CLOUDFLARE,
    DEST_CUSTOM1,
    DEST_CUSTOM2,
    DEST_GATEWAY,
    GRAPH_AREA,
    GRAPH_LINE,
    SETTINGS,
)

_DEST_OPTIONS = [DEST_GATEWAY, DEST_CLOUDFLARE, DEST_CUSTOM1, DEST_CUSTOM2]


class SettingsScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 100;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        border: solid $primary;
        background: $surface;
        padding: 1 3 2 3;
        overflow-y: auto;
    }

    #settings-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        height: 1;
        margin-bottom: 1;
    }

    #settings-columns {
        height: auto;
        layout: horizontal;
    }

    .settings-col {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }

    .section-label {
        color: $text-muted;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    .section-label-first {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    RadioSet {
        height: auto;
        margin: 0;
        border: none;
    }

    .custom-input {
        margin: 0 0 0 4;
        height: 3;
    }

    .custom-label {
        margin: 0 0 0 4;
        color: $text-muted;
    }

    #settings-buttons {
        align: right middle;
        height: 3;
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("Settings", id="settings-title")

            with Horizontal(id="settings-columns"):
                # ── Left column: display settings ──
                with Vertical(classes="settings-col"):
                    yield Label("Bandwidth Units", classes="section-label-first")
                    yield RadioSet(
                        RadioButton("Bytes  (B, KB, MB, GB/s)", value=SETTINGS.bw_unit == "bytes"),
                        RadioButton("Bits   (b, Kb, Mb, Gb/s)", value=SETTINGS.bw_unit == "bits"),
                        id="bw-unit-radio",
                    )

                    yield Label("Graph Style", classes="section-label")
                    yield RadioSet(
                        RadioButton(
                            "Line  (braille dots)", value=SETTINGS.graph_style == GRAPH_LINE
                        ),
                        RadioButton("Area  (block fill)", value=SETTINGS.graph_style == GRAPH_AREA),
                        id="graph-style-radio",
                    )

                    yield Label("Custom Addresses", classes="section-label")
                    yield Label("Custom 1", classes="custom-label")
                    yield Input(
                        value=SETTINGS.custom1_addr,
                        placeholder="IP or hostname",
                        id="custom1-input",
                        classes="custom-input",
                    )
                    yield Label("Custom 2", classes="custom-label")
                    yield Input(
                        value=SETTINGS.custom2_addr,
                        placeholder="IP or hostname",
                        id="custom2-input",
                        classes="custom-input",
                    )

                # ── Right column: diagnostic settings ──
                with Vertical(classes="settings-col"):
                    yield Label("Ping Destination", classes="section-label-first")
                    yield RadioSet(
                        RadioButton("Gateway", value=SETTINGS.ping_dest == DEST_GATEWAY),
                        RadioButton(
                            "Cloudflare (1.1.1.1)",
                            value=SETTINGS.ping_dest == DEST_CLOUDFLARE,
                        ),
                        RadioButton("Custom 1", value=SETTINGS.ping_dest == DEST_CUSTOM1),
                        RadioButton("Custom 2", value=SETTINGS.ping_dest == DEST_CUSTOM2),
                        id="ping-dest-radio",
                    )

                    yield Label("Traceroute Destination", classes="section-label")
                    yield RadioSet(
                        RadioButton("Gateway", value=SETTINGS.traceroute_dest == DEST_GATEWAY),
                        RadioButton(
                            "Cloudflare (1.1.1.1)",
                            value=SETTINGS.traceroute_dest == DEST_CLOUDFLARE,
                        ),
                        RadioButton("Custom 1", value=SETTINGS.traceroute_dest == DEST_CUSTOM1),
                        RadioButton("Custom 2", value=SETTINGS.traceroute_dest == DEST_CUSTOM2),
                        id="traceroute-dest-radio",
                    )

            with Horizontal(id="settings-buttons"):
                yield Button("Close", variant="primary", id="btn-close")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        radio_id = event.radio_set.id
        if radio_id == "bw-unit-radio":
            SETTINGS.bw_unit = "bytes" if event.index == 0 else "bits"
        elif radio_id == "graph-style-radio":
            SETTINGS.graph_style = GRAPH_LINE if event.index == 0 else GRAPH_AREA
        elif radio_id == "ping-dest-radio":
            SETTINGS.ping_dest = _DEST_OPTIONS[event.index]
        elif radio_id == "traceroute-dest-radio":
            SETTINGS.traceroute_dest = _DEST_OPTIONS[event.index]

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "custom1-input":
            SETTINGS.custom1_addr = event.value.strip()
        elif event.input.id == "custom2-input":
            SETTINGS.custom2_addr = event.value.strip()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
