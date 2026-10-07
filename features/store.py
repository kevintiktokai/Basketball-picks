"""Feature store + walk-forward cache: compute once, reuse everywhere.

* Features are saved per league under data/processed/store/, keyed by a fingerprint of
  the input games and box scores. Any script (research or live) asking for the same
  data gets the stored file instantly; when new games arrive, completed seasons are
  reused and only the newest seasons are recomputed (values are identical because the
  rating window never reaches two seasons back and all team histories restart each
  season — see models/live_ncaab.cached_features).
* Walk-forward predictions + calibrators are cached by (engine spec, feature fingerprint).

Raw downloads were already cached and checksummed in data/raw/; nothing is re-fetched.
"""
from __future__ import annotations

import hashlib
import json
import pickle

import pandas as pd

from config_loader import ROOT
from features.ncaab_features import build_ncaab_features

STORE = ROOT / "data" / "processed" / "store"


def fingerprint(games: pd.DataFrame, box: pd.DataFrame | None = None) -> str:
    cols = [c for c in ("game_key", "date", "home", "away", "home_pts", "away_pts", "line_open",
                        "line_close", "clean") if c in games]
    h = hashlib.sha1(pd.util.hash_pandas_object(games[cols].sort_values("game_key"), index=False).values.tobytes())
    if box is not None and len(box):
        bcols = [c for c in ("espn_game_id", "team_id", "pts", "poss") if c in box]
        h.update(pd.util.hash_pandas_object(box[bcols], index=False).values.tobytes())
    return h.hexdigest()[:16]


def _prev(season: str) -> str:
    y = int(season[:4]) - 1
    return f"{y}-{str(y + 1)[2:]}"


def get_features(league: str, games: pd.DataFrame, box: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    STORE.mkdir(parents=True, exist_ok=True)
    fp = fingerprint(games, box)
    path = STORE / f"{league}_features_{fp}.parquet"
    if path.exists():
        if verbose:
            print(f"[store] {league} features: reused {path.name}", flush=True)
        return pd.read_parquet(path)
    # incremental: reuse the newest stored file whose completed seasons are unchanged
    seasons = sorted(games.season.unique())
    best = None
    for cand in sorted(STORE.glob(f"{league}_features_*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = cand.with_suffix(".json")
        if not meta.exists():
            continue
        info = json.loads(meta.read_text())
        for s in sorted(info.get("season_fingerprints", {}), reverse=True):
            done = [x for x in seasons if x < s]
            if done and info["season_fingerprints"].get(s) == fingerprint(games[games.season < s]):
                best = (cand, s)
                break
        if best:
            break
    if best is not None:
        cand, s = best
        old = pd.read_parquet(cand)
        hist = old[old.season < s]
        recent = build_ncaab_features(write=False, games=games[games.season >= _prev(s)], box=box)
        recent = recent[recent.season >= s]
        f = pd.concat([hist, recent], ignore_index=True)
        if verbose:
            print(f"[store] {league} features: reused seasons < {s}, recomputed {s}+", flush=True)
    else:
        if verbose:
            print(f"[store] {league} features: building from scratch (one-off)", flush=True)
        f = build_ncaab_features(write=False, games=games, box=box)
    f.to_parquet(path, index=False)
    path.with_suffix(".json").write_text(json.dumps({
        "fingerprint": fp, "rows": len(f),
        "season_fingerprints": {s: fingerprint(games[games.season < s]) for s in seasons}}))
    prune(league)
    return f


def prune(league: str, keep: int = 3) -> None:
    """Keep only the newest `keep` feature files per league (daily live runs add one each)."""
    files = sorted(STORE.glob(f"{league}_features_*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)
        old.with_suffix(".json").unlink(missing_ok=True)


def cached_walk_forward(d: pd.DataFrame, spec: dict, seasons: list, feature_fp: str):
    """Walk-forward predictions + calibrators, cached by engine spec + feature fingerprint."""
    from backtest.wf2 import walk_forward_market
    STORE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(json.dumps({"spec": spec, "seasons": seasons, "fp": feature_fp,
                                   "n": len(d)}, sort_keys=True, default=str).encode()).hexdigest()[:16]
    path = STORE / f"wf_{key}.pkl"
    if path.exists():
        return pickle.loads(path.read_bytes())
    out = walk_forward_market(d, spec["mean_feats"], spec["var_feats"], spec["kind"], spec["shape"],
                              spec["alpha"], seasons=seasons, min_games=spec["min_games"],
                              train_decay=spec.get("train_decay"), calib_decay=spec.get("calib_decay"))
    path.write_bytes(pickle.dumps(out))
    return out


def adopt(league: str, path, games: pd.DataFrame, box: pd.DataFrame) -> "Path":
    """Register an already-built feature file (built from exactly `games`/`box`) in the
    store, so nothing has to be recomputed."""
    from pathlib import Path
    path = Path(path)
    f = pd.read_parquet(path, columns=["game_key", "season"])
    expected = set(games[games.clean].game_key)
    if set(f.game_key) != expected:
        raise ValueError(f"{path.name} was not built from these games ({len(f)} vs {len(expected)} rows)")
    STORE.mkdir(parents=True, exist_ok=True)
    fp = fingerprint(games, box)
    dest = STORE / f"{league}_features_{fp}.parquet"
    path.replace(dest)
    seasons = sorted(games.season.unique())
    dest.with_suffix(".json").write_text(json.dumps({
        "fingerprint": fp, "rows": len(f),
        "season_fingerprints": {s: fingerprint(games[games.season < s]) for s in seasons}}))
    return dest
