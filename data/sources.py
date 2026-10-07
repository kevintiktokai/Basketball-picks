"""Raw data acquisition: pinned, checksummed downloads.

Nothing is fetched from a moving target. Each source is pinned to a git commit
and verified against a sha256 recorded in config/config.yaml. If a checksum
does not match, ingestion fails loudly.
"""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from config_loader import load_config, ROOT

RAW_DIR = ROOT / "data" / "raw"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_path(name: str) -> Path:
    src = load_config()["sources"][name]
    return RAW_DIR / f"{name}__{Path(src['path']).name}"


def fetch_all(force: bool = False) -> dict[str, Path]:
    cfg = load_config()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, src in cfg["sources"].items():
        dest = raw_path(name)
        if force or not dest.exists():
            url = f"https://raw.githubusercontent.com/{src['repo']}/{src['commit']}/{src['path']}"
            print(f"fetching {name} <- {url}")
            urllib.request.urlretrieve(url, dest)
        digest = _sha256(dest)
        if digest != src["sha256"]:
            raise RuntimeError(
                f"checksum mismatch for {name}: expected {src['sha256']}, got {digest}"
            )
        out[name] = dest
    return out


if __name__ == "__main__":
    for k, v in fetch_all().items():
        print(k, v)
