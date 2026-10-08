"""Data for the loss-autopsy page: why the NCAAB straight bets lost, every idea screened (rounds 1-3),
the venue park factor, and study 6's verdict. Reads the outputs of scripts/loss_autopsy*.py and
scripts/study6_venue.py; writes reports/loss_autopsy.json.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from config_loader import ROOT

PROC, REP = ROOT / "data" / "processed", ROOT / "reports"
FACTORS = [("s_three_luck", "3-point shooting"), ("s_two_luck", "2-point shooting"), ("s_pace_pts", "Pace"),
           ("s_ft_luck", "Free throws"), ("s_ot_pts", "Overtime")]


def md_table(text: str, after: str) -> list[dict]:
    """First pipe table following the line that contains `after`."""
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if after in l)
    rows = []
    for l in lines[i + 1:]:
        if l.startswith("|"):
            rows.append([c.strip() for c in l.strip("|").split("|")])
        elif rows:
            break
    head, body = rows[0], [r for r in rows[2:]]
    return [dict(zip(head, r)) for r in body]


def latest(name: str) -> dict:
    return json.loads(Path(sorted(glob.glob(str(REP / "experiments" / f"*_{name}.json")))[-1]).read_text())["results"]


def main():
    B = pd.read_parquet(PROC / "loss_autopsy_bets.parquet")
    B = B[B.s_three_luck.notna() & B.s_ot_pts.notna() & B.pace_pts.notna()]
    decomp = []
    for res, lab in ((1, "won"), (0, "lost")):
        x = B[B.won == res]
        decomp.append({"bets": lab, "n": int(len(x)), "margin": float(x.s_miss.mean()),
                       "edge": float((x.best_side * x.mu).mean()), "p": float(x.p_best.mean()),
                       **{name: float(x[c].mean()) for c, name in FACTORS}})
    lost = B[B.won == 0]
    worst = lost[[c for c, _ in FACTORS]].idxmin(axis=1).map(dict(FACTORS)).value_counts(normalize=True)
    eras = {e: {"won": int((g.won == 1).sum()), "lost": int((g.won == 0).sum())} for e, g in B.groupby("era")}

    ideas = []
    for rnd, name in ((1, "loss_autopsy"), (2, "loss_autopsy_round2"), (3, "loss_autopsy_round3")):
        for r in latest(name)["ideas"]:
            ideas.append({"round": rnd, "idea": r["idea"], "t_disc": r["t all games (disc)"], "t_val": r["t all games (val)"],
                          "t_bets_disc": r.get("t our bets (disc)"), "t_bets_val": r.get("t our bets (val)"), "lead": bool(r["lead?"])})
    over = latest("loss_autopsy_round2")["overshoot"]

    R = pd.read_parquet(PROC / "loss_autopsy_round2.parquet")
    V = R[R.venue_factor.notna()].copy()
    quint = []
    for era, g in V.groupby("era"):
        g = g.assign(q=pd.qcut(g.venue_factor, 5, labels=False))
        for q, h in g.groupby("q"):
            quint.append({"era": era, "quintile": int(q) + 1, "factor": float(h.venue_factor.mean()),
                          "miss": float(h.r.mean()), "se": float(h.r.std() / np.sqrt(len(h))), "games": int(len(h))})
    agree = []
    for era, g in V[V.bet].groupby("era"):
        strong = g.venue_factor.abs() >= 1
        for lab, sel in (("Strong, agrees with the bet", strong & (np.sign(g.venue_factor) == g.best_side)),
                         ("Strong, against the bet", strong & (np.sign(g.venue_factor) != g.best_side)),
                         ("Weak (under 1 point)", ~strong)):
            x = g[sel]
            agree.append({"era": era, "group": lab, "bets": int(len(x)), "won": float(x.won.mean()),
                          "roi": float((x.won * 100 / 110 - (1 - x.won)).mean())})
    absent = []
    R3 = (REP / "loss_autopsy_round3.md").read_text()
    for r in md_table(R3, "Bets with and without the flag"):
        if r["idea"] == "key player missed the last game":
            absent.append({"era": r["era"], "side": r["side"], "flagged": r["flagged"] == "True", "bets": int(r["bets"]),
                           "won": float(r["won"])})

    study = None
    rep6 = REP / "study6_venue.md"
    if rep6.exists():
        t6 = rep6.read_text()
        study = {"selection": md_table(t6, "## Selection (2011-21)"),
                 "qualifies": re.search(r"Qualifies.*", t6).group(0), "selected": re.search(r"Selected: \*\*(.+?)\*\*", t6).group(1),
                 "bets_2011_21": md_table(t6, "Locked engine's bets by venue factor (secondary, 2011-21)")}
        if "## Confirmation" in t6:
            study["confirmation"] = md_table(t6, "## Confirmation on the sealed")
            study["by_season"] = md_table(t6, "Season by season:")
            study["cards"] = md_table(t6, "2.5+ target cards and main-line doubles")
            study["bets_2021_26"] = md_table(t6, "Locked engine's 2021-26 bets by venue factor")
            study["passed"] = "Confirmation passed: True" in t6
    paired = {}
    pc = REP / "study6_paired_cards.json"
    if pc.exists():
        for k, v in json.loads(pc.read_text()).items():
            paired[k] = {"diff": v["diff"], "ci": v["diff ci95"], "same": v["identical cards"], "n": v["cards locked"],
                         "better_share": v["share of resamples venue better"]}
    out = {"paired": paired, "decomp": decomp, "worst": {k: float(v) for k, v in worst.items()}, "eras": eras,
           "ot_share_lost": float((lost.ot_pts > 0).mean()), "ot_share_lost_under": float((lost[lost.best_side == -1].ot_pts > 0).mean()),
           "ideas": ideas, "overshoot": over, "quintiles": quint, "agree": agree, "absent": absent, "study6": study}
    (REP / "loss_autopsy.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k in ("decomp", "worst", "eras")}, indent=1))
    print(len(ideas), "ideas;", "study 6:", None if study is None else (study["selected"], study.get("passed")))


if __name__ == "__main__":
    main()
