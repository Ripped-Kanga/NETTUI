from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from nettui.models import InterfaceInfo, NetworkProfile
from nettui.networkd import (
    NetworkFileWriter,
    NetworkdPermissionError,
    delete_profile,
    load_all,
    reload_networkd,
)
from nettui.networkd.parser import NETWORKD_DIR
from nettui.screens.confirm_dialog import ConfirmDialog
from nettui.screens.connection_editor import ConnectionEditorScreen
from nettui.widgets.interface_detail import InterfaceDetailPanel
from nettui.widgets.profile_table import ProfileTable
from nettui.widgets.status_bar import StatusBar


class ProfileListScreen(Screen):
    CSS_PATH = "profile_list.tcss"

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("n", "new_profile", "New"),
        Binding("enter", "edit_profile", "Edit"),
        Binding("d", "delete_profile", "Delete"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, interface: InterfaceInfo) -> None:
        super().__init__()
        self.interface = interface
        self._can_write = os.access(NETWORKD_DIR, os.W_OK)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        self.title = f"Profiles — {self.interface.name}"

        # Top bar: interface summary spanning full width
        with Horizontal(id="iface-bar"):
            yield Label(self.interface.name, id="iface-name")
            yield Label(
                f"MAC: {self.interface.mac_address or '—'}   "
                f"Type: {self.interface.type}   "
                f"State: {self.interface.operational_state}",
                id="iface-meta",
            )

        # Bottom split: detail panel left, profile table right
        with Horizontal(id="split"):
            yield InterfaceDetailPanel(interface=self.interface, id="detail-panel")
            yield ProfileTable(id="profile-table")

        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self) -> None:
        if not self._can_write:
            self.query_one(StatusBar).set_permission_warning()
        self.action_refresh()

    def action_refresh(self) -> None:
        self.run_worker(self._load_profiles, thread=True)

    def _load_profiles(self) -> None:
        profiles = [p for p in load_all() if p.interface_name == self.interface.name]
        self.app.call_from_thread(self._update_table, profiles)

    def _update_table(self, profiles: list[NetworkProfile]) -> None:
        self.query_one(ProfileTable).load(profiles)

    def action_new_profile(self) -> None:
        blank = NetworkProfile(filename="", interface_name=self.interface.name, dhcp="yes")
        self.app.push_screen(ConnectionEditorScreen(profile=blank), self._on_editor_result)

    def action_edit_profile(self) -> None:
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.app.push_screen(ConnectionEditorScreen(profile=profile), self._on_editor_result)

    def on_profile_table_selected(self, event: ProfileTable.Selected) -> None:
        self.app.push_screen(
            ConnectionEditorScreen(profile=event.profile), self._on_editor_result
        )

    def _on_editor_result(self, profile: NetworkProfile | None) -> None:
        if profile is None:
            return
        self.run_worker(self._write_and_reload(profile), thread=True)

    def action_delete_profile(self) -> None:
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.app.push_screen(
            ConfirmDialog(f"Delete '{profile.filename}'?"), self._on_confirm_delete
        )

    def _on_confirm_delete(self, confirmed: bool) -> None:
        if not confirmed:
            return
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.run_worker(self._delete_and_reload(profile.filename), thread=True)

    def _write_and_reload(self, profile: NetworkProfile):
        def _work() -> None:
            status = self.query_one(StatusBar)
            try:
                writer = NetworkFileWriter()
                path = writer.write(profile)
                try:
                    reload_networkd()
                    self.app.call_from_thread(
                        status.set_status, f"Saved and reloaded: {path.name}"
                    )
                except Exception as exc:
                    self.app.call_from_thread(
                        status.set_status,
                        f"Saved {path.name} but reload failed: {exc}",
                        False,
                        True,
                    )
            except NetworkdPermissionError as exc:
                self.app.call_from_thread(status.set_status, str(exc), True)
            except Exception as exc:
                self.app.call_from_thread(status.set_status, f"Error: {exc}", True)
            finally:
                self.app.call_from_thread(self.action_refresh)
                self.app.call_from_thread(
                    self.query_one(InterfaceDetailPanel).refresh_live
                )

        return _work

    def _delete_and_reload(self, filename: str):
        def _work() -> None:
            status = self.query_one(StatusBar)
            try:
                delete_profile(filename)
                try:
                    reload_networkd()
                    self.app.call_from_thread(
                        status.set_status, f"Deleted and reloaded: {filename}"
                    )
                except Exception as exc:
                    self.app.call_from_thread(
                        status.set_status,
                        f"Deleted {filename} but reload failed: {exc}",
                        False,
                        True,
                    )
            except NetworkdPermissionError as exc:
                self.app.call_from_thread(status.set_status, str(exc), True)
            except Exception as exc:
                self.app.call_from_thread(status.set_status, f"Error: {exc}", True)
            finally:
                self.app.call_from_thread(self.action_refresh)
                self.app.call_from_thread(
                    self.query_one(InterfaceDetailPanel).refresh_live
                )

        return _work
