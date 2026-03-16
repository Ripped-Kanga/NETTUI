from __future__ import annotations

import os
import shutil
import sys

from textual.app import App
from textual.binding import Binding

from nettui.screens.interface_list import InterfaceListScreen


class NettuiApp(App):
    TITLE = "NETTUI"
    SUB_TITLE = "systemd-networkd manager"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    def on_mount(self) -> None:
        self.push_screen(InterfaceListScreen())


def main() -> None:
    if os.getuid() != 0 and not os.access("/etc/systemd/network", os.W_OK):
        exe = shutil.which(sys.argv[0]) or sys.argv[0]
        os.execvp("sudo", ["sudo", exe, *sys.argv[1:]])
    NettuiApp().run()


if __name__ == "__main__":
    main()
