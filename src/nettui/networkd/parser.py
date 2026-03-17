from __future__ import annotations

import logging
from pathlib import Path

from nettui.models import NetworkProfile
from nettui.networkd.exceptions import NetworkdParseError

logger = logging.getLogger(__name__)

NETWORKD_DIR = Path("/etc/systemd/network")

# Simple type alias: section → key → list of values (repeated keys accumulate)
_Sections = dict[str, dict[str, list[str]]]


def _parse_ini(text: str, filename: str = "") -> _Sections:
    """
    Minimal INI parser that accumulates repeated keys into lists.
    Handles [Section], key=value, and # / ; comments.
    """
    sections: _Sections = {}
    current: dict[str, list[str]] | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            end = line.find("]")
            if end == -1:
                raise NetworkdParseError(
                    f"Malformed section header at line {lineno}", filename=filename
                )
            section = line[1:end]
            current = sections.setdefault(section, {})
        elif "=" in line:
            if current is None:
                raise NetworkdParseError(
                    f"Key=value before any section header at line {lineno}", filename=filename
                )
            key, _, value = line.partition("=")
            current.setdefault(key.strip(), []).append(value.strip())
        # Ignore continuation lines and anything else (lenient)
    return sections


def _get_scalar(section: dict[str, list[str]], key: str, default: str = "") -> str:
    """Return last value for key, or default."""
    vals = section.get(key)
    if not vals:
        return default
    return vals[-1]


def _get_list(section: dict[str, list[str]], key: str) -> list[str]:
    """Return all values for key, splitting each on whitespace."""
    result: list[str] = []
    for v in section.get(key, []):
        result.extend(v.split())
    return result


def parse_file(path: Path) -> NetworkProfile:
    """Parse a single .network file and return a NetworkProfile."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise NetworkdParseError(f"File not found: {path}", filename=path.name) from exc

    try:
        sections = _parse_ini(text, filename=path.name)
    except NetworkdParseError:
        raise
    except Exception as exc:
        raise NetworkdParseError(f"Failed to parse {path.name}: {exc}", filename=path.name) from exc

    if "Match" not in sections:
        raise NetworkdParseError(
            f"Missing [Match] section in {path.name}", filename=path.name, field="Match"
        )

    match = sections["Match"]
    interface_name = _get_scalar(match, "Name")
    if not interface_name:
        raise NetworkdParseError(
            f"Missing Name= in [Match] section of {path.name}",
            filename=path.name,
            field="Name",
        )

    net = sections.get("Network", {})
    dhcp = _get_scalar(net, "DHCP", default="no").lower()
    addresses = _get_list(net, "Address")
    gateway = _get_scalar(net, "Gateway")
    dns = _get_list(net, "DNS")
    domains = _get_list(net, "Domains")
    ra_raw = _get_scalar(net, "IPv6AcceptRA", default="yes")
    ipv6_accept_ra = ra_raw.lower() not in ("no", "false", "0")

    # Route metric: check [Route] Metric=, [DHCPv4] RouteMetric=, [DHCPv6] RouteMetric=
    route_section = sections.get("Route", {})
    dhcpv4_section = sections.get("DHCPv4", {})
    dhcpv6_section = sections.get("DHCPv6", {})
    metric_raw = (
        _get_scalar(route_section, "Metric")
        or _get_scalar(dhcpv4_section, "RouteMetric")
        or _get_scalar(dhcpv6_section, "RouteMetric")
    )
    route_metric = int(metric_raw) if metric_raw.isdigit() else 0

    nettui = sections.get("X-Nettui", {})
    description = _get_scalar(nettui, "Description")
    applied_from = _get_scalar(nettui, "AppliedFrom")

    return NetworkProfile(
        filename=path.name,
        interface_name=interface_name,
        dhcp=dhcp,
        addresses=addresses,
        gateway=gateway,
        dns=dns,
        domains=domains,
        ipv6_accept_ra=ipv6_accept_ra,
        route_metric=route_metric,
        description=description,
        applied_from=applied_from,
    )


def load_all(directory: Path | None = None) -> list[NetworkProfile]:
    """Load all *.network files from directory, skipping unparseable ones."""
    d = directory or NETWORKD_DIR
    profiles: list[NetworkProfile] = []
    for path in sorted(d.glob("*.network")):
        try:
            profiles.append(parse_file(path))
        except NetworkdParseError as exc:
            logger.warning("Skipping %s: %s", path.name, exc)
    return profiles
