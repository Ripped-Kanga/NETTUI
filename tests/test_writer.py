import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nettui.models import NetworkProfile
from nettui.networkd.exceptions import NetworkdPermissionError
from nettui.networkd.parser import parse_file
from nettui.networkd.writer import NetworkFileWriter, delete_profile, _render_network_file


def _static_profile() -> NetworkProfile:
    return NetworkProfile(
        filename="10-eth0.network",
        interface_name="eth0",
        dhcp="no",
        addresses=["192.168.1.10/24"],
        gateway="192.168.1.1",
        dns=["1.1.1.1", "8.8.8.8"],
        domains=["example.com"],
        ipv6_accept_ra=False,
        description="Test profile",
    )


def test_render_contains_required_sections():
    rendered = _render_network_file(_static_profile())
    assert "[Match]" in rendered
    assert "[Network]" in rendered
    assert "Name=eth0" in rendered
    assert "DHCP=no" in rendered
    assert "Address=192.168.1.10/24" in rendered
    assert "Gateway=192.168.1.1" in rendered
    assert "DNS=1.1.1.1" in rendered
    assert "DNS=8.8.8.8" in rendered
    assert "[X-Nettui]" in rendered
    assert "Description=Test profile" in rendered


def test_render_no_x_nettui_when_no_description():
    p = _static_profile()
    p.description = ""
    rendered = _render_network_file(p)
    assert "[X-Nettui]" not in rendered


def test_write_and_round_trip(tmp_path):
    profile = _static_profile()
    writer = NetworkFileWriter(directory=tmp_path)
    written = writer.write(profile)
    assert written.exists()

    reparsed = parse_file(written)
    assert reparsed.interface_name == profile.interface_name
    assert reparsed.dhcp == profile.dhcp
    assert reparsed.addresses == profile.addresses
    assert reparsed.gateway == profile.gateway
    assert set(reparsed.dns) == set(profile.dns)
    assert reparsed.description == profile.description


def test_write_new_profile_uses_suggested_filename(tmp_path):
    profile = NetworkProfile(filename="", interface_name="eth0", dhcp="yes")
    writer = NetworkFileWriter(directory=tmp_path)
    written = writer.write(profile)
    assert written.name == profile.suggested_filename()


def test_write_permission_denied(tmp_path):
    profile = _static_profile()
    with patch("nettui.networkd.writer.os.access", return_value=False):
        writer = NetworkFileWriter(directory=tmp_path)
        with pytest.raises(NetworkdPermissionError):
            writer.write(profile)


def test_delete_profile(tmp_path):
    target = tmp_path / "10-eth0.network"
    target.write_text("[Match]\nName=eth0\n")
    delete_profile("10-eth0.network", directory=tmp_path)
    assert not target.exists()


def test_delete_profile_permission_denied(tmp_path):
    with patch("nettui.networkd.writer.os.access", return_value=False):
        with pytest.raises(NetworkdPermissionError):
            delete_profile("10-eth0.network", directory=tmp_path)
