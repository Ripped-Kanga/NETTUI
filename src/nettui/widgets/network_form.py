from __future__ import annotations

import ipaddress

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widget import Widget
from textual.widgets import Input, Label, Select, Switch

from nettui.models import NetworkProfile, ProfileValidationError


class NetworkForm(Widget):
    DEFAULT_CSS = """
    NetworkForm {
        height: 1fr;
        overflow-y: auto;
        padding: 1 2;
    }

    .form-row {
        layout: horizontal;
        height: auto;
        margin-bottom: 1;
    }

    .form-label {
        width: 22;
        height: 3;
        content-align: right middle;
        padding-right: 2;
        color: $text-muted;
    }

    .form-field {
        width: 1fr;
    }

    .switch-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }

    .switch-label {
        width: 22;
        height: 3;
        content-align: right middle;
        padding-right: 2;
        color: $text-muted;
    }

    Input.-invalid {
        border: tall $error;
    }

    #form-error {
        color: $error;
        height: 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, profile: NetworkProfile, **kwargs) -> None:
        super().__init__(**kwargs)
        self._profile = profile

    def compose(self) -> ComposeResult:
        p = self._profile
        with ScrollableContainer():
            yield Label("", id="form-error")

            with Vertical(classes="form-row"):
                yield Label("Interface name", classes="form-label")
                yield Input(
                    value=p.interface_name,
                    placeholder="e.g. eth0",
                    id="f-iface",
                    classes="form-field",
                )

            with Vertical(classes="form-row"):
                yield Label("Filename", classes="form-label")
                yield Input(
                    value=p.filename or p.suggested_filename(),
                    placeholder="10-eth0.network",
                    id="f-filename",
                    classes="form-field",
                    disabled=not p.is_new(),
                )

            with Vertical(classes="form-row"):
                yield Label("Description", classes="form-label")
                yield Input(
                    value=p.description,
                    placeholder="Optional label",
                    id="f-desc",
                    classes="form-field",
                )

            with Vertical(classes="form-row"):
                yield Label("DHCP", classes="form-label")
                yield Select(
                    [
                        ("Disabled (static)", "no"),
                        ("IPv4 only", "ipv4"),
                        ("IPv6 only", "ipv6"),
                        ("Both IPv4 & IPv6", "yes"),
                    ],
                    value=p.dhcp,
                    id="f-dhcp",
                    classes="form-field",
                )

            with Vertical(classes="form-row"):
                yield Label("Addresses", classes="form-label")
                yield Input(
                    value=", ".join(p.addresses),
                    placeholder="192.168.1.10/24, 10.0.0.5/8",
                    id="f-addr",
                    classes="form-field",
                    disabled=p.is_dhcp(),
                )

            with Vertical(classes="form-row"):
                yield Label("Gateway", classes="form-label")
                yield Input(
                    value=p.gateway,
                    placeholder="192.168.1.1",
                    id="f-gw",
                    classes="form-field",
                    disabled=p.is_dhcp(),
                )

            with Vertical(classes="form-row"):
                yield Label("DNS servers", classes="form-label")
                yield Input(
                    value=" ".join(p.dns),
                    placeholder="1.1.1.1 8.8.8.8",
                    id="f-dns",
                    classes="form-field",
                    disabled=p.is_dhcp(),
                )

            with Vertical(classes="form-row"):
                yield Label("Search domains", classes="form-label")
                yield Input(
                    value=" ".join(p.domains),
                    placeholder="example.com local",
                    id="f-domains",
                    classes="form-field",
                )

            with Vertical(classes="switch-row"):
                yield Label("IPv6 Accept RA", classes="switch-label")
                yield Switch(value=p.ipv6_accept_ra, id="f-ipv6ra")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "f-dhcp":
            return
        is_static = event.value == "no"
        for fid in ("f-addr", "f-gw", "f-dns"):
            try:
                self.query_one(f"#{fid}", Input).disabled = not is_static
            except Exception:
                pass

    def show_error(self, field_id: str, message: str) -> None:
        self.query_one("#form-error", Label).update(f"Error: {message}")
        try:
            widget = self.query_one(f"#{field_id}")
            widget.add_class("-invalid")
        except Exception:
            pass

    def clear_errors(self) -> None:
        self.query_one("#form-error", Label).update("")
        for w in self.query(".-invalid"):
            w.remove_class("-invalid")

    def collect(self) -> NetworkProfile:
        """Read all fields and return a NetworkProfile, raising ProfileValidationError on bad input."""
        self.clear_errors()

        iface = self.query_one("#f-iface", Input).value.strip()
        if not iface:
            raise ProfileValidationError(field="f-iface", message="Interface name is required")
        if " " in iface:
            raise ProfileValidationError(
                field="f-iface", message="Interface name must not contain spaces"
            )

        filename_input = self.query_one("#f-filename", Input).value.strip()
        if not filename_input.endswith(".network"):
            raise ProfileValidationError(
                field="f-filename", message="Filename must end with .network"
            )
        if "/" in filename_input or "\\" in filename_input:
            raise ProfileValidationError(
                field="f-filename", message="Filename must not contain path separators"
            )

        dhcp_select = self.query_one("#f-dhcp", Select)
        dhcp = str(dhcp_select.value) if dhcp_select.value is not Select.BLANK else "no"

        addresses: list[str] = []
        gateway = ""
        dns: list[str] = []

        if dhcp == "no":
            raw_addr = self.query_one("#f-addr", Input).value.strip()
            if raw_addr:
                for part in raw_addr.split(","):
                    cidr = part.strip()
                    if not cidr:
                        continue
                    try:
                        ipaddress.ip_interface(cidr)
                    except ValueError:
                        raise ProfileValidationError(
                            field="f-addr", message=f"'{cidr}' is not a valid CIDR address"
                        )
                    addresses.append(cidr)

            raw_gw = self.query_one("#f-gw", Input).value.strip()
            if raw_gw:
                try:
                    ipaddress.ip_address(raw_gw)
                    gateway = raw_gw
                except ValueError:
                    raise ProfileValidationError(
                        field="f-gw", message=f"'{raw_gw}' is not a valid IP address"
                    )

            raw_dns = self.query_one("#f-dns", Input).value.strip()
            if raw_dns:
                for token in raw_dns.split():
                    try:
                        ipaddress.ip_address(token)
                        dns.append(token)
                    except ValueError:
                        raise ProfileValidationError(
                            field="f-dns", message=f"'{token}' is not a valid DNS server IP"
                        )

        raw_domains = self.query_one("#f-domains", Input).value.strip()
        domains = raw_domains.split() if raw_domains else []

        ipv6_accept_ra = self.query_one("#f-ipv6ra", Switch).value
        description = self.query_one("#f-desc", Input).value.strip()

        # Determine filename: if existing file, keep original; if new, use form value
        orig_filename = self._profile.filename
        filename = orig_filename if orig_filename else filename_input

        return NetworkProfile(
            filename=filename,
            interface_name=iface,
            dhcp=dhcp,
            addresses=addresses,
            gateway=gateway,
            dns=dns,
            domains=domains,
            ipv6_accept_ra=ipv6_accept_ra,
            description=description,
        )
