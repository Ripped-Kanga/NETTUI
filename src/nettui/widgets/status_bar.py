from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class StatusBar(Widget):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        padding: 0 2;
    }
    StatusBar Label {
        width: 1fr;
    }
    StatusBar.error Label {
        color: $error;
    }
    StatusBar.warning Label {
        color: $warning;
    }
    StatusBar.success Label {
        color: $success;
    }
    """

    message: reactive[str] = reactive("", layout=True)

    def compose(self) -> ComposeResult:
        yield Label("", id="status-label")

    def watch_message(self, msg: str) -> None:
        self.query_one("#status-label", Label).update(msg)

    def set_status(self, msg: str, error: bool = False, warning: bool = False) -> None:
        self.remove_class("error", "warning", "success")
        if error:
            self.add_class("error")
        elif warning:
            self.add_class("warning")
        else:
            self.add_class("success")
        self.message = msg

    def set_permission_warning(self) -> None:
        self.set_status(
            "Warning: no write access to /etc/systemd/network/ — read-only mode",
            warning=True,
        )

    def clear(self) -> None:
        self.remove_class("error", "warning", "success")
        self.message = ""
