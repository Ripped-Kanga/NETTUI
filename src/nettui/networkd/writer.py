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

    if profile.gateway:
        lines.append(f"Gateway={profile.gateway}")

    for srv in profile.dns:
        lines.append(f"DNS={srv}")

    if profile.domains:
        lines.append(f"Domains={' '.join(profile.domains)}")

    if profile.description:
        lines.append("")
        lines.append("[X-Nettui]")
        lines.append(f"Description={profile.description}")

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
            f"No write access to {d}. "
            "Try running with sudo or joining the systemd-network group."
        )
    target.unlink()
