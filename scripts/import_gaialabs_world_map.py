#!/usr/bin/env python3
"""Prepare the verified GaiaLabs collision data for Original Companion."""

import argparse
import hashlib
from pathlib import Path
import subprocess


REVISION = "754d3bfbb0f4452fb33ac0a1c3eb8304ebb0e2cc"
ASSET = "modules/walkable-world-map/walkable_map_collision.raw.bin"
SHA256 = "ef5d12e71f00725eecef1747a8093bed20f993b4c4c681921a9f2275251abcbb"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="local IOGRetranslation Git checkout")
    parser.add_argument("output", type=Path, help="new output path inside .local")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / ".local").resolve()):
        parser.error("output must be inside the project's .local directory")

    data = subprocess.check_output(
        ("git", "-C", str(args.checkout.resolve()), "show", f"{REVISION}:{ASSET}")
    )
    if len(data) != 2048 or hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("unexpected GaiaLabs world-map collision asset")
    with output.open("xb") as stream:
        stream.write(data)
    print(f"Prepared {output.name} from {REVISION} ({SHA256})")


if __name__ == "__main__":
    main()
