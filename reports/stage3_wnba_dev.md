# Stage 3 — WNBA opening-line engine: development (2021, 2022)

Data: 1997 WNBA games 2019-2026 with final scores (1989 with a usable opener); box scores matched for 100%. Test seasons (2023-26) removed before fitting. Odds start in 2019, so 2019-20 are training history only.

Log-loss gain of each variant's probability over the market-only model at the real opener (×10⁻⁴; uncalibrated, since calibration needs two earlier predicted seasons and starts in 2023):

| variant | season | games | ll_gain_x1e4 | bets_p>=55% | win_p>=55% | ci95 |
|---|---|---|---|---|---|---|
| W1_same_as_ncaab | 2021 | 188 | -16.349 | 83 | 0.518 | 0.412–0.622 |
| W1_same_as_ncaab | 2022 | 216 | -257.877 | 131 | 0.466 | 0.382–0.551 |
| W1_same_as_ncaab | DEV POOLED | 404 | -145.483 | 214 | 0.486 | 0.420–0.553 |
| W3_no_style | 2021 | 188 | -121.702 | 108 | 0.472 | 0.381–0.566 |
| W3_no_style | 2022 | 216 | -188.893 | 98 | 0.459 | 0.364–0.558 |
| W3_no_style | DEV POOLED | 404 | -157.626 | 206 | 0.466 | 0.399–0.534 |

**Rule:** choose the variant with the best pooled development gain → **W1_same_as_ncaab** (-145.5×10⁻⁴). Locked in `config/stage3_wnba_locked.yaml`.

