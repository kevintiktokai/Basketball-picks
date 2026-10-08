# Stage 3 — NBA opening-line engine: development (2021-22, 2022-23)

Archive seasons (2007-21) supply history with a single line used as both open and close; 2021-22 onward use real openers (median of up to 6 books).

| variant | season | games | ll_gain_x1e4 | max_p | bets_p>=55% | win_p>=55% | ci95 |
|---|---|---|---|---|---|---|---|
| N1_same_as_ncaab | 2021-22 | 1227 | -29.809 | 0.699 | 612 | 0.529 | 0.490–0.569 |
| N1_same_as_ncaab | 2022-23 | 1260 | 13.092 | 0.640 | 87 | 0.540 | 0.436–0.641 |
| N1_same_as_ncaab | DEV POOLED | 2487 | -8.074 | 0.699 | 699 | 0.531 | 0.494–0.567 |
| N2_plus_real_open_interactions | 2021-22 | 1227 | -29.809 | 0.699 | 612 | 0.529 | 0.490–0.569 |
| N2_plus_real_open_interactions | 2022-23 | 1260 | 8.731 | 0.631 | 64 | 0.469 | 0.352–0.589 |
| N2_plus_real_open_interactions | DEV POOLED | 2487 | -10.283 | 0.699 | 676 | 0.524 | 0.486–0.561 |
| N3_no_style | 2021-22 | 1227 | 19.457 | 0.643 | 310 | 0.558 | 0.502–0.612 |
| N3_no_style | 2022-23 | 1260 | -4.464 | 0.635 | 106 | 0.528 | 0.434–0.621 |
| N3_no_style | DEV POOLED | 2487 | 7.338 | 0.643 | 416 | 0.550 | 0.502–0.598 |

**Rule:** choose the variant with the best pooled development log-loss gain at the real opener → **N3_no_style** (+7.3×10⁻⁴).

## Locked stage-3 products on the development seasons (informational)

| product | season | cards | pct_slates | hit | hit_ci95 | avg_odds | breakeven | model_hit | leg_win | leg_p | roi | roi_ci95 | units | max_dd | losing_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| [dev] TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | 2021-22 | 185 | 0.894 | 0.384 | 0.317–0.456 | 2.831 | 0.361 | 0.396 | 0.614 | 0.628 | 0.051 | -0.148–0.246 | 9.527 | 14.446 | 7 |
| [dev] TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | 2022-23 | 182 | 0.883 | 0.368 | 0.301–0.440 | 3.100 | 0.331 | 0.358 | 0.613 | 0.597 | 0.108 | -0.115–0.333 | 19.592 | 19.391 | 11 |
| [dev] TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | POOLED | 367 | 0.889 | 0.376 | 0.328–0.427 | 2.964 | 0.346 | 0.377 | 0.613 | 0.613 | 0.079 | -0.063–0.231 | 29.119 | 20.506 | 11 |
| [dev]   sensitivity: alternate margin 8% | 2021-22 | 184 | 0.889 | 0.370 | 0.303–0.441 | 3.250 | 0.315 | 0.351 | 0.603 | 0.591 | 0.172 | -0.050–0.404 | 31.611 | 9.061 | 7 |
| [dev]   sensitivity: alternate margin 8% | 2022-23 | 171 | 0.830 | 0.339 | 0.272–0.413 | 3.413 | 0.297 | 0.327 | 0.564 | 0.571 | 0.128 | -0.096–0.368 | 21.823 | 21.657 | 10 |
| [dev]   sensitivity: alternate margin 8% | POOLED | 355 | 0.860 | 0.355 | 0.307–0.406 | 3.328 | 0.306 | 0.340 | 0.585 | 0.581 | 0.151 | -0.018–0.320 | 53.434 | 21.657 | 10 |
| [dev]   stress: alternates priced off the CLOSE | 2021-22 | 185 | 0.894 | 0.384 | 0.317–0.456 | 2.905 | 0.372 | 0.396 | 0.614 | 0.628 | 0.012 | -0.185–0.210 | 2.282 | 15.586 | 7 |
| [dev]   stress: alternates priced off the CLOSE | 2022-23 | 182 | 0.883 | 0.368 | 0.301–0.440 | 2.977 | 0.352 | 0.358 | 0.613 | 0.597 | 0.060 | -0.154–0.278 | 10.986 | 20.651 | 11 |
| [dev]   stress: alternates priced off the CLOSE | POOLED | 367 | 0.889 | 0.376 | 0.328–0.427 | 2.941 | 0.362 | 0.377 | 0.613 | 0.613 | 0.036 | -0.107–0.185 | 13.268 | 27.865 | 11 |
| [dev]   variant: alternates shopped at best book | 2021-22 | 185 | 0.894 | 0.432 | 0.363–0.504 | 2.572 | 0.391 | 0.463 | 0.662 | 0.679 | 0.099 | -0.083–0.282 | 18.271 | 14.293 | 7 |
| [dev]   variant: alternates shopped at best book | 2022-23 | 184 | 0.893 | 0.462 | 0.391–0.534 | 2.634 | 0.383 | 0.452 | 0.685 | 0.671 | 0.208 | 0.021–0.396 | 38.250 | 14.419 | 8 |
| [dev]   variant: alternates shopped at best book | POOLED | 369 | 0.893 | 0.447 | 0.397–0.498 | 2.603 | 0.387 | 0.458 | 0.673 | 0.675 | 0.153 | 0.018–0.290 | 56.520 | 27.186 | 8 |
| [dev] MAIN-LINE DOUBLE (real prices only) | 2021-22 | 173 | 0.836 | 0.306 | 0.242–0.379 | 3.643 | 0.274 | 0.351 | 0.543 | 0.592 | 0.107 | -0.137–0.360 | 18.476 | 12.208 | 8 |
| [dev] MAIN-LINE DOUBLE (real prices only) | 2022-23 | 165 | 0.801 | 0.345 | 0.277–0.421 | 3.643 | 0.275 | 0.350 | 0.600 | 0.591 | 0.258 | 0.014–0.545 | 42.582 | 11.000 | 11 |
| [dev] MAIN-LINE DOUBLE (real prices only) | POOLED | 338 | 0.818 | 0.325 | 0.278–0.377 | 3.643 | 0.274 | 0.350 | 0.571 | 0.591 | 0.181 | 0.013–0.358 | 61.058 | 19.867 | 11 |

