import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path, data: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(str(tmp), str(path))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def make_tempfile(suffix=""):
    fd, p = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return p
