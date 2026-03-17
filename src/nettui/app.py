from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from nettui.screens.interface_list import InterfaceListScreen

_PKG_ASSETS = Path(__file__).parent / "assets"


class NettuiApp(App):
    TITLE = "NETTUI"
    SUB_TITLE = "systemd-networkd manager"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    def on_mount(self) -> None:
        self.push_screen(InterfaceListScreen())


def _install_desktop() -> None:
    """Install .desktop file and icon for application launchers."""
    apps_dir = Path.home() / ".local" / "share" / "applications"
    icons_dir = Path.home() / ".local" / "share" / "icons"
    apps_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    desktop_src = _PKG_ASSETS / "nettui.desktop"
    icon_src = _PKG_ASSETS / "nettui.svg"

    if not desktop_src.exists() or not icon_src.exists():
        print(f"Error: asset files not found at {_PKG_ASSETS}")
        sys.exit(1)

    desktop_dest = apps_dir / "nettui.desktop"
    icon_dest = icons_dir / "nettui.svg"

    shutil.copy2(icon_src, icon_dest)
    print(f"Installed icon: {icon_dest}")

    # Write desktop file with absolute icon path
    content = desktop_src.read_text(encoding="utf-8")
    content = content.replace("Icon=nettui", f"Icon={icon_dest}")

    # Resolve the nettui executable path
    nettui_bin = shutil.which("nettui") or "nettui"
    content = content.replace("Exec=nettui", f"Exec={nettui_bin}")

    desktop_dest.write_text(content, encoding="utf-8")
    print(f"Installed desktop file: {desktop_dest}")
    print("Done. The application should now appear in your launcher.")


def _uninstall_desktop() -> None:
    """Remove .desktop file and icon."""
    desktop = Path.home() / ".local" / "share" / "applications" / "nettui.desktop"
    icon = Path.home() / ".local" / "share" / "icons" / "nettui.svg"

    for path in (desktop, icon):
        if path.exists():
            path.unlink()
            print(f"Removed: {path}")
        else:
            print(f"Not found: {path}")

    print("Done.")


def main() -> None:
    if "--install-desktop" in sys.argv:
        _install_desktop()
        return
    if "--uninstall-desktop" in sys.argv:
        _uninstall_desktop()
        return

    if os.getuid() != 0 and not os.access("/etc/systemd/network", os.W_OK):
        exe = shutil.which(sys.argv[0]) or sys.argv[0]
        os.execvp("sudo", ["sudo", exe, *sys.argv[1:]])
    NettuiApp().run()


if __name__ == "__main__":
    main()
