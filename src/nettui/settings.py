from __future__ import annotations

from dataclasses import dataclass

# Preset destination choices (value → display label)
DEST_GATEWAY = "gateway"
DEST_CLOUDFLARE = "cloudflare"
DEST_CUSTOM1 = "custom1"
DEST_CUSTOM2 = "custom2"

CLOUDFLARE_IP = "1.1.1.1"

GRAPH_LINE = "line"
GRAPH_AREA = "area"


@dataclass
class Settings:
    bw_unit: str = "bytes"  # "bytes" | "bits"
    graph_style: str = GRAPH_LINE  # "line" | "area"
    ping_dest: str = DEST_GATEWAY  # "gateway" | "cloudflare" | "custom1" | "custom2"
    traceroute_dest: str = DEST_CLOUDFLARE
    custom1_addr: str = ""
    custom2_addr: str = ""

    def resolve_target(self, dest: str, gateway: str) -> str:
        """Resolve a destination choice to an IP/hostname."""
        if dest == DEST_GATEWAY:
            return gateway or CLOUDFLARE_IP
        if dest == DEST_CLOUDFLARE:
            return CLOUDFLARE_IP
        if dest == DEST_CUSTOM1:
            return self.custom1_addr or CLOUDFLARE_IP
        if dest == DEST_CUSTOM2:
            return self.custom2_addr or CLOUDFLARE_IP
        return CLOUDFLARE_IP


# Global settings instance — mutated in place by the settings screen.
SETTINGS = Settings()
