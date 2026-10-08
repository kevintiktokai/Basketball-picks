"""Post-hoc sizing for study 6 (its one confirmation had already run and failed): paired, day-level bootstrap
of the 2.5+ card and main-line double, locked engine vs the venue engine, 2021-26 at real prices. Not a test;
it only measures how much of the card difference could be noise. Writes reports/study6_paired_cards.json."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parent))
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import study2_stage_matchup as S2, study6_venue as S6
from features.store import cached_walk_forward
from stage3_common import evaluate
d, fp = S6.market()
seasons = sorted(d.season.unique())
base = S2.spec_v3()
arms = {"locked": cached_walk_forward(d, base, seasons, fp),
        "venue": cached_walk_forward(d, dict(base, mean_feats=list(base["mean_feats"]) + ["venue_factor"], study="study_6:V1_venue"), seasons, fp)}
books = d.set_index("game_key").books_json
out = {}
cards = {}
for k, (P, cals, calm) in arms.items():
    R, C = evaluate(P, cals, calm, books, S2.CONF)
    cards[k] = C
for prod in cards["locked"]:
    if not prod.startswith(("TARGET", "MAIN")):
        continue
    a, b = cards["locked"][prod], cards["venue"][prod]
    da = a.groupby("date").profit.sum(); db = b.groupby("date").profit.sum()
    na = a.groupby("date").size(); nb = b.groupby("date").size()
    days = sorted(set(da.index) | set(db.index))
    A = np.array([da.get(x, 0.0) for x in days]); Bv = np.array([db.get(x, 0.0) for x in days])
    NA = np.array([na.get(x, 0) for x in days]); NB = np.array([nb.get(x, 0) for x in days])
    rng = np.random.default_rng(7)
    diffs = []
    for _ in range(10000):
        i = rng.integers(0, len(days), len(days))
        diffs.append(Bv[i].sum() / max(NB[i].sum(), 1) - A[i].sum() / max(NA[i].sum(), 1))
    key_a = set(zip(a.date, a.game_a, a.game_b, a.side_a, a.side_b)); key_b = set(zip(b.date, b.game_a, b.game_b, b.side_a, b.side_b))
    out[prod] = {"cards locked": len(a), "cards venue": len(b), "identical cards": len(key_a & key_b),
                 "roi locked": A.sum() / NA.sum(), "roi venue": Bv.sum() / NB.sum(),
                 "diff": float(np.mean(diffs)), "diff ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
                 "share of resamples venue better": float(np.mean(np.array(diffs) > 0))}
print(json.dumps(out, indent=1, default=float))
json.dump(out, open(Path(__file__).resolve().parents[1] / "reports" / "study6_paired_cards.json", "w"), indent=1, default=float)
