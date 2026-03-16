class NettuilError(Exception):
    """Base exception for all NETTUI errors."""


class NetworkdPermissionError(NettuilError):
    """Cannot write to /etc/systemd/network/."""


class NetworkdParseError(NettuilError):
    """Malformed .network file."""

    def __init__(self, message: str, filename: str = "", field: str = "") -> None:
        super().__init__(message)
        self.filename = filename
        self.field = field


class NetworkdReloadError(NettuilError):
    """networkctl reload failed."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class InterfaceNotFoundError(NettuilError):
    """Network interface no longer exists."""
