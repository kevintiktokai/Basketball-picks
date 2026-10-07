"""Shared config access and experiment logging."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=None)
def load_config() -> dict:
    with open(ROOT / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


def season_period(season: str) -> str:
    for period, seasons in load_config()["periods"].items():
        if season in seasons:
            return period
    raise KeyError(season)


def git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def log_experiment(name: str, params: dict, results: dict) -> Path:
    """Write a reproducibility record: timestamp, dataset/model version, params, results."""
    cfg = load_config()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record = {
        "experiment": name,
        "timestamp_utc": stamp,
        "dataset_version": cfg["dataset_version"],
        "code_revision": git_revision(),
        "params": params,
        "params_hash": hashlib.sha256(
            json.dumps(params, sort_keys=True, default=str).encode()
        ).hexdigest()[:12],
        "results": results,
    }
    out_dir = ROOT / "reports" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stamp}_{name}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    return path
