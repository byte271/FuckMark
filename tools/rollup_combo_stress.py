from __future__ import annotations

import argparse
from pathlib import Path

from fuckmark.cycle8.combo_stress import (
    CYCLE8_COMBO_STRESS_N192_PATH,
    write_combo_stress_n192_scorecard,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=CYCLE8_COMBO_STRESS_N192_PATH)
    args = parser.parse_args()
    destination = write_combo_stress_n192_scorecard(Path(args.out))
    print("wrote", destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
