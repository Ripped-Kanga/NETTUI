from unittest.mock import MagicMock, patch

from nettui.models import InterfaceInfo, NetworkProfile
from nettui.networkd.interfaces import InterfaceScanner, link_profiles


def _mock_sysfs(entries: dict[str, dict[str, str]]):
    """Build a mock /sys/class/net directory with given interface attrs."""
    iface_paths = []
    for name in entries:
        mock_entry = MagicMock()
        mock_entry.name = name
        iface_paths.append(mock_entry)
    return iface_paths


def test_link_profiles_exact_match():
    ifaces = [
        InterfaceInfo("eth0", "ether", True, "routable", "aa:bb:cc:dd:ee:ff"),
        InterfaceInfo("wlan0", "wlan", False, "off", "11:22:33:44:55:66"),
    ]
    profiles = [
        NetworkProfile(filename="10-eth0.network", interface_name="eth0"),
        NetworkProfile(filename="20-wlan0.network", interface_name="wlan0"),
        NetworkProfile(filename="30-other.network", interface_name="eth1"),
    ]
    result = link_profiles(ifaces, profiles)
    assert result[0].linked_profiles == ["10-eth0.network"]
    assert result[1].linked_profiles == ["20-wlan0.network"]


def test_link_profiles_no_match():
    ifaces = [InterfaceInfo("eth0", "ether", True, "routable", "")]
    profiles = [NetworkProfile(filename="10-wlan.network", interface_name="wlan0")]
    result = link_profiles(ifaces, profiles)
    assert result[0].linked_profiles == []


def test_list_interfaces_no_sysfs():
    with patch("nettui.networkd.interfaces._SYS_NET") as mock_path:
        mock_path.exists.return_value = False
        scanner = InterfaceScanner()
        result = scanner.list_interfaces()
        assert result == []


def test_list_interfaces_sorts_loopback_last():
    ifaces = [
        InterfaceInfo("lo", "loopback", True, "carrier", "00:00:00:00:00:00"),
        InterfaceInfo("eth0", "ether", True, "routable", "aa:bb:cc:dd:ee:ff"),
    ]

    def sort_key(i: InterfaceInfo):
        order = {"loopback": 2, "ether": 0, "wlan": 0}
        return (order.get(i.type, 1), i.name)

    sorted_ifaces = sorted(ifaces, key=sort_key)
    assert sorted_ifaces[0].name == "eth0"
    assert sorted_ifaces[-1].name == "lo"
