from nettui.models import NetworkProfile, ProfileValidationError


def test_is_new():
    p = NetworkProfile(filename="", interface_name="eth0")
    assert p.is_new()
    p2 = NetworkProfile(filename="10-eth0.network", interface_name="eth0")
    assert not p2.is_new()


def test_is_dhcp():
    assert NetworkProfile(filename="", interface_name="eth0", dhcp="yes").is_dhcp()
    assert NetworkProfile(filename="", interface_name="eth0", dhcp="ipv4").is_dhcp()
    assert not NetworkProfile(filename="", interface_name="eth0", dhcp="no").is_dhcp()


def test_display_address_dhcp():
    p = NetworkProfile(filename="", interface_name="eth0", dhcp="ipv4")
    assert "DHCP" in p.display_address()


def test_display_address_static():
    p = NetworkProfile(filename="", interface_name="eth0", addresses=["192.168.1.1/24"])
    assert p.display_address() == "192.168.1.1/24"


def test_display_address_empty():
    p = NetworkProfile(filename="", interface_name="eth0")
    assert p.display_address() == "(none)"


def test_suggested_filename():
    p = NetworkProfile(filename="", interface_name="eth0")
    assert p.suggested_filename() == "10-eth0.network"


def test_suggested_filename_sanitises():
    p = NetworkProfile(filename="", interface_name="my iface")
    assert " " not in p.suggested_filename()


def test_validation_error_str():
    err = ProfileValidationError(field="address", message="invalid CIDR")
    assert "address" in str(err)
    assert "invalid CIDR" in str(err)
