"""Is there a newer Calculon? Reads GitHub's latest-release reply; no Qt, no network here."""

import json
import re
from dataclasses import dataclass
from typing import Literal

from . import __repo__

# GitHub leaves drafts and pre-releases out of this one
LATEST_URL = f"https://api.github.com/repos/{__repo__}/releases/latest"
MAX_BYTES = 1_000_000


@dataclass(frozen=True)
class Newer:
    version: str  # "0.5.0"

    @property
    def url(self) -> str:
        return f"https://github.com/{__repo__}/releases/tag/v{self.version}"


type Result = Newer | Literal["up_to_date", "failed"]


def version_key(text: str) -> tuple[int, int, int] | None:
    """(0, 10, 0) from "v0.10.0", "0.10.0" or "0.10.0.dev0+..."; None if it has no X.Y.Z."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", text)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def read_latest(body: bytes, current: str) -> Result:
    """What GitHub's latest-release reply means for the version running now."""
    try:
        tag = json.loads(body)["tag_name"]
    except ValueError, KeyError, TypeError:
        return "failed"
    latest = version_key(tag) if isinstance(tag, str) else None
    now = version_key(current)
    if latest is None or now is None:
        return "failed"
    if latest <= now:
        return "up_to_date"
    return Newer(".".join(map(str, latest)))
