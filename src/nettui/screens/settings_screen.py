from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet

from nettui.settings import SETTINGS


class SettingsScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-container {
        width: 58;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 3 2 3;
    }

    #settings-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        height: 1;
        margin-bottom: 1;
    }

    .section-label {
        color: $text-muted;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    RadioSet {
        height: auto;
        margin: 0;
        border: none;
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
            yield Label("Bandwidth Units", classes="section-label")
            yield RadioSet(
                RadioButton("Bytes  (B, KB, MB, GB/s)", value=SETTINGS.bw_unit == "bytes"),
                RadioButton("Bits   (b, Kb, Mb, Gb/s)", value=SETTINGS.bw_unit == "bits"),
                id="bw-unit-radio",
            )
            with Horizontal(id="settings-buttons"):
                yield Button("Close", variant="primary", id="btn-close")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        SETTINGS.bw_unit = "bytes" if event.index == 0 else "bits"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
