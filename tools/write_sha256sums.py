from __future__ import annotations

import argparse
from pathlib import Path

from fuckmark.hashing import sha256_file

SKIP_NAMES = {"run.log", "SHA256SUMS.txt", "SHA256SUMS"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    root = Path(args.dir)
    names = args.only or [
        path.name
        for path in sorted(root.iterdir())
        if path.is_file() and path.name not in SKIP_NAMES
    ]
    lines = [f"{sha256_file(root / name)}  {name}" for name in names]
    (root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
