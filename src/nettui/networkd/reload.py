from __future__ import annotations

import subprocess

from nettui.networkd.exceptions import NetworkdReloadError


def reload_networkd() -> None:
    """Run networkctl reload to apply changed .network files."""
    try:
        result = subprocess.run(
            ["networkctl", "reload"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise NetworkdReloadError(
                f"networkctl reload failed (exit {result.returncode})",
                stderr=result.stderr,
            )
    except FileNotFoundError as exc:
        raise NetworkdReloadError(
            "networkctl not found — is systemd-networkd installed?"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise NetworkdReloadError("networkctl reload timed out") from exc
