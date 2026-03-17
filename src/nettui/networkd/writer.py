from __future__ import annotations

import os
from pathlib import Path

from nettui.models import NetworkProfile
from nettui.networkd.exceptions import NetworkdPermissionError
from nettui.networkd.parser import NETWORKD_DIR


def _render_network_file(profile: NetworkProfile) -> str:
    """Serialise a NetworkProfile to .network INI text."""
    lines: list[str] = []

    lines.append("[Match]")
    lines.append(f"Name={profile.interface_name}")
    lines.append("")

    lines.append("[Network]")
    lines.append(f"DHCP={profile.dhcp}")
    lines.append(f"IPv6AcceptRA={'yes' if profile.ipv6_accept_ra else 'no'}")

    for addr in profile.addresses:
        lines.append(f"Address={addr}")

    # Gateway goes in [Network] unless we need a [Route] section for metric
    use_route_section = profile.route_metric and profile.dhcp == "no" and profile.gateway
    if profile.gateway and not use_route_section:
        lines.append(f"Gateway={profile.gateway}")

    for srv in profile.dns:
        lines.append(f"DNS={srv}")

    if profile.domains:
        lines.append(f"Domains={' '.join(profile.domains)}")

    if profile.route_metric and profile.dhcp != "no":
        if profile.dhcp in ("yes", "ipv4"):
            lines.append("")
            lines.append("[DHCPv4]")
            lines.append(f"RouteMetric={profile.route_metric}")
        if profile.dhcp in ("yes", "ipv6"):
            lines.append("")
            lines.append("[DHCPv6]")
            lines.append(f"RouteMetric={profile.route_metric}")

    if use_route_section:
        lines.append("")
        lines.append("[Route]")
        lines.append(f"Gateway={profile.gateway}")
        lines.append(f"Metric={profile.route_metric}")

    if profile.description or profile.applied_from:
        lines.append("")
        lines.append("[X-Nettui]")
        if profile.description:
            lines.append(f"Description={profile.description}")
        if profile.applied_from:
            lines.append(f"AppliedFrom={profile.applied_from}")

    lines.append("")
    return "\n".join(lines)


class NetworkFileWriter:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or NETWORKD_DIR

    def _check_write_permission(self, path: Path) -> None:
        if not os.access(self.directory, os.W_OK):
            raise NetworkdPermissionError(
                f"No write access to {self.directory}. "
                "Try running with sudo or joining the systemd-network group."
            )
        if path.exists() and not os.access(path, os.W_OK):
            raise NetworkdPermissionError(f"No write access to {path}.")

    def write(self, profile: NetworkProfile) -> Path:
        """Write profile to disk atomically. Returns the written path."""
        filename = profile.filename if not profile.is_new() else profile.suggested_filename()
        target = self.directory / filename
        self._check_write_permission(target)

        content = _render_network_file(profile)
        tmp = target.with_suffix(".network.nettui-tmp")
        try:
            tmp.write_text(content, encoding="utf-8")
            os.replace(tmp, target)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

        return target


def delete_profile(filename: str, directory: Path | None = None) -> None:
    """Delete a .network file by name."""
    d = directory or NETWORKD_DIR
    target = d / filename
    if not os.access(d, os.W_OK):
        raise NetworkdPermissionError(
            f"No write access to {d}. Try running with sudo or joining the systemd-network group."
        )
    target.unlink()


def _managed_filename(iface_name: str) -> str:
    """Return the dedicated managed filename for an interface."""
    safe = iface_name.replace("/", "_").replace(" ", "_")
    return f"00-nettui-{safe}.network"


def apply_profile(source: NetworkProfile, directory: Path | None = None) -> Path:
    """Write *source* profile's settings into a dedicated managed file for its interface.

    The managed file uses a ``00-nettui-`` prefix so it always wins priority in
    systemd-networkd.  It carries an ``AppliedFrom=`` tag so the UI can identify it.
    The source profile is not modified on disk.
    Returns the path of the written managed file.
    """
    d = directory or NETWORKD_DIR
    if not os.access(d, os.W_OK):
        raise NetworkdPermissionError(
            f"No write access to {d}. Try running with sudo or joining the systemd-network group."
        )
    managed = _managed_filename(source.interface_name)
    target = d / managed

    applied = NetworkProfile(
        filename=managed,
        interface_name=source.interface_name,
        dhcp=source.dhcp,
        addresses=list(source.addresses),
        gateway=source.gateway,
        dns=list(source.dns),
        domains=list(source.domains),
        ipv6_accept_ra=source.ipv6_accept_ra,
        route_metric=source.route_metric,
        description=source.description,
        applied_from=source.filename,
    )

    content = _render_network_file(applied)
    tmp = target.with_suffix(".network.nettui-tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

    return target
