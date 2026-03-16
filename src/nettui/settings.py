from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    bw_unit: str = "bytes"  # "bytes" | "bits"


# Global settings instance — mutated in place by the settings screen.
SETTINGS = Settings()
