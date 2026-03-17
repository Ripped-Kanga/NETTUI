from __future__ import annotations

import subprocess
import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog


class DiagnosticScreen(Screen):
    DEFAULT_CSS = """
    DiagnosticScreen {
        layout: vertical;
    }

    RichLog {
        margin: 1;
        border: solid $primary;
        scrollbar-size: 1 1;
    }
    """

    BINDINGS = [
        Binding("escape", "stop_and_close", "Close"),
        Binding("q", "stop_and_close", "Close"),
    ]

    def __init__(self, command: list[str], title: str = "Diagnostic") -> None:
        super().__init__()
        self._command = command
        self._title = title
        self._proc: subprocess.Popen | None = None
        self._stop_event = threading.Event()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        self.title = f"NETTUI — {self._title}"
        yield RichLog(highlight=True, markup=False, wrap=True, id="output")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(f"$ {' '.join(self._command)}\n")
        self.run_worker(self._run_command, thread=True)

    def _run_command(self) -> None:
        log = self.query_one(RichLog)
        try:
            self._proc = subprocess.Popen(
                self._command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in self._proc.stdout:
                if self._stop_event.is_set():
                    break
                self.app.call_from_thread(log.write, line.rstrip())
            self._proc.wait()
            rc = self._proc.returncode
            if rc and not self._stop_event.is_set():
                self.app.call_from_thread(log.write, f"\nProcess exited with code {rc}")
        except FileNotFoundError:
            self.app.call_from_thread(log.write, f"Command not found: {self._command[0]}")
        except Exception as exc:
            self.app.call_from_thread(log.write, f"Error: {exc}")
        finally:
            if not self._stop_event.is_set():
                self.app.call_from_thread(log.write, "\n[Press Escape or q to close]")

    def action_stop_and_close(self) -> None:
        self._stop_event.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self.app.pop_screen()
