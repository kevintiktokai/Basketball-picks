# CORRECTED results — book-outlier guard (post-test data-quality fix)

_See the module docstring: books whose opener is > 3 pts from the cross-book median are ignored when shopping for the best number. Original one-time reports are unchanged; these corrected figures are not pristine because the originals had been seen._

## NCAAB 2021-26 (re-analysis) — stage-3 products, corrected

| product | season | cards | pct_slates | hit | hit_ci95 | avg_odds | breakeven | model_hit | leg_win | leg_p | roi | roi_ci95 | units | max_dd | losing_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | POOLED | 664 | 0.969 | 0.468 | 0.431–0.506 | 2.571 | 0.391 | 0.447 | 0.676 | 0.669 | 0.199 | 0.104–0.295 | 132.300 | 13.447 | 8 |
|   sensitivity: alternate margin 8% | POOLED | 654 | 0.955 | 0.430 | 0.392–0.468 | 2.701 | 0.375 | 0.414 | 0.654 | 0.644 | 0.151 | 0.047–0.256 | 98.501 | 22.648 | 11 |
|   stress: alternates priced off the CLOSE | POOLED | 664 | 0.969 | 0.468 | 0.431–0.506 | 2.346 | 0.435 | 0.447 | 0.676 | 0.669 | 0.088 | 0.001–0.178 | 58.363 | 15.057 | 8 |
|   variant: alternates shopped at best book | POOLED | 664 | 0.969 | 0.483 | 0.446–0.521 | 2.523 | 0.397 | 0.480 | 0.695 | 0.693 | 0.220 | 0.126–0.312 | 145.884 | 15.791 | 9 |
| MAIN-LINE DOUBLE (real prices only) | POOLED | 652 | 0.952 | 0.356 | 0.320–0.393 | 3.644 | 0.275 | 0.348 | 0.590 | 0.589 | 0.290 | 0.163–0.426 | 188.970 | 17.063 | 13 |

## NCAAB 2021-26 — stage-2b secondary figures, corrected

* v2 buffered cards, line-shopping variant: 435/664 = 65.5% (CI 61.8%–69.0%)
| two-sided P | bets | win_best_book | ci95 | roi_best_book_real_price |
|---|---|---|---|---|
| 50%-55% | 18655 | 0.531 | 0.524–0.538 | 0.011 |
| 55%-60% | 3526 | 0.579 | 0.562–0.595 | 0.102 |
| 60%-100% | 80 | 0.575 | 0.466–0.677 | 0.099 |

* v3 buffered cards, line-shopping variant: 444/664 = 66.9% (CI 63.2%–70.3%)
| two-sided P | bets | win_best_book | ci95 | roi_best_book_real_price |
|---|---|---|---|---|
| 50%-55% | 18345 | 0.534 | 0.527–0.541 | 0.018 |
| 55%-60% | 3268 | 0.576 | 0.559–0.593 | 0.097 |
| 60%-100% | 223 | 0.592 | 0.526–0.654 | 0.129 |

## NBA 2023-26 test — stage-3 products, corrected

| product | season | cards | pct_slates | hit | hit_ci95 | avg_odds | breakeven | model_hit | leg_win | leg_p | roi | roi_ci95 | units | max_dd | losing_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | 2023-24 | 179 | 0.869 | 0.352 | 0.286–0.424 | 3.275 | 0.312 | 0.332 | 0.570 | 0.575 | 0.110 | -0.115–0.350 | 19.619 | 15.802 | 14 |
| TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | 2024-25 | 181 | 0.858 | 0.359 | 0.293–0.431 | 3.080 | 0.333 | 0.358 | 0.610 | 0.597 | 0.098 | -0.120–0.306 | 17.740 | 20.843 | 16 |
| TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | 2025-26 | 183 | 0.876 | 0.328 | 0.264–0.399 | 2.886 | 0.354 | 0.379 | 0.568 | 0.615 | -0.090 | -0.271–0.107 | -16.405 | 37.301 | 11 |
| TARGET CARD (locked: ~1.6 legs, >=2.5, max win prob) | POOLED | 543 | 0.867 | 0.346 | 0.307–0.387 | 3.079 | 0.333 | 0.356 | 0.583 | 0.595 | 0.039 | -0.084–0.161 | 20.954 | 55.262 | 16 |
|   sensitivity: alternate margin 8% | 2023-24 | 169 | 0.820 | 0.343 | 0.276–0.418 | 3.531 | 0.285 | 0.305 | 0.541 | 0.552 | 0.202 | -0.052–0.450 | 34.163 | 14.601 | 10 |
|   sensitivity: alternate margin 8% | 2024-25 | 170 | 0.806 | 0.335 | 0.269–0.409 | 3.419 | 0.297 | 0.320 | 0.582 | 0.565 | 0.123 | -0.104–0.374 | 20.978 | 19.079 | 13 |
|   sensitivity: alternate margin 8% | 2025-26 | 168 | 0.804 | 0.333 | 0.266–0.408 | 3.300 | 0.309 | 0.334 | 0.551 | 0.577 | 0.045 | -0.177–0.254 | 7.553 | 21.897 | 10 |
|   sensitivity: alternate margin 8% | POOLED | 507 | 0.810 | 0.337 | 0.297–0.380 | 3.417 | 0.297 | 0.320 | 0.558 | 0.565 | 0.124 | -0.018–0.263 | 62.693 | 32.961 | 13 |
|   stress: alternates priced off the CLOSE | 2023-24 | 179 | 0.869 | 0.352 | 0.286–0.424 | 3.168 | 0.332 | 0.332 | 0.570 | 0.575 | 0.054 | -0.167–0.285 | 9.638 | 15.802 | 14 |
|   stress: alternates priced off the CLOSE | 2024-25 | 181 | 0.858 | 0.359 | 0.293–0.431 | 2.947 | 0.361 | 0.358 | 0.610 | 0.597 | 0.023 | -0.187–0.221 | 4.102 | 21.007 | 16 |
|   stress: alternates priced off the CLOSE | 2025-26 | 183 | 0.876 | 0.328 | 0.264–0.399 | 2.736 | 0.386 | 0.379 | 0.568 | 0.615 | -0.153 | -0.328–0.033 | -28.031 | 41.824 | 11 |
|   stress: alternates priced off the CLOSE | POOLED | 543 | 0.867 | 0.346 | 0.307–0.387 | 2.949 | 0.360 | 0.356 | 0.583 | 0.595 | -0.026 | -0.145–0.091 | -14.290 | 60.142 | 16 |
|   variant: alternates shopped at best book | 2023-24 | 183 | 0.888 | 0.443 | 0.373–0.515 | 2.641 | 0.383 | 0.417 | 0.656 | 0.645 | 0.136 | -0.050–0.320 | 24.966 | 15.410 | 6 |
|   variant: alternates shopped at best book | 2024-25 | 182 | 0.863 | 0.368 | 0.301–0.440 | 2.605 | 0.387 | 0.426 | 0.624 | 0.652 | -0.063 | -0.244–0.119 | -11.546 | 22.010 | 11 |
|   variant: alternates shopped at best book | 2025-26 | 185 | 0.885 | 0.389 | 0.322–0.461 | 2.555 | 0.392 | 0.436 | 0.627 | 0.660 | -0.001 | -0.177–0.188 | -0.148 | 19.377 | 8 |
|   variant: alternates shopped at best book | POOLED | 550 | 0.879 | 0.400 | 0.360–0.442 | 2.600 | 0.388 | 0.427 | 0.635 | 0.653 | 0.024 | -0.081–0.131 | 13.272 | 35.443 | 11 |
| MAIN-LINE DOUBLE (real prices only) | 2023-24 | 154 | 0.748 | 0.299 | 0.232–0.375 | 3.647 | 0.274 | 0.312 | 0.552 | 0.559 | 0.055 | -0.193–0.316 | 8.469 | 12.808 | 10 |
| MAIN-LINE DOUBLE (real prices only) | 2024-25 | 158 | 0.749 | 0.285 | 0.220–0.360 | 3.643 | 0.275 | 0.317 | 0.547 | 0.562 | 0.037 | -0.217–0.311 | 5.864 | 14.169 | 10 |
| MAIN-LINE DOUBLE (real prices only) | 2025-26 | 178 | 0.852 | 0.264 | 0.205–0.333 | 3.640 | 0.275 | 0.318 | 0.520 | 0.564 | -0.037 | -0.263–0.208 | -6.543 | 25.481 | 15 |
| MAIN-LINE DOUBLE (real prices only) | POOLED | 490 | 0.783 | 0.282 | 0.244–0.323 | 3.643 | 0.275 | 0.316 | 0.539 | 0.562 | 0.016 | -0.136–0.160 | 7.790 | 27.836 | 15 |

### NBA singles at the best book (corrected)

| two-sided P | bets | win_best_book | ci95 | roi_best_book_real_price |
|---|---|---|---|---|
| 50%-55% | 3054 | 0.535 | 0.517–0.552 | 0.020 |
| 55%-60% | 275 | 0.602 | 0.543–0.658 | 0.150 |
| 60%-100% | 8 | 0.625 | 0.306–0.863 | 0.193 |
