from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from nettui.aliases import load_aliases, save_alias
from nettui.models import InterfaceInfo, NetworkProfile
from nettui.networkd import (
    InterfaceScanner,
    NetworkdPermissionError,
    NetworkFileWriter,
    apply_profile,
    delete_profile,
    link_profiles,
    load_all,
    reload_networkd,
    update_interface_alias,
)
from nettui.networkd.parser import NETWORKD_DIR
from nettui.screens.alias_editor import AliasEditorDialog
from nettui.screens.confirm_dialog import ConfirmDialog
from nettui.screens.connection_editor import ConnectionEditorScreen
from nettui.screens.diagnostic_screen import DiagnosticScreen
from nettui.screens.settings_screen import SettingsScreen
from nettui.widgets.interface_detail import BandwidthGraphPanel, InterfaceDetailPanel
from nettui.widgets.interface_table import InterfaceTable
from nettui.widgets.profile_table import ProfileTable
from nettui.widgets.status_bar import StatusBar


class InterfaceListScreen(Screen):
    CSS_PATH = "interface_list.tcss"

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("ctrl+e", "edit_alias", "Edit Alias"),
        Binding("n", "new_profile", "New Profile"),
        Binding("e", "edit_profile", "Edit Profile"),
        Binding("d", "delete_profile", "Delete Profile"),
        Binding("a", "activate_profile", "Activate Profile"),
        Binding("s", "settings", "Settings"),
        Binding("p", "ping", "Ping"),
        Binding("t", "traceroute", "Traceroute"),
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
            with Vertical(id="profile-panel"):
                yield ProfileTable(id="profile-table")
                yield BandwidthGraphPanel(id="bw-graph")
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
            # Populate interface aliases from config
            aliases = load_aliases()
            for iface in interfaces:
                iface.alias = aliases.get(iface.name, "")
            # Fetch active profile info for the selected (or first) interface
            iface_name = (
                self._selected_interface.name
                if self._selected_interface
                else (interfaces[0].name if interfaces else "")
            )
            # Find the applied_from tag from any managed file for this interface
            applied_from = ""
            if iface_name:
                for p in profiles:
                    if p.interface_name == iface_name and p.applied_from:
                        applied_from = p.applied_from
                        break
            self.app.call_from_thread(
                self._update_interface_table, interfaces, profiles, applied_from
            )
        except Exception as exc:
            self.app.call_from_thread(
                self.query_one(StatusBar).set_status,
                f"Error loading interfaces: {exc}",
                True,
            )

    def _update_interface_table(
        self,
        interfaces: list[InterfaceInfo],
        profiles: list[NetworkProfile],
        applied_from: str = "",
    ) -> None:
        iface_table = self.query_one(InterfaceTable)
        prev_name = self._selected_interface.name if self._selected_interface else None

        # Suppress highlight events while repopulating.
        # Textual queues RowHighlighted messages that fire AFTER this method returns,
        # so we defer turning off the flag to let those stale events drain first.
        self._suppress_highlight = True
        iface_table.load(interfaces)

        # Restore cursor to previously selected interface
        if prev_name:
            iface_table.select_by_name(prev_name)
            # Update _selected_interface with refreshed data (new profile counts etc.)
            self._selected_interface = next((i for i in interfaces if i.name == prev_name), None)

        # Refresh the detail and profile panels using already-loaded profiles.
        # Exclude profiles with applied_from set — those are managed active files,
        # not user templates.
        if self._selected_interface is not None:
            self.query_one(InterfaceDetailPanel).load_interface(self._selected_interface)
            self.query_one(BandwidthGraphPanel).load_interface(self._selected_interface.name)
            iface_profiles = [
                p
                for p in profiles
                if p.interface_name == self._selected_interface.name and not p.applied_from
            ]
            self.query_one(ProfileTable).load(iface_profiles)

        self.query_one(ProfileTable).update_active_label(applied_from)

        # Turn off suppress after queued highlight events have been processed
        self.set_timer(0.1, self._enable_highlight)

    def _enable_highlight(self) -> None:
        self._suppress_highlight = False

    def _load_profiles_for(self, interface: InterfaceInfo) -> None:
        self.run_worker(
            lambda: self._fetch_profiles(interface.name),
            thread=True,
            group="profile-load",
            exclusive=True,
        )

    def _fetch_profiles(self, iface_name: str) -> None:
        all_profiles = [p for p in load_all() if p.interface_name == iface_name]
        # Find the applied_from tag from the managed active file
        applied_from = ""
        for p in all_profiles:
            if p.applied_from:
                applied_from = p.applied_from
                break
        # Exclude profiles with applied_from — those are managed active files
        profiles = [p for p in all_profiles if not p.applied_from]
        self.app.call_from_thread(self.query_one(ProfileTable).load, profiles)
        self.app.call_from_thread(self.query_one(ProfileTable).update_active_label, applied_from)

    # ── Interface selection ───────────────────────────────────────────────────

    def on_interface_table_highlighted(self, event: InterfaceTable.Highlighted) -> None:
        if self._suppress_highlight:
            return
        self._selected_interface = event.interface
        self.query_one(InterfaceDetailPanel).load_interface(event.interface)
        self.query_one(BandwidthGraphPanel).load_interface(event.interface.name)
        self._load_profiles_for(event.interface)

    def on_interface_table_selected(self, event: InterfaceTable.Selected) -> None:
        """Enter on interface row — move focus to profile table."""
        self._selected_interface = event.interface
        self.query_one(ProfileTable).query_one("DataTable").focus()

    # ── Profile actions ───────────────────────────────────────────────────────

    def action_new_profile(self) -> None:
        if self._selected_interface is None:
            self.query_one(StatusBar).set_status("Select an interface first.", warning=True)
            return
        blank = NetworkProfile(
            filename="", interface_name=self._selected_interface.name, dhcp="yes"
        )
        self.app.push_screen(ConnectionEditorScreen(profile=blank), self._on_editor_result)

    def action_edit_profile(self) -> None:
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.app.push_screen(ConnectionEditorScreen(profile=profile), self._on_editor_result)

    def on_profile_table_selected(self, event: ProfileTable.Selected) -> None:
        self.app.push_screen(ConnectionEditorScreen(profile=event.profile), self._on_editor_result)

    def action_delete_profile(self) -> None:
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.app.push_screen(
            ConfirmDialog(f"Delete '{profile.filename}'?"), self._on_confirm_delete
        )

    def action_activate_profile(self) -> None:
        if self._selected_interface is None:
            self.query_one(StatusBar).set_status("Select an interface first.", warning=True)
            return
        profile = self.query_one(ProfileTable).highlighted_profile()
        if profile is None:
            return
        self.run_worker(
            self._activate_and_reload(profile),
            thread=True,
        )

    def _activate_and_reload(self, source: NetworkProfile):
        def _work() -> None:
            status = self.query_one(StatusBar)
            try:
                path = apply_profile(source)
                try:
                    reload_networkd()
                    self.app.call_from_thread(
                        status.set_status,
                        f"Applied {source.filename} → {path.name}",
                    )
                except Exception as exc:
                    self.app.call_from_thread(
                        status.set_status,
                        f"Applied {source.filename} but reload failed: {exc}",
                        False,
                        True,
                    )
            except NetworkdPermissionError as exc:
                self.app.call_from_thread(
                    status.set_status,
                    f"Permission denied: {exc}. Try running with sudo.",
                    True,
                )
            except Exception as exc:
                self.app.call_from_thread(status.set_status, f"Error: {exc}", True)
                return
            self.app.call_from_thread(self.action_refresh)
            self.app.call_from_thread(self.query_one(InterfaceDetailPanel).refresh_live)

        return _work

    # ── Alias editing ──────────────────────────────────────────────────────

    def action_edit_alias(self) -> None:
        if self._selected_interface is None:
            self.query_one(StatusBar).set_status("Select an interface first.", warning=True)
            return
        iface = self._selected_interface
        self.app.push_screen(
            AliasEditorDialog(iface.name, iface.alias),
            self._on_alias_result,
        )

    def _on_alias_result(self, alias: str | None) -> None:
        if alias is None:
            return
        if self._selected_interface is None:
            return
        iface_name = self._selected_interface.name
        self.run_worker(self._save_alias(iface_name, alias), thread=True)

    def _save_alias(self, iface_name: str, alias: str):
        def _work() -> None:
            status = self.query_one(StatusBar)
            try:
                save_alias(iface_name, alias)
                # Update [X-Nettui] InterfaceAlias= in all templates for this interface
                if self._can_write:
                    update_interface_alias(iface_name, alias)
                label = f"'{alias}'" if alias else "removed"
                self.app.call_from_thread(
                    status.set_status,
                    f"Alias {label} for {iface_name}",
                )
            except NetworkdPermissionError as exc:
                # Alias saved locally but templates couldn't be updated
                self.app.call_from_thread(
                    status.set_status,
                    f"Alias saved locally but templates not updated: {exc}",
                    False,
                    True,
                )
            except Exception as exc:
                self.app.call_from_thread(status.set_status, f"Error: {exc}", True)
            self.app.call_from_thread(self.action_refresh)

        return _work

    # ── Settings / diagnostics ─────────────────────────────────────────────

    def action_settings(self) -> None:
        def _after(_: None) -> None:
            self.query_one(InterfaceDetailPanel)._rebuild_display()
            self.query_one(BandwidthGraphPanel)._rebuild()

        self.app.push_screen(SettingsScreen(), _after)

    def _diagnostic_target(self, dest_setting: str) -> str:
        """Resolve a destination setting to an IP/hostname using live gateway."""
        from nettui.settings import SETTINGS

        gateway = self.query_one(InterfaceDetailPanel)._live.get("gateway", "")
        return SETTINGS.resolve_target(dest_setting, gateway)

    def action_ping(self) -> None:
        from nettui.settings import SETTINGS

        if self._selected_interface is None:
            self.query_one(StatusBar).set_status("Select an interface first.", warning=True)
            return
        iface = self._selected_interface.name
        target = self._diagnostic_target(SETTINGS.ping_dest)
        self.app.push_screen(
            DiagnosticScreen(
                ["ping", "-c", "10", "-I", iface, target],
                title=f"Ping {target} via {iface}",
            )
        )

    def action_traceroute(self) -> None:
        from nettui.settings import SETTINGS

        if self._selected_interface is None:
            self.query_one(StatusBar).set_status("Select an interface first.", warning=True)
            return
        iface = self._selected_interface.name
        target = self._diagnostic_target(SETTINGS.traceroute_dest)
        self.app.push_screen(
            DiagnosticScreen(
                ["traceroute", "-i", iface, target],
                title=f"Traceroute to {target} via {iface}",
            )
        )

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
                    self.app.call_from_thread(status.set_status, f"Saved and reloaded: {path.name}")
                except Exception as exc:
                    self.app.call_from_thread(
                        status.set_status,
                        f"Saved {path.name} but reload failed: {exc}",
                        False,
                        True,
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
                self.app.call_from_thread(self.query_one(InterfaceDetailPanel).refresh_live)

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
                        False,
                        True,
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
