# European picks, live (EuroLeague totals)

## What it does

`scripts/predict_euro.py` takes one live odds snapshot, values every soft-book total (1xBet,
Betway, Unibet) against Pinnacle's no-vig price, and asks the European ratings model whether it
agrees. It prints two products:

| product | rule | status |
|---|---|---|
| **2.5+ card** | the locked European strategy (`config/europe_locked.yaml`), unchanged: legs at odds 1.70–2.10, at least 1% above Pinnacle's fair price, model agrees, best leg per game, the pair with the highest joint value and combined odds ≥ 2.5, one card a day | locked before its holdout; development evidence only |
| **singles** | each game's best soft-book price at least 2% above Pinnacle's fair price | test phase |

Where the evidence stands: in development (144 games of 2025-26) soft-book prices above
Pinnacle's fair price beat Pinnacle's closing price by +2% to +5% on average, which is the sign
of a real edge. Win/loss results on so few games are still mostly noise (singles came out near
break-even, and the locked card won 5 of 9). The holdout (21 Mar–Jun 2026) waits for OddsPapi's
November allowance. Treat the first weeks as a live test: **stake 0.5% of the bankroll per single
and per card** (half the NCAAB stake), record every pick, and grade them.

## One-time setup

1. Get a free key at [the-odds-api.com](https://the-odds-api.com) (Starter plan: 500 credits a month).
2. In the cloud environment's settings, add it as the environment variable **`THE_ODDS_API_KEY`**.
3. Start a new session; it picks the key up.

Each run costs 2 credits (EuroLeague totals, EU + UK bookmakers), so 500 credits cover about
250 runs a month. The source has EuroLeague only; EuroCup needs OddsPapi (`data/oddspapi.py`),
whose free allowance resets on the 1st of each month.

## When to run it

The value is largest right after Pinnacle posts a game, typically around **13:00 Madrid time the
day before**, and about half of it is gone 30–60 minutes later. By game-day morning most of it
has gone; some comes back in the last 3–6 hours before tip-off. In practice:

* **Every EuroLeague day at about 13:15–14:00 Madrid time.** This catches the next day's games
  near Pinnacle's opening and the same day's games 5–7 hours before tip-off.
* Optionally a second run 2–4 hours before the evening's first tip.
* Place the bets right after the run; the prices move.

## Commands

```
python scripts/predict_euro.py --update --bankroll 10000 --record   # snapshot, picks, ledger
python scripts/grade_euro.py                                        # results + value against the close
python -m data.oddsapi usage                                        # credits left
```

Every snapshot is kept (`data/raw/oddsapi/snapshots/`), every game's Pinnacle line and model
total is logged (`reports/euro_live_games.csv`), and the picks go to `reports/live_ledger_euro.csv`.
The grade shows wins and losses and each pick's value against Pinnacle's last price before
tip-off. That second number is the one to watch: if it stays positive over 100+ bets, the edge
is real even while results swing.
