"""Write calculon/_version.py and print the version.

With a tag like v1.2.3 the version is 1.2.3. Without one (manual CI runs, local
test builds) it is 0.0.0.dev0+<git describe>, so test builds are easy to spot.

Usage: python scripts/write_version.py [vX.Y.Z]
"""

import re
import subprocess
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent.parent / "calculon" / "_version.py"


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else ""
    m = re.fullmatch(r"v(\d+\.\d+\.\d+)", ref)
    if ref and not m:
        print(f"not a release tag: {ref!r} (expected vX.Y.Z)", file=sys.stderr)
        return 1
    if m:
        version = m.group(1)
    else:
        try:
            desc = subprocess.run(
                ["git", "describe", "--tags", "--always", "--dirty"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except OSError, subprocess.CalledProcessError:
            desc = "unknown"
        version = "0.0.0.dev0+" + re.sub(r"[^A-Za-z0-9.]+", ".", desc).strip(".")
    TARGET.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
