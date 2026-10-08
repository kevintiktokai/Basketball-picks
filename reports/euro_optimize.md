# Europe: optimising the two-leg card strategy (development games)

Development games: **144** (2026-01-20 .. 2026-03-20 plus 3 samples), 30 match dates; strategies tried: **1680** (7 decision times x 240 leg/card rules). Objective: mean joint CLV per card against Pinnacle's close.

## Honest estimate (nested time split)

Choose the best strategy on one half of the dates, then score it on the other half. This is what to expect from the selection procedure on unseen games.

| selected on | decision_time | leg_ev_min | leg_odds_band | books | model_agrees | cards_per_date | selection-half CLV | scored on | cards | CLV | both won | ROI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| first half | pinnacle_open | 0.050 | 1.700–2.100 | 1xbet | False | all_disjoint | 0.172 | second half | 1 | 0.089 | 0.000 | -1.000 |
| second half | pinnacle_open | 0.010 | 1.700–2.100 | all_soft | True | 1 | 0.080 | first half | 5 | 0.166 | 0.600 | 1.304 |

## Selected strategy (best on all development games, >= 8 cards)

```
decision_time: pinnacle_open
leg_ev_min: 0.01
leg_odds_band:
- 1.7
- 2.1
books: all_soft
model_agrees: true
cards_per_date: '1'
min_combined_odds: 2.5
```

| cards | dates | mean odds | mean EV | mean CLV | CLV > 0 | both won | break-even | ROI | profit (units) | max drawdown | longest losing run | ROI 95% CI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | 9 | 3.682 | 0.122 | 0.128 | 1.000 | 0.556 | 0.273 | 1.127 | 10.145 | 3.000 | 3 | -0.150–2.390 |

Baseline (Q4 rule: when Pinnacle opens, any positive EV, legs 1.40-1.90, all books, one card per date): 17 cards, CLV +0.073, both won 0.294, ROI -0.058.

How often each setting appears among the 15 best strategies (robustness):

* decision_time: {'pinnacle_open': 15}
* leg_ev_min: {'0.0': 6, '0.01': 4, '0.03': 3, '0.05': 1, '0.02': 1}
* leg_odds_band: {'(1.7, 2.1)': 12, '(1.4, 1.9)': 3}
* books: {'all_soft': 11, '1xbet': 4}
* model_agrees: {'True': 10, 'False': 5}
* cards_per_date: {'all_disjoint': 8, '1': 7}

## Every card of the selected strategy (the backtest)

| date | leg_a | leg_b | odds | ev | clv | win | pnl | cum_units |
|---|---|---|---|---|---|---|---|---|
| 2026-01-29 | betway under 165.5 @1.71 | 1xbet under 167.5 @2.03 | 3.485 | 0.109 | 0.124 | True | 2.485 | 2.485 |
| 2026-01-30 | 1xbet under 172.5 @2.03 | 1xbet under 171.5 @1.92 | 3.903 | 0.116 | 0.115 | True | 2.903 | 5.388 |
| 2026-02-03 | 1xbet over 170.5 @2.03 | 1xbet over 173.5 @2.03 | 4.133 | 0.139 | 0.258 | True | 3.133 | 8.521 |
| 2026-02-05 | 1xbet under 168.5 @2.03 | 1xbet under 176.5 @1.85 | 3.767 | 0.088 | 0.034 | False | -1.000 | 7.521 |
| 2026-02-06 | 1xbet over 173.5 @1.73 | 1xbet under 172.5 @1.93 | 3.329 | 0.203 | 0.301 | False | -1.000 | 6.521 |
| 2026-02-26 | betway under 180.5 @1.75 | betway over 179.5 @1.91 | 3.341 | 0.123 | 0.036 | False | -1.000 | 5.521 |
| 2026-03-05 | betway over 176.5 @2.05 | 1xbet under 170.5 @2.03 | 4.168 | 0.144 | 0.085 | True | 3.168 | 8.689 |
| 2026-03-11 | 1xbet under 165.5 @2.03 | betway over 165.5 @1.75 | 3.558 | 0.079 | 0.153 | False | -1.000 | 7.689 |
| 2026-03-12 | 1xbet over 177.5 @1.92 | betway under 168.5 @1.80 | 3.456 | 0.099 | 0.046 | True | 2.456 | 10.145 |

## Caveats

* About 100 usable games: the best of hundreds of strategies is flattered by selection; trust the nested estimate and the holdout, not the in-sample ROI.
* Results depend on the soft-book prices in the OddsPapi feed being available when shown; a live check of prices is part of the forward test.
* Execution: these cards act the instant Pinnacle opens. A person acting 30-60 minutes later keeps about half the value (CLV +6.5% / +6.1% for the locked strategy); see [`euro_execution.md`](euro_execution.md). The holdout's primary arm is therefore +30 minutes.
* Locked in `config/europe_locked.yaml`; next checks: holdout (21 Mar - Jun 2026, once fetched), then the 2026-27 test.
