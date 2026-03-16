from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header

from nettui.models import InterfaceInfo, NetworkProfile
from nettui.networkd import (
    InterfaceScanner,
    NetworkFileWriter,
    NetworkdPermissionError,
    delete_profile,
    link_profiles,
    load_all,
    reload_networkd,
)
from nettui.networkd.parser import NETWORKD_DIR
from nettui.screens.confirm_dialog import ConfirmDialog
from nettui.screens.connection_editor import ConnectionEditorScreen
from nettui.screens.settings_screen import SettingsScreen
from nettui.widgets.interface_detail import InterfaceDetailPanel
from nettui.widgets.interface_table import InterfaceTable
from nettui.widgets.profile_table import ProfileTable
from nettui.widgets.status_bar import StatusBar


class InterfaceListScreen(Screen):
    CSS_PATH = "interface_list.tcss"

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("n", "new_profile", "New Profile"),
        Binding("e", "edit_profile", "Edit Profile"),
        Binding("d", "delete_profile", "Delete Profile"),
        Binding("s", "settings", "Settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._selected_interface: InterfaceInfo | None = None
        self._can_write = os.access(NETWORKD_DIR, os.W_OK)
        self._suppress_highlight = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        self.title = "NETTUI — Network Manager"
        yield InterfaceTable(id="iface-table")
        with Horizontal(id="bottom-split"):
            yield InterfaceDetailPanel(id="detail-panel")
            yield ProfileTable(id="profile-table")
        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self) -> None:
        if not self._can_write:
            self.query_one(StatusBar).set_permission_warning()
        self.action_refresh()

    # ── Data loading ──────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self.run_worker(self._load_interfaces, thread=True)

    def _load_interfaces(self) -> None:
        try:
            interfaces = InterfaceScanner().list_interfaces()
            profiles = load_all()
            link_profiles(interfaces, profiles)
            self.app.call_from_thread(self._update_interface_table, interfaces, profiles)
        except Exception as exc:
            self.app.call_from_thread(
                self.query_one(StatusBar).set_status,
                f"Error loading interfaces: {exc}",
                True,
            )

    def _update_interface_table(
        self, interfaces: list[InterfaceInfo], profiles: list[NetworkProfile]
    ) -> None:
        iface_table = self.query_one(InterfaceTable)
        prev_name = self._selected_interface.name if self._selected_interface else None

        # Suppress highlight events while repopulating to avoid cursor-reset side effects
        self._suppress_highlight = True
        iface_table.load(interfaces)

        # Restore cursor to previously selected interface
        if prev_name:
            iface_table.select_by_name(prev_name)
            # Update _selected_interface with refreshed data (new profile counts etc.)
            self._selected_interface = next(
                (i for i in interfaces if i.name == prev_name), None
            )
        self._suppress_highlight = False

        # Refresh the detail and profile panels using already-loaded profiles
        if self._selected_interface is not None:
            self.query_one(InterfaceDetailPanel).load_interface(self._selected_interface)
            iface_profiles = [
                p for p in profiles if p.interface_name == self._selected_interface.name
            ]
            self.query_one(ProfileTable).load(iface_profiles)

    def _load_profiles_for(self, interface: InterfaceInfo) -> None:
        self.run_worker(
            lambda: self._fetch_profiles(interface.name), thread=True
        )

    def _fetch_profiles(self, iface_name: str) -> None:
        profiles = [p for p in load_all() if p.interface_name == iface_name]
        self.app.call_from_thread(self.query_one(ProfileTable).load, profiles)

    # ── Interface selection ───────────────────────────────────────────────────

    def on_interface_table_highlighted(self, event: InterfaceTable.Highlighted) -> None:
        if self._suppress_highlight:
            return
        self._selected_interface = event.interface
        self.query_one(InterfaceDetailPanel).load_interface(event.interface)
        self._load_profiles_for(event.interface)

    def on_interface_table_selected(self, event: InterfaceTable.Selected) -> None:
        """Enter on interface row — move focus to profile table."""
        self._selected_interface = event.interface
        self.query_one(ProfileTable).query_one("DataTable").focus()

    # ── Profile actions ───────────────────────────────────────────────────────

    def action_new_profile(self) -> None:
        if self._selected_interface is None:
            self.query_one(StatusBar).set_status(
                "Select an interface first.", warning=True
            )
            return
        blank = NetworkProfile(
            filename="", interface_name=self._selected_interface.name, dhcp="yes"
        )
        self.app.push_screen(ConnectionEditorScreen(profile=blank), self._on_editor_result)

    def action_edit_profile(self) -> None:
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.app.push_screen(
            ConnectionEditorScreen(profile=profile), self._on_editor_result
        )

    def on_profile_table_selected(self, event: ProfileTable.Selected) -> None:
        self.app.push_screen(
            ConnectionEditorScreen(profile=event.profile), self._on_editor_result
        )

    def action_delete_profile(self) -> None:
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.app.push_screen(
            ConfirmDialog(f"Delete '{profile.filename}'?"), self._on_confirm_delete
        )

    def action_settings(self) -> None:
        def _after(_: None) -> None:
            self.query_one(InterfaceDetailPanel)._rebuild_display()

        self.app.push_screen(SettingsScreen(), _after)

    def _on_confirm_delete(self, confirmed: bool) -> None:
        if not confirmed:
            return
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.run_worker(self._delete_and_reload(profile.filename), thread=True)

    def _on_editor_result(self, profile: NetworkProfile | None) -> None:
        if profile is None:
            return
        self.run_worker(self._write_and_reload(profile), thread=True)

    # ── Write / delete workers ────────────────────────────────────────────────

    def _write_and_reload(self, profile: NetworkProfile):
        def _work() -> None:
            status = self.query_one(StatusBar)
            ok = False
            try:
                path = NetworkFileWriter().write(profile)
                ok = True
                try:
                    reload_networkd()
                    self.app.call_from_thread(
                        status.set_status, f"Saved and reloaded: {path.name}"
                    )
                except Exception as exc:
                    self.app.call_from_thread(
                        status.set_status,
                        f"Saved {path.name} but reload failed: {exc}",
                        False, True,
                    )
            except NetworkdPermissionError as exc:
                self.app.call_from_thread(
                    status.set_status,
                    f"Permission denied: {exc}. Try running with sudo.",
                    True,
                )
            except Exception as exc:
                self.app.call_from_thread(status.set_status, f"Error: {exc}", True)

            if ok:
                self.app.call_from_thread(self.action_refresh)
                self.app.call_from_thread(
                    self.query_one(InterfaceDetailPanel).refresh_live
                )

        return _work

    def _delete_and_reload(self, filename: str):
        def _work() -> None:
            status = self.query_one(StatusBar)
            ok = False
            try:
                delete_profile(filename)
                ok = True
                try:
                    reload_networkd()
                    self.app.call_from_thread(
                        status.set_status, f"Deleted and reloaded: {filename}"
                    )
                except Exception as exc:
                    self.app.call_from_thread(
                        status.set_status,
                        f"Deleted {filename} but reload failed: {exc}",
                        False, True,
                    )
            except NetworkdPermissionError as exc:
                self.app.call_from_thread(
                    status.set_status,
                    f"Permission denied: {exc}. Try running with sudo.",
                    True,
                )
            except Exception as exc:
                self.app.call_from_thread(status.set_status, f"Error: {exc}", True)

            if ok:
                self.app.call_from_thread(self.action_refresh)

        return _work
