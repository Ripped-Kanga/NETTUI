from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header

from nettui.models import NetworkProfile, ProfileValidationError
from nettui.widgets.network_form import NetworkForm
from nettui.widgets.status_bar import StatusBar


class ConnectionEditorScreen(Screen[NetworkProfile | None]):
    CSS_PATH = "connection_editor.tcss"

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, profile: NetworkProfile) -> None:
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        title = "New Profile" if self._profile.is_new() else f"Edit — {self._profile.filename}"
        yield Header(show_clock=False)
        self.title = title
        yield NetworkForm(profile=self._profile, id="editor-form")
        with Horizontal(id="editor-buttons"):
            yield Button("Save  [ctrl+s]", variant="primary", id="btn-save")
            yield Button("Cancel  [esc]", variant="default", id="btn-cancel")
        yield StatusBar(id="status")
        yield Footer()

    def action_save(self) -> None:
        form = self.query_one("#editor-form", NetworkForm)
        try:
            updated = form.collect()
            self.dismiss(updated)
        except ProfileValidationError as exc:
            form.show_error(exc.field, exc.message)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
