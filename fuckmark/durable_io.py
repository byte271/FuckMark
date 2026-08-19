from __future__ import annotations

import os
from pathlib import Path

from .config import canonical_json_text


def write_canonical_json_fsynced(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json_text(value))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if os.name == "posix":
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
