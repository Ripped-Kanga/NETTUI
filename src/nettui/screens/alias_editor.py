from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class AliasEditorDialog(ModalScreen[str | None]):
    """Modal dialog for editing an interface alias name."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AliasEditorDialog {
        align: center middle;
    }

    #alias-container {
        width: 60;
        height: auto;
        border: solid $accent;
        background: $surface;
        padding: 2 4;
        layout: vertical;
    }

    #alias-title {
        height: auto;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #alias-hint {
        height: auto;
        color: $text-muted;
        margin-bottom: 1;
    }

    #alias-input {
        margin-bottom: 1;
    }

    #alias-buttons {
        layout: horizontal;
        align: center middle;
        height: auto;
    }

    #alias-buttons Button {
        margin: 0 2;
    }
    """

    def __init__(self, iface_name: str, current_alias: str = "") -> None:
        super().__init__()
        self._iface_name = iface_name
        self._current_alias = current_alias

    def compose(self) -> ComposeResult:
        with Vertical(id="alias-container"):
            yield Label(f"Edit Alias — {self._iface_name}", id="alias-title")
            yield Label(
                "Set a friendly name for this interface. Leave empty to remove.",
                id="alias-hint",
            )
            yield Input(
                value=self._current_alias,
                placeholder="e.g. Home WiFi, Office LAN",
                id="alias-input",
            )
            from textual.containers import Horizontal

            with Horizontal(id="alias-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#alias-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            alias = self.query_one("#alias-input", Input).value.strip()
            self.dismiss(alias)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        alias = event.value.strip()
        self.dismiss(alias)

    def action_cancel(self) -> None:
        self.dismiss(None)
