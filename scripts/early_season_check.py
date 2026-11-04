"""Early-season check: the locked NCAAB engine on games it never bets (either team has played fewer
than 3 games this season, the eligibility rule). Best 5 a day at P >= 53% and all picks at P >= 53% / 55%,
-110 before 2021-22 and the best real opening price after. Run once on 4 Nov 2026 (opening week).
usage: python scripts/early_season_check.py
"""
import sys; sys.path.insert(0,'scripts'); sys.path.insert(0,'.')
import warnings; warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from diagnose_bets import load
from backtest.wf2 import main_line_probs
from backtest.odds_cards import best_main
P, cals, _ = load()
M = main_line_probs(P, cals)
E = M[~M.eligible & M.season.isin([f"{y}-{str(y+1)[2:]}" for y in range(2011, 2026)])].copy()
E['day'] = E.date.dt.strftime('%Y-%m-%d')
E['games_in'] = E.rt_min_games.fillna(0) if 'rt_min_games' in E else np.nan
print('early games', len(E), 'by min games played', E.games_in.value_counts().sort_index().to_dict())
def grade(B):
    side = B.best_side.values; real = (B.season >= '2021-22').values
    st = [best_main(bj, s)[:2] if r and isinstance(bj, str) else (np.nan, np.nan) for bj, s, r in zip(B.books_json, side, real)]
    rl, ro = np.array(st, dtype=float).T
    ok = ~np.isnan(rl) & ~np.isnan(ro)
    line = np.where(ok, rl, B.line); odds = np.where(ok, ro, 1 + 100/110)
    win = np.where(side == 1, B.outcome > line, B.outcome < line); push = B.outcome.values == line
    return B.assign(pnl=np.where(push, 0, np.where(win, odds - 1, -1.0)), won=win & ~push, push=push)
for floor, n in ((0.53, 5), (0.55, None), (0.53, None)):
    S = E[E.p_best >= floor].sort_values(['day', 'p_best'], ascending=[True, False])
    if n: S = S[S.groupby('day').cumcount() < n]
    G = grade(S)
    for lab, g in (('2011-21', G[G.season < '2021-22']), ('2021-26', G[G.season >= '2021-22'])):
        d = g[~g.push]
        print(f"{'best %d a day' % n if n else 'all'} P>={floor}: {lab} bets {len(g)} won {d.won.mean():.3f} ROI {g.pnl.mean():+.3f} ± {g.pnl.std()/np.sqrt(len(g)):.3f}")
    print('  by games played:', G.groupby('games_in').agg(n=('pnl','size'), roi=('pnl','mean')).round(3).to_dict('index'))
