from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable

from nettui.models import InterfaceInfo

_STATE_COLOURS = {
    "routable": "green",
    "degraded": "yellow",
    "no-carrier": "red",
    "off": "red",
    "dormant": "yellow",
    "carrier": "cyan",
}


def _state_text(state: str) -> Text:
    colour = _STATE_COLOURS.get(state, "white")
    return Text(state, style=colour)


def _carrier_text(carrier: bool) -> Text:
    return Text("●" if carrier else "○", style="green" if carrier else "red")


class InterfaceTable(Widget):
    BORDER_TITLE = "Interfaces"

    class Selected(Message):
        def __init__(self, interface: InterfaceInfo) -> None:
            self.interface = interface
            super().__init__()

    class Highlighted(Message):
        def __init__(self, interface: InterfaceInfo) -> None:
            self.interface = interface
            super().__init__()

    DEFAULT_CSS = """
    InterfaceTable {
        height: 1fr;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._interfaces: dict[str, InterfaceInfo] = {}

    def compose(self) -> ComposeResult:
        table: DataTable = DataTable(cursor_type="row", zebra_stripes=True)
        yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Interface", "Type", "State", "Carrier", "Profiles")

    def load(self, interfaces: list[InterfaceInfo]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._interfaces = {}
        for iface in interfaces:
            self._interfaces[iface.name] = iface
            table.add_row(
                iface.name,
                iface.type,
                _state_text(iface.operational_state),
                _carrier_text(iface.carrier),
                str(len(iface.linked_profiles)),
                key=iface.name,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = str(event.row_key.value)
        if key in self._interfaces:
            self.post_message(InterfaceTable.Selected(self._interfaces[key]))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None:
            return
        key = str(event.row_key.value)
        if key in self._interfaces:
            self.post_message(InterfaceTable.Highlighted(self._interfaces[key]))

    def select_by_name(self, name: str) -> None:
        """Move the cursor to the row matching the given interface name."""
        table = self.query_one(DataTable)
        for i, row_key in enumerate(table.rows):
            if str(row_key.value) == name:
                table.move_cursor(row=i)
                return

    def highlighted_interface(self) -> InterfaceInfo | None:
        table = self.query_one(DataTable)
        if table.cursor_row < 0:
            return None
        try:
            row_key, _ = table.coordinate_to_cell_key(
                table.cursor_coordinate  # type: ignore[arg-type]
            )
            return self._interfaces.get(str(row_key.value))
        except Exception:
            return None
