# Basketball Totals Card Engine

A walk-forward research engine for basketball totals. It builds **two-pick cards**,
where both legs must win, and asks whether such a card can win 2/2 at least 60% of the
time **on seasons it has never seen**.

| stage | scope | out-of-sample answer |
|---|---|---|
| 1 | NBA, Overs only, main line | **No.** Each leg needs ~77%; the NBA close tops out near 60%. 0 cards in 2,896 slates. [`RESEARCH_SUMMARY.md`](reports/RESEARCH_SUMMARY.md) |
| 2 | NCAA men's basketball, Over **or** Under, opening line, **buffered (alternate) lines** | **Yes:** 63.9% 2/2 over 664 never-seen cards, 2021-26 (95% CI 60.1–67.4%). 60.9% on the 2018-21 holdout. [`STAGE2_SUMMARY.md`](reports/STAGE2_SUMMARY.md) |
| 3 | Odds-targeted cards: combined odds ≥ 2.5 (legs ≈ 1.6), NCAAB + NBA openers, real prices | **NCAAB: 46.8% of cards won at 2.57 avg (break-even 39%), ROI ≈ +20%** (2021-26 re-analysis; +16–17% in development). NBA: no reliable edge. [`STAGE3_SUMMARY.md`](reports/STAGE3_SUMMARY.md) |
| Europe | EuroLeague + EuroCup: free official data (2016-26, with referees) loaded; odds history pending | Ratings work (residual SD ~17 pts); referees/rest add nothing out of sample. The missing input is historical odds; a free OddsPapi key unlocks them. [`EUROPE_DATA.md`](reports/EUROPE_DATA.md) |

The 60% is bought with price. Each leg is an alternate total about 10 points better than
the opener (~80% win, ~1.25 odds), so the double pays ~1.65. Whether it makes money depends
on getting alternate lines near the **opening** number at a fair margin. The tool prints
the break-even odds for every card.

## Daily use (NCAAB)

```bash
pip install -r requirements.txt
python -m data.ncaab_ingest                       # archive odds + ESPN box scores (pinned, checksummed)
python -m data.sbr_live fetch && python -m data.sbr_live parse   # 2021-26 odds (cached, ~1 req/s)

# a day's card: refresh this season's results/odds, then build the card
python scripts/predict_cards.py --date 2026-11-20 --update --record                 # target card (>=2.5, legs ~1.6)
python scripts/predict_cards.py --date 2026-11-20 --product main --record         # main-line double, real prices
python scripts/predict_cards.py --date 2026-11-20 --product sixty                 # stage-2 60% buffered card
python scripts/predict_cards.py --date 2026-11-20 --slate my_slate.csv   # manual openers
python scripts/grade_ledger.py                     # forward-test record of recorded cards
```

`my_slate.csv` columns: `home, away, line` (opening total) and optionally `home_spread`,
`neutral`, and `over_odds` / `under_odds` (decimal) so the main-line legs use your real prices. The default engine is `v3`; `--engine v2` uses the pre-registered primary
engine. Output for each leg: side, alternate line to bet, model probability, conservative
probability and fair odds, plus the card's break-even double odds and the unbuffered
main-line view for every game.

## Layout

```
config/       config.yaml (stage 1), stage2.yaml / stage2b.yaml (pre-registrations),
              stage2_locked.yaml (v2), stage3_v3_locked.yaml (v3)
data/         NBA: sources.py, ingest.py · NCAAB: ncaab_ingest.py (SBR archive + ESPN box),
              sbr_live.py (sportsbookreview.com scraper/parser), ncaab_unify.py (ESPN team ids)
              Europe: euroleague.py (official API: games, box, referees), oddspapi.py (historical odds)
features/     pit.py (NBA), ratings.py (daily ridge ratings), ncaab_features.py (3 markets)
models/       total_models.py (stage 1), dist_models.py (mean+variance, edge-aware calibrator),
              live.py (NBA CLI), live_ncaab.py (NCAAB card engine)
backtest/     walkforward.py / cards.py / engine.py (stage 1), wf2.py (stage 2 walk-forward,
              leg pricing, buffered card engine)
scripts/      run_research.py, run_holdout.py, predict.py (stage 1)
              stage2_iterate.py, stage2_holdout.py, stage2b_test.py, predict_cards.py, grade_ledger.py
              euro_info_study.py (what the free European data adds)
reports/      RESEARCH_SUMMARY.md, STAGE2_SUMMARY.md, ITERATIONS.md, holdout & test reports,
              experiments/*.json (one record per run)
tests/        leakage tests (NBA + NCAAB, all markets) and engine unit tests
```

## Ground rules enforced in code

* Features use only games on **earlier dates**. Tests corrupt future results and lines and
  require earlier features to be bit-identical.
* Models and calibrators for season *s* are fitted only on seasons before *s*.
* Every test period was pre-registered, and the engine was locked and committed before the
  test ran once. Every configuration tried is logged.
* Cards require the **conservative** joint probability to clear the target. Targets are
  never relaxed to fill a card.
