from nettui.aliases import load_aliases, save_alias
from nettui.models import NetworkProfile
from nettui.networkd.parser import parse_file
from nettui.networkd.writer import (
    NetworkFileWriter,
    _render_network_file,
    update_interface_alias,
)


def test_save_and_load_alias(tmp_path, monkeypatch):
    monkeypatch.setattr("nettui.aliases._CONFIG_DIR", tmp_path)
    monkeypatch.setattr("nettui.aliases._ALIASES_FILE", tmp_path / "aliases.json")

    save_alias("eth0", "Office LAN")
    aliases = load_aliases()
    assert aliases == {"eth0": "Office LAN"}


def test_save_empty_alias_removes(tmp_path, monkeypatch):
    monkeypatch.setattr("nettui.aliases._CONFIG_DIR", tmp_path)
    monkeypatch.setattr("nettui.aliases._ALIASES_FILE", tmp_path / "aliases.json")

    save_alias("eth0", "Office LAN")
    save_alias("eth0", "")
    aliases = load_aliases()
    assert "eth0" not in aliases


def test_load_aliases_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("nettui.aliases._ALIASES_FILE", tmp_path / "nope.json")
    assert load_aliases() == {}


def test_render_interface_alias():
    p = NetworkProfile(
        filename="10-eth0.network",
        interface_name="eth0",
        dhcp="yes",
        interface_alias="Office LAN",
    )
    rendered = _render_network_file(p)
    assert "[X-Nettui]" in rendered
    assert "InterfaceAlias=Office LAN" in rendered


def test_round_trip_interface_alias(tmp_path):
    p = NetworkProfile(
        filename="10-eth0.network",
        interface_name="eth0",
        dhcp="yes",
        interface_alias="Home WiFi",
        description="My config",
    )
    writer = NetworkFileWriter(directory=tmp_path)
    written = writer.write(p)
    reparsed = parse_file(written)
    assert reparsed.interface_alias == "Home WiFi"
    assert reparsed.description == "My config"


def test_update_interface_alias(tmp_path):
    # Create two profiles for eth0 and one for wlan0
    writer = NetworkFileWriter(directory=tmp_path)
    writer.write(NetworkProfile(filename="10-eth0.network", interface_name="eth0", dhcp="yes"))
    writer.write(NetworkProfile(filename="20-eth0.network", interface_name="eth0", dhcp="no"))
    writer.write(NetworkProfile(filename="10-wlan0.network", interface_name="wlan0", dhcp="yes"))

    update_interface_alias("eth0", "Office LAN", directory=tmp_path)

    # eth0 profiles should have the alias
    p1 = parse_file(tmp_path / "10-eth0.network")
    p2 = parse_file(tmp_path / "20-eth0.network")
    assert p1.interface_alias == "Office LAN"
    assert p2.interface_alias == "Office LAN"

    # wlan0 should be unaffected
    p3 = parse_file(tmp_path / "10-wlan0.network")
    assert p3.interface_alias == ""


def test_update_interface_alias_clears(tmp_path):
    writer = NetworkFileWriter(directory=tmp_path)
    writer.write(
        NetworkProfile(
            filename="10-eth0.network",
            interface_name="eth0",
            dhcp="yes",
            interface_alias="Old Name",
        )
    )

    update_interface_alias("eth0", "", directory=tmp_path)

    p = parse_file(tmp_path / "10-eth0.network")
    assert p.interface_alias == ""
