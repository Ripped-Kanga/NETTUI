from pathlib import Path

import pytest

from nettui.networkd.exceptions import NetworkdParseError
from nettui.networkd.parser import load_all, parse_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_static():
    profile = parse_file(FIXTURES / "static.network")
    assert profile.filename == "static.network"
    assert profile.interface_name == "eth0"
    assert profile.dhcp == "no"
    assert "192.168.1.10/24" in profile.addresses
    assert "10.0.0.5/8" in profile.addresses
    assert profile.gateway == "192.168.1.1"
    assert "1.1.1.1" in profile.dns
    assert "8.8.8.8" in profile.dns
    assert "example.com" in profile.domains
    assert "local" in profile.domains
    assert profile.ipv6_accept_ra is False
    assert profile.description == "Home static config"
    assert profile.route_metric == 100


def test_parse_dhcp():
    profile = parse_file(FIXTURES / "dhcp.network")
    assert profile.interface_name == "wlan0"
    assert profile.dhcp == "yes"
    assert profile.ipv6_accept_ra is True
    assert profile.description == "WiFi DHCP"
    assert profile.addresses == []
    assert profile.gateway == ""
    assert profile.route_metric == 0


def test_parse_missing_file():
    with pytest.raises(NetworkdParseError):
        parse_file(Path("/nonexistent/path/foo.network"))


def test_parse_missing_match_section(tmp_path):
    bad = tmp_path / "bad.network"
    bad.write_text("[Network]\nDHCP=yes\n")
    with pytest.raises(NetworkdParseError, match="Match"):
        parse_file(bad)


def test_parse_missing_name(tmp_path):
    bad = tmp_path / "bad.network"
    bad.write_text("[Match]\n\n[Network]\nDHCP=yes\n")
    with pytest.raises(NetworkdParseError, match="Name"):
        parse_file(bad)


def test_parse_dhcp_route_metric(tmp_path):
    f = tmp_path / "dhcp-metric.network"
    f.write_text("[Match]\nName=eth0\n\n[Network]\nDHCP=yes\n\n[DHCPv4]\nRouteMetric=600\n")
    profile = parse_file(f)
    assert profile.route_metric == 600


def test_load_all_skips_unparseable(tmp_path):
    good = tmp_path / "good.network"
    good.write_text("[Match]\nName=eth0\n\n[Network]\nDHCP=yes\n")
    bad = tmp_path / "bad.network"
    bad.write_text("not an ini file at all!!!\n")
    profiles = load_all(tmp_path)
    assert len(profiles) == 1
    assert profiles[0].interface_name == "eth0"


def test_load_all_empty_dir(tmp_path):
    assert load_all(tmp_path) == []
