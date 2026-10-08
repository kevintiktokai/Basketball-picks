# NBA: effect of the possessions fix on the development seasons

Mean predicted possessions: as locked **50.7**, fixed **101.4** (actual box-score average 103.4).

Locked NBA variant (N3_no_style), walk-forward, development seasons only; the 2023-26 test seasons are removed before modelling. `ll_gain` is the log-loss gain over the market-only model at the opener (×10⁻⁴; higher is better).

| ratings | season | games | ll_gain_x1e4 | bets_p>=55% | win_p>=55% | ci95 |
|---|---|---|---|---|---|---|
| as locked (bug) | 2021-22 | 1227 | 19.457 | 310 | 0.558 | 0.502–0.612 |
| as locked (bug) | 2022-23 | 1260 | -4.464 | 106 | 0.528 | 0.434–0.621 |
| as locked (bug) | DEV POOLED | 2487 | 7.338 | 416 | 0.550 | 0.502–0.598 |
| venue_tempo fixed | 2021-22 | 1227 | 20.161 | 296 | 0.544 | 0.487–0.600 |
| venue_tempo fixed | 2022-23 | 1260 | -5.780 | 116 | 0.534 | 0.444–0.623 |
| venue_tempo fixed | DEV POOLED | 2487 | 7.018 | 412 | 0.541 | 0.493–0.589 |

