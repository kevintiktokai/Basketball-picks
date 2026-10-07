# Stage 2 — NCAAB holdout report (locked engine, run once)

Locked at revision `752af4b`; market `open`; model `it10_open_style`; card policy: buffered lines, conservative joint ≥ 0.625, max buffer 15 pts.

## 1. Two-pick card results by stage

| stage | slates | cards | 2of2 | rate_2of2 | ci95 | leg_win | avg_leg_p | model_joint | avg_buffer | dbl_odds | roi_open_px | roi_close_px |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEVELOPMENT (disc+val) | 870 | 870 | 572 | 0.657 | 0.625–0.688 | 0.811 | 0.800 | 0.638 | 10.711 | 1.704 | 0.123 | 0.031 |
| FINAL HOLDOUT 2018-21 | 363 | 363 | 221 | 0.609 | 0.558–0.658 | 0.787 | 0.798 | 0.635 | 10.352 | 1.736 | 0.060 | -0.069 |

### Holdout by season

| season | cards | 2of2 | 1of2 | 0of2 | rate_2of2 | ci95 | model_joint | roi_open_px_4.5% | roi_close_px_4.5% |
|---|---|---|---|---|---|---|---|---|---|
| 2018-19 | 135 | 79 | 46 | 10 | 0.585 | 0.501–0.665 | 0.637 | 0.043 | -0.085 |
| 2019-20 | 116 | 73 | 41 | 2 | 0.629 | 0.539–0.712 | 0.636 | 0.103 | -0.034 |
| 2020-21 | 112 | 69 | 42 | 1 | 0.616 | 0.524–0.701 | 0.633 | 0.034 | -0.087 |

Leg independence in holdout cards: leg A 78.5%, leg B 78.8%, product 61.9%, actual 2/2 60.9%, outcome corr -0.058.

* both Over: 183 cards, 2/2 60.1%
* both Under: 67 cards, 2/2 67.2%
* mixed: 113 cards, 2/2 58.4%

Longest run of non-2/2 cards: 6. Max drawdown of the 1-unit double (open-priced, 4.5% margin): 11.2 units.

## 2. Pricing scenarios for the holdout cards (EV is assumption-dependent)

| alt price reference | margin per leg | avg double odds | ROI per card | break-even 2/2 rate |
|---|---|---|---|---|
| open | 0.045 | 1.736 | 0.060 | 0.578 |
| close | 0.045 | 1.540 | -0.069 | 0.654 |
| open | 0.080 | 1.613 | -0.016 | 0.622 |
| close | 0.080 | 1.431 | -0.135 | 0.704 |

No historical alternate-line prices exist in the data, so these are scenarios: the market-only distribution around the stated line, minus the stated margin per leg.

## 3. Main-line (no buffer) two-sided performance, holdout

Log loss model 0.69017 vs market-only 0.69325 (gain +30.9×10⁻⁴) over 12481 games.

| two-sided P bucket | bets | pred | win | ci95 | roi_at_1.909 |
|---|---|---|---|---|---|
| 50%-55% | 7855 | 0.522 | 0.524 | 0.513–0.535 | -0.000 |
| 55%-60% | 2621 | 0.568 | 0.561 | 0.542–0.580 | 0.071 |
| 60%-65% | 303 | 0.614 | 0.611 | 0.555–0.664 | 0.166 |
| 65%-100% | 9 | 0.660 | 0.333 | 0.121–0.646 | -0.364 |

Main-line top-2 card every slate (no buffer): 363 cards, 2/2 35.5% (CI 30.8%–40.6%).

## 4. Closing-line value of the chosen legs (holdout)

Average open→close line move in the direction of our bet: +2.45 points (share of legs where the market moved our way: 83.2%, against: 12.0%).

