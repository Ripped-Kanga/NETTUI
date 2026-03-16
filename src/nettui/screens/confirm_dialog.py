from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmDialog(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }

    #dialog-container {
        width: 60;
        height: 10;
        border: solid $warning;
        background: $surface;
        padding: 2 4;
        layout: vertical;
    }

    #dialog-question {
        height: 3;
        content-align: center middle;
        text-align: center;
    }

    #dialog-buttons {
        layout: horizontal;
        align: center middle;
        height: 3;
    }

    #dialog-buttons Button {
        margin: 0 2;
    }
    """

    def __init__(self, question: str) -> None:
        super().__init__()
        self._question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog-container"):
            yield Label(self._question, id="dialog-question")
            with Horizontal(id="dialog-buttons"):
                yield Button("Yes", variant="error", id="yes")
                yield Button("No", variant="default", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")
