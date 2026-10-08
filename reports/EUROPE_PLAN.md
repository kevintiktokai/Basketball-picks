# Taking the engine to European basketball — plan

## What carries over unchanged

The engine is league-agnostic. A new league needs only an **adapter** that produces
two tables. Everything downstream (point-in-time features, ratings, mean + variance
models, edge-aware calibration, odds-targeted cards, leakage tests, walk-forward
validation) runs unchanged.

| table | required columns | used for |
|---|---|---|
| `games` | season, date, home, away, home_pts, away_pts, line_open, line_close, home_spread_open, neutral, per-book odds (`books_json`: open/close total + Over/Under prices) | targets, market features, real prices |
| `box` (optional) | game id, team, pts, FGA, FGM, 3PA, 3PM, FTA, FTM, ORB, DRB, TOV | possessions, tempo-free ratings, style matchups |

Without box scores the engine falls back to points-only ratings. Stage 1 showed
that this loses only a little.

## What European markets change

* **Ladders, not one line.** European books list several totals per game, each with
  its own price, e.g. Over 157.5 @ 1.62 and Over 160.5 @ 1.87. This is exactly what
  the odds-targeted card engine models. Real ladder prices replace our modelled
  alternate prices, which removes the biggest assumption in the US results.
* **Scale.** 40-minute games, fewer possessions: totals around 150–175, residual SD
  around 13–15 points (NCAAB ~17, NBA ~18). A leg at ~1.6 sits about 3–4 points off the
  main line rather than 4–5.
* **Softness varies by league.** EuroLeague is sharp; second-tier domestic leagues
  likely less so, but with lower limits. The same CLV check (does the market move our
  way?) tells us which leagues are worth it.
* **Schedule effects.** EuroLeague double-game weeks, domestic + European fixture
  congestion and travel all feed the rest/fatigue features.

## Data — what was verified to be reachable (October 2026)

| need | source | status |
|---|---|---|
| EuroLeague / EuroCup results | `api-live.euroleague.net/v1/results?seasonCode=E2024` (U = EuroCup) | ✅ free; 330 EuroLeague games in 2024-25 |
| EuroLeague box scores, by quarter | `live.euroleague.net/api/Boxscore`, `api-live.euroleague.net/v2/.../stats` | ✅ free |
| domestic league results/box (ACB, LNB, BBL, LBA, BSL, GBL, ABA…) | league sites / aggregators | per league; to be built |
| **historical odds with opening + closing ladders** | OddsPortal / BetExplorer | pages load, but odds are loaded dynamically; automated collection may breach their terms |
| | The Odds API (historical snapshots since 2020, includes EuroLeague) | needs a paid key |
| | sportsbookreview.com (used for NCAAB/NBA) | ❌ no European leagues |

**The bottleneck is odds history, not results.**

## Recommended path

1. **Start collecting now.** A paid odds API that returns opening and pre-game totals
   ladders with prices, one snapshot when lines open and one near tip-off, for the
   leagues you care about. A season of your own data is worth more than any scrape.
2. **Build the adapters:** EuroLeague/EuroCup first (free results and box scores),
   then 2–3 domestic leagues with the deepest markets.
3. **Backfill history where it can be done legitimately** (purchased historical odds) to
   get 3–5 seasons per league for development.
4. **Apply the same protocol:** pre-registered splits, development only on early seasons,
   lock, one-time test, real ladder prices, CLV check, then a forward paper-trading ledger.
5. **Go live only where the forward record and CLV agree.**

## Expectations

From the US results: the edge, where it exists, is at **opening lines** and grows with
**line shopping across books**. At combined odds ≈ 2.5 a winning engine hits roughly
45–50% of cards. A claim of 60%+ at those odds would mean a +50% return per card, and
no market supports that sustainably.
