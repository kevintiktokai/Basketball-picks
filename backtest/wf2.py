"""Stage-2 walk-forward engine for any market (NCAAB open/close/2H, NBA close).

* Mean + variance model refit before each test season on earlier seasons only.
* Edge-aware latent calibrator for season s fitted only on OOS predictions of
  seasons < s (pseudo-bets at many buffers, both sides).
* A MARKET-ONLY model (no features: the line is taken as the truth, historical
  residual distribution) is run through the same machinery; its calibrated
  probabilities are the "fair book price" used to price buffered/alternate legs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from models.dist_models import DistModel, LatentCalibrator

Z95 = 1.6449   # one-sided 95%


def walk_forward_market(df: pd.DataFrame, mean_feats, var_feats, kind="ridge", shape="normal",
                        alpha=50.0, seasons=None, min_train=2, min_games=3,
                        calib_seed_seasons=2):
    seasons = seasons or sorted(df.season.unique())
    data = df[df.season.isin(seasons)].copy()
    elig = data.rt_min_games.fillna(0) >= min_games
    data["eligible"] = elig
    preds = []
    for i, s in enumerate(seasons):
        if i < min_train:
            continue
        tr = data[data.season.isin(seasons[:i]) & data.eligible]
        te = data[data.season == s].copy()
        m = DistModel(mean_feats, var_feats, kind=kind, shape=shape, alpha=alpha).fit(tr)
        te["mu"] = m.predict_mean(te)
        te["sd"] = m.predict_sd(te)
        mk = DistModel([], [], shape=shape).fit(tr)               # market-only reference
        te["mu_mkt"] = mk.predict_mean(te)
        te["sd_mkt"] = mk.predict_sd(te)
        preds.append(te)
    P = pd.concat(preds, ignore_index=True)
    cals, cals_mkt = {}, {}
    pseasons = list(dict.fromkeys(P.season))
    for j, s in enumerate(pseasons):
        if j < calib_seed_seasons:
            continue
        hist = P[P.season.isin(pseasons[:j]) & P.eligible]
        cals[s] = LatentCalibrator().fit(hist)
        cals_mkt[s] = LatentCalibrator().fit(hist.assign(mu=hist.mu_mkt, sd=hist.sd_mkt))
    P["calibrated"] = P.season.isin(list(cals))
    return P, cals, cals_mkt


# ------------------------------------------------------------- leg pricing
K_GRID = np.arange(0.0, 20.5, 0.5)          # buffer (points in bettor's favour)


def leg_table(P: pd.DataFrame, cals: dict, cals_mkt: dict, k_grid=K_GRID) -> dict:
    """For every calibrated game, side and buffer: model prob, conservative prob,
    market-only prob, threshold, outcome. Returns arrays keyed by name with shape
    (n_games, 2 sides, n_k)."""
    P = P[P.calibrated].reset_index(drop=True)
    n, nk = len(P), len(k_grid)
    sides = np.array([1, -1])
    out = {k: np.full((n, 2, nk), np.nan) for k in ("p", "p_cons", "p_mkt", "p_mkt_close", "thr", "win")}
    has_close = "line_close" in P
    line = P.line.values
    base = {1: np.ceil(line + 0.5) - 0.5, -1: np.floor(line - 0.5) + 0.5}
    for s_i, side in enumerate(sides):
        for k_i, k in enumerate(k_grid):
            thr = base[side] - side * k
            win = (P.outcome.values > thr) if side == 1 else (P.outcome.values < thr)
            out["thr"][:, s_i, k_i] = thr
            out["win"][:, s_i, k_i] = win
    for season, idx in P.groupby("season").groups.items():
        idx = np.asarray(idx)
        cal, calm = cals[season], cals_mkt[season]
        for s_i, side in enumerate(sides):
            for k_i in range(nk):
                thr = out["thr"][idx, s_i, k_i]
                sm = side * P.mu.values[idx] / P.sd.values[idx]
                sb = side * (line[idx] - thr) / P.sd.values[idx]
                p, lo = cal.prob(sm, sb, z=Z95)
                out["p"][idx, s_i, k_i] = p
                out["p_cons"][idx, s_i, k_i] = lo
                smm = side * P.mu_mkt.values[idx] / P.sd_mkt.values[idx]
                sbm = side * (line[idx] - thr) / P.sd_mkt.values[idx]
                out["p_mkt"][idx, s_i, k_i] = calm.prob(smm, sbm)
                if has_close:
                    # stress test: the same alternate line priced off the CLOSING line
                    sbc = side * (P.line_close.values[idx] - thr) / P.sd_mkt.values[idx]
                    out["p_mkt_close"][idx, s_i, k_i] = calm.prob(smm, sbc)
    out["frame"] = P
    out["k_grid"] = k_grid
    return out


# ------------------------------------------------------------- main line
def main_line_probs(P: pd.DataFrame, cals: dict) -> pd.DataFrame:
    """Calibrated P(win) for Over and Under at the actual market line (pushes possible)."""
    P = P[P.calibrated].copy()
    L = P.line.values
    for side, name in ((1, "over"), (-1, "under")):
        thr = (np.ceil(L + 0.5) - 0.5) if side == 1 else (np.floor(L - 0.5) + 0.5)
        p = np.empty(len(P))
        lo = np.empty(len(P))
        for season, idx in P.groupby("season").groups.items():
            ii = P.index.get_indexer(idx)
            sm = side * P.mu.values[ii] / P.sd.values[ii]
            sb = side * (L[ii] - thr[ii]) / P.sd.values[ii]
            p[ii], lo[ii] = cals[season].prob(sm, sb, z=Z95)
        P[f"p_{name}"] = p
        P[f"p_{name}_cons"] = lo
    P["p_push"] = np.clip(1 - P.p_over - P.p_under, 0, None)
    P["best_side"] = np.where(P.p_over >= P.p_under, 1, -1)
    P["p_best"] = np.maximum(P.p_over, P.p_under)
    P["p_best_cons"] = np.where(P.best_side == 1, P.p_over_cons, P.p_under_cons)
    P["best_win"] = np.where(P.best_side == 1, P.outcome > P.line, P.outcome < P.line).astype(int)
    P["best_push"] = P.outcome == P.line
    return P


# ------------------------------------------------------------- cards
def _pair_search(legs, joint_target, rho_lo=0.0):
    """legs: list of dicts with arrays over k: p, p_cons, val (= p * odds). Choose a pair of
    legs from DIFFERENT games and a buffer for each maximizing val_A*val_B subject to
    p_cons_A * p_cons_B >= joint_target (independence lower-bound; rho_lo<=0 adds slack)."""
    best = None
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            a, b = legs[i], legs[j]
            if a["game"] == b["game"]:
                continue
            cA = a["p_cons"][:, None]
            cB = b["p_cons"][None, :]
            ok = cA * cB + rho_lo * np.sqrt(cA * (1 - cA) * cB * (1 - cB)) >= joint_target
            if not ok.any():
                continue
            v = a["val"][:, None] * b["val"][None, :]
            v = np.where(ok, v, -np.inf)
            ka, kb = np.unravel_index(np.argmax(v), v.shape)
            if best is None or v[ka, kb] > best[0]:
                best = (v[ka, kb], i, j, ka, kb)
    return best


def buffered_cards(T: dict, joint_target=0.60, margin=0.0455, top_legs=14, value_gate=False,
                   rho_lo=0.0, max_buffer=None):
    """Simulate the buffered-line card engine slate by slate.
    Pricing: offered decimal odds at threshold t = (1 - margin) / p_mkt(t)."""
    P = T["frame"]
    kg = T["k_grid"]
    kmask = np.ones(len(kg), bool) if max_buffer is None else (kg <= max_buffer)
    odds = (1 - margin) / np.clip(T["p_mkt"], 1e-3, 1)
    val = T["p"] * odds
    rows = []
    for date, idx in P.groupby("date").groups.items():
        idx = np.asarray(idx)
        idx = idx[P.eligible.values[idx]]
        if len(idx) < 2:
            continue
        # rank legs by best value achievable at the symmetric requirement
        req = np.sqrt(joint_target)
        cand = []
        for gi in idx:
            for s_i in range(2):
                pc = np.where(kmask, T["p_cons"][gi, s_i], 0.0)
                feas = pc >= req
                if not feas.any():
                    continue
                score = np.max(np.where(feas, val[gi, s_i], -np.inf))
                cand.append((score, gi, s_i))
        if len(cand) < 2:
            rows.append({"date": date, "season": P.season.values[idx[0]], "released": False})
            continue
        cand.sort(reverse=True)
        # masked buffers: p_cons = 0 (never feasible), val = 0 (never preferred)
        legs = [{"game": gi, "side": s_i, "p_cons": np.where(kmask, T["p_cons"][gi, s_i], 0.0),
                 "val": np.where(kmask, val[gi, s_i], 0.0)} for _, gi, s_i in cand[:top_legs]]
        best = _pair_search(legs, joint_target, rho_lo)
        if best is None:
            rows.append({"date": date, "season": P.season.values[idx[0]], "released": False})
            continue
        v, i, j, ka, kb = best
        A, B = legs[i], legs[j]
        ga, sa, gb, sb = A["game"], A["side"], B["game"], B["side"]
        pa, pb = T["p"][ga, sa, ka], T["p"][gb, sb, kb]
        oa, ob = odds[ga, sa, ka], odds[gb, sb, kb]
        ev = pa * pb * oa * ob - 1
        released = (not value_gate) or ev > 0
        wa, wb = T["win"][ga, sa, ka], T["win"][gb, sb, kb]
        rows.append({
            "date": date, "season": P.season.values[ga], "released": released,
            "game_a": P.game_key.values[ga], "side_a": 1 - 2 * sa, "buf_a": kg[ka],
            "thr_a": T["thr"][ga, sa, ka], "p_a": pa, "pc_a": T["p_cons"][ga, sa, ka],
            "pm_a": T["p_mkt"][ga, sa, ka], "odds_a": oa, "win_a": wa,
            "game_b": P.game_key.values[gb], "side_b": 1 - 2 * sb, "buf_b": kg[kb],
            "thr_b": T["thr"][gb, sb, kb], "p_b": pb, "pc_b": T["p_cons"][gb, sb, kb],
            "pm_b": T["p_mkt"][gb, sb, kb], "odds_b": ob, "win_b": wb,
            "joint_model": pa * pb, "joint_cons": T["p_cons"][ga, sa, ka] * T["p_cons"][gb, sb, kb],
            "joint_mkt": T["p_mkt"][ga, sa, ka] * T["p_mkt"][gb, sb, kb],
            "ev_double": ev, "card_2of2": int(wa and wb),
            "profit_double": (oa * ob - 1) if (wa and wb) else -1.0,
        })
        pmc_a, pmc_b = T["p_mkt_close"][ga, sa, ka], T["p_mkt_close"][gb, sb, kb]
        if not (np.isnan(pmc_a) or np.isnan(pmc_b)):
            oca, ocb = (1 - margin) / pmc_a, (1 - margin) / pmc_b
            rows[-1].update({"odds_close_a": oca, "odds_close_b": ocb,
                             "profit_double_close": (oca * ocb - 1) if (wa and wb) else -1.0})
    return pd.DataFrame(rows)


def card_summary(C: pd.DataFrame) -> dict:
    from calibration.calibrate import wilson
    if C.empty:
        return {"slates": 0, "cards": 0}
    R = C[C.released == True]  # noqa: E712
    n = len(R)
    out = {"slates": int(len(C)), "cards": int(n), "pct_slates_with_card": n / len(C)}
    if n:
        k = int(R.card_2of2.sum())
        lo, hi = wilson(k, n)
        out.update({
            "rate_2of2": k / n, "ci95": (lo, hi), "avg_joint_model": float(R.joint_model.mean()),
            "avg_joint_cons": float(R.joint_cons.mean()), "avg_joint_mkt": float(R.joint_mkt.mean()),
            "avg_buffer": float((R.buf_a + R.buf_b).mean() / 2),
            "avg_double_odds": float((R.odds_a * R.odds_b).mean()),
            "roi_double": float(R.profit_double.mean()), "avg_model_ev": float(R.ev_double.mean()),
            "roi_double_close_priced": float(R.profit_double_close.mean()) if "profit_double_close" in R else np.nan,
            "leg_win_rate": float((R.win_a.sum() + R.win_b.sum()) / (2 * n)),
            "avg_leg_p": float((R.p_a + R.p_b).mean() / 2),
        })
    return out
