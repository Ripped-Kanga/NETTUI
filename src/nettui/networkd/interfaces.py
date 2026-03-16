from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from nettui.models import InterfaceInfo, NetworkProfile

logger = logging.getLogger(__name__)

_SYS_NET = Path("/sys/class/net")

_ARPHRD_TO_TYPE: dict[str, str] = {
    "1": "ether",
    "772": "loopback",
    "801": "wlan",
    "802": "wlan",
}


def _read_sysfs(iface: str, attr: str, default: str = "") -> str:
    try:
        return (_SYS_NET / iface / attr).read_text(encoding="utf-8").strip()
    except OSError:
        return default


def _carrier(iface: str) -> bool:
    val = _read_sysfs(iface, "carrier", "0")
    return val == "1"


def _iface_type(iface: str) -> str:
    arphrd = _read_sysfs(iface, "type", "")
    return _ARPHRD_TO_TYPE.get(arphrd, "other")


def _networkctl_data() -> dict[str, dict]:
    """Run networkctl --json=short list and return per-interface dict."""
    try:
        result = subprocess.run(
            ["networkctl", "--no-pager", "--json=short", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            # JSON is {"Interfaces": [...]}
            ifaces = data.get("Interfaces", data) if isinstance(data, dict) else data
            return {item["Name"]: item for item in ifaces if "Name" in item}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass

    # Fallback: try plain-text networkctl list
    try:
        result = subprocess.run(
            ["networkctl", "--no-pager", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return _parse_networkctl_text(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {}


def _parse_networkctl_text(output: str) -> dict[str, dict]:
    """Parse plain-text `networkctl list` output as a fallback."""
    result: dict[str, dict] = {}
    for line in output.splitlines():
        parts = line.split()
        # Lines look like: IDX LINK TYPE OPERATIONAL SETUP
        if len(parts) >= 4 and parts[0].isdigit():
            name = parts[1]
            result[name] = {
                "Name": name,
                "Type": parts[2] if len(parts) > 2 else "other",
                "OperationalState": parts[3] if len(parts) > 3 else "unknown",
            }
    return result


class InterfaceScanner:
    def list_interfaces(self) -> list[InterfaceInfo]:
        if not _SYS_NET.exists():
            return []

        nc_data = _networkctl_data()

        interfaces: list[InterfaceInfo] = []
        for entry in _SYS_NET.iterdir():
            name = entry.name
            nc = nc_data.get(name, {})

            itype = nc.get("Type", _iface_type(name)) or _iface_type(name)
            op_state = nc.get("OperationalState", "unknown")
            mac = _read_sysfs(name, "address", "")
            carrier = _carrier(name)

            interfaces.append(
                InterfaceInfo(
                    name=name,
                    type=itype,
                    carrier=carrier,
                    operational_state=op_state,
                    mac_address=mac,
                )
            )

        # Sort: physical first, loopback last, then alphabetically
        def sort_key(i: InterfaceInfo) -> tuple[int, str]:
            order = {"loopback": 2, "ether": 0, "wlan": 0}
            return (order.get(i.type, 1), i.name)

        interfaces.sort(key=sort_key)
        return interfaces


def link_profiles(
    interfaces: list[InterfaceInfo], profiles: list[NetworkProfile]
) -> list[InterfaceInfo]:
    """Populate linked_profiles on each InterfaceInfo."""
    for iface in interfaces:
        iface.linked_profiles = [
            p.filename for p in profiles if p.interface_name == iface.name
        ]
    return interfaces
