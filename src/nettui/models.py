from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InterfaceInfo:
    name: str
    type: str  # "ether", "wlan", "loopback", "other"
    carrier: bool
    operational_state: str  # "routable", "degraded", "off", "unknown", etc.
    mac_address: str
    linked_profiles: list[str] = field(default_factory=list)
    alias: str = ""


@dataclass
class NetworkProfile:
    filename: str  # basename e.g. "20-eth0.network"; empty string for new profiles
    interface_name: str
    dhcp: str = "no"  # "yes", "no", "ipv4", "ipv6"
    addresses: list[str] = field(default_factory=list)
    gateway: str = ""
    dns: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    ipv6_accept_ra: bool = True
    route_metric: int = 0  # 0 means unset (use networkd default)
    description: str = ""
    applied_from: str = ""  # source profile filename, set when activated via nettui
    interface_alias: str = ""  # alias for the interface, stored in [X-Nettui]

    def is_new(self) -> bool:
        return self.filename == ""

    def is_dhcp(self) -> bool:
        return self.dhcp != "no"

    def display_address(self) -> str:
        if self.is_dhcp():
            return f"DHCP ({self.dhcp})"
        if self.addresses:
            return self.addresses[0]
        return "(none)"

    def suggested_filename(self) -> str:
        safe = self.interface_name.replace("/", "_").replace(" ", "_")
        return f"10-{safe}.network"


@dataclass
class ProfileValidationError(Exception):
    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"
