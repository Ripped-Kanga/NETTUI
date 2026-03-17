from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static

from nettui.models import NetworkProfile


class ProfileTable(Widget):
    BORDER_TITLE = "Profiles"

    class Selected(Message):
        def __init__(self, profile: NetworkProfile) -> None:
            self.profile = profile
            super().__init__()

    DEFAULT_CSS = """
    ProfileTable {
        height: 1fr;
    }

    #active-profile-label {
        height: 1;
        padding: 0 1;
        color: $text;
        text-style: bold;
        background: $primary 15%;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._profiles: dict[str, NetworkProfile] = {}

    def compose(self) -> ComposeResult:
        yield Static("Active Profile: —", id="active-profile-label")
        yield DataTable(cursor_type="row", zebra_stripes=True)

    def update_active_label(self, applied_from: str) -> None:
        label = self.query_one("#active-profile-label", Static)
        if applied_from:
            display = applied_from
            if display.endswith(".network"):
                display = display[: -len(".network")]
            label.update(f"● Active Profile: {display}")
        else:
            label.update("Active Profile: —")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("File", "Mode", "Address", "DNS", "Gateway", "Metric")

    def load(self, profiles: list[NetworkProfile]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._profiles = {}
        for p in profiles:
            self._profiles[p.filename] = p
            dns_display = str(len(p.dns)) + " server(s)" if p.dns else "—"
            table.add_row(
                p.filename,
                "DHCP" if p.is_dhcp() else "Static",
                p.display_address(),
                dns_display,
                p.gateway or "—",
                str(p.route_metric) if p.route_metric else "—",
                key=p.filename,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        if key in self._profiles:
            self.post_message(ProfileTable.Selected(self._profiles[key]))

    def highlighted_profile(self) -> NetworkProfile | None:
        table = self.query_one(DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(
                table.cursor_coordinate  # type: ignore[arg-type]
            )
            return self._profiles.get(str(row_key.value))
        except Exception:
            return None
