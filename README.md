# Basketball Over Engine

A walk-forward research engine for basketball totals (Overs only). It asks
whether two-pick Over cards can win 2/2 at least 60% of the time **out of
sample**. It may release a TWO-PICK CARD, ONE QUALIFYING PICK or NO BET on
each slate.

**Stage-1 answer (NBA 2007–2026): no.** Same-slate games are effectively
independent, so each pick would need P ≈ 77%. The closing NBA total never let
the model exceed about 61%. The engine correctly released 0 cards in 2,896
historical slates. See [`reports/RESEARCH_SUMMARY.md`](reports/RESEARCH_SUMMARY.md).

## Layout

```
config/       config.yaml (pre-registered splits, data pins), locked_model.yaml
data/         sources.py (pinned fetch), ingest.py (clean/validate), SCHEMA.md
features/     pit.py — point-in-time feature builder (leakage-asserted)
models/       total_models.py (ablation feature sets, learners, P(over)), live.py
calibration/  calibrate.py — Platt/isotonic, conservative bounds, ECE/Brier/log loss
backtest/     walkforward.py, dependence.py, cards.py (selection engine), engine.py, analysis.py
scripts/      run_research.py (development), run_holdout.py (one-shot), predict.py (CLI)
reports/      development_report.md, holdout_report.md, RESEARCH_SUMMARY.md, experiments/*.json
tests/        leakage tests + engine unit tests
```

## Reproduce

```bash
pip install -r requirements.txt
python -m data.ingest            # fetch pinned sources, verify sha256, build processed tables
python -m pytest                 # leakage + engine tests
python scripts/run_research.py   # discovery + validation only; writes config/locked_model.yaml
python scripts/run_holdout.py    # refuses to run if reports/holdout_report.md exists
```

Every run writes a JSON record to `reports/experiments/` with the timestamp,
dataset version, code revision, parameters and results.

## Live use

```bash
python scripts/predict.py --slate examples/slate_example.csv --time 19:00 --bookmaker fanduel \
    [--history recent_results.csv]
```

`slate.csv` needs: `home, away, line, over_odds` plus optional `date`,
`home_spread` and `league`. The bundled dataset ends on 2026-01-07. For later
dates, pass `--history` with completed games (`date, home, away, line,
home_pts, away_pts`) so team ratings are current. Only NBA is supported, because
no other league has historical totals data here. The example slate's lines are
illustrative, not real market prices.

## Ground rules enforced in code

* Features for a game use only games on **earlier dates** (`feature_asof < date` is asserted;
  tests corrupt future results and require past features to be bit-identical).
* Models and calibrators for season *s* are fitted only on seasons before *s*.
* Holdout seasons are never predicted by the development script. The model was
  locked and committed before the holdout ran once.
* Cards require the **conservative** joint probability (5% lower-bound marginals +
  lower-bound dependence) ≥ 60%. Thresholds are never relaxed to fill a card.
