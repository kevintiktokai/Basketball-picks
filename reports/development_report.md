# OVER ENGINE — Development report (discovery + validation only)

Dataset `nba-v1`. Holdout seasons ['2021-22', '2022-23', '2023-24'] and live-sim seasons ['2024-25', '2025-26'] were NOT predicted by this run.

## 1. Dataset

| season | games | over_rate | push_rate | mean_line | resid_sd | line_mae |
|---|---|---|---|---|---|---|
| 2007-08 | 1316 | 0.479 | 0.014 | 198.948 | 18.180 | 14.268 |
| 2008-09 | 1315 | 0.490 | 0.011 | 199.073 | 17.848 | 14.100 |
| 2009-10 | 1312 | 0.479 | 0.021 | 200.486 | 16.959 | 13.303 |
| 2010-11 | 1307 | 0.475 | 0.015 | 198.727 | 17.564 | 13.891 |
| 2011-12 | 1070 | 0.488 | 0.012 | 191.631 | 17.259 | 13.430 |
| 2012-13 | 1311 | 0.497 | 0.014 | 195.554 | 17.564 | 13.775 |
| 2013-14 | 1317 | 0.509 | 0.013 | 200.580 | 17.265 | 13.712 |
| 2014-15 | 1309 | 0.477 | 0.015 | 200.136 | 17.608 | 13.609 |
| 2015-16 | 1316 | 0.482 | 0.011 | 204.728 | 17.727 | 13.715 |
| 2016-17 | 1304 | 0.495 | 0.019 | 210.613 | 17.469 | 13.841 |
| 2017-18 | 1311 | 0.473 | 0.014 | 212.380 | 18.231 | 14.603 |
| 2018-19 | 1312 | 0.485 | 0.013 | 221.408 | 18.928 | 14.766 |
| 2019-20 | 1141 | 0.511 | 0.006 | 222.209 | 19.099 | 15.131 |
| 2020-21 | 1167 | 0.493 | 0.004 | 224.431 | 18.740 | 14.727 |

The closing total is an extremely strong predictor: mean absolute error ≈14 points, residual SD ≈17–19, Over rate within a few points of 50% every season.

## 2. Model comparison and ablation (walk-forward, season refit)

Common evaluation sample: 8207 games (calibrated, ≥5 games played, non-push) in seasons 2014-15..2020-21 — the seasons where every model (including box-score models) has a calibrated walk-forward prediction.

`gain_vs_mkt` = mean per-bet log-loss improvement over the market-only model (×10⁻⁴), 95% CI from a date-clustered bootstrap. A coin flip has log loss 0.6931.

| features | learner | dist | calib | n | logloss | gain_vs_mkt_x1e4 | gain_ci_x1e4 | brier | ece | rmse_resid | max_p_cal | n_p>=0.55 | win_p>=0.55 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F5_rest_home | ridge | normal | platt | 8207 | 0.6918 | 13.6362 | 2.769–24.094 | 0.2493 | 0.0164 | 18.2345 | 0.6288 | 239 | 0.5397 |
| F4_matchup | ridge | normal | platt | 8207 | 0.6918 | 13.2135 | 3.540–22.176 | 0.2493 | 0.0142 | 18.2325 | 0.5728 | 101 | 0.5743 |
| F6_market | ridge | normal | platt | 8207 | 0.6920 | 11.4965 | 0.324–21.928 | 0.2494 | 0.0174 | 18.2436 | 0.6477 | 388 | 0.5258 |
| S_scores_full | ridge | normal | none | 8207 | 0.6921 | 9.8811 | -2.509–23.094 | 0.2495 | 0.0129 | 18.2491 | 0.6461 | 337 | 0.5401 |
| S_scores_full | ridge | normal | platt | 8207 | 0.6922 | 9.6990 | 2.910–16.998 | 0.2495 | 0.0083 | 18.2491 | 0.5863 | 28 | 0.5357 |
| S_scores_full | ridge | empirical | platt | 8207 | 0.6922 | 9.4727 | 2.968–16.510 | 0.2495 | 0.0126 | 18.2491 | 0.5963 | 41 | 0.5366 |
| F8_trends | ridge | normal | platt | 8207 | 0.6922 | 8.9652 | -3.820–20.409 | 0.2495 | 0.0192 | 18.2374 | 0.6727 | 582 | 0.5258 |
| F7_context | ridge | normal | platt | 8207 | 0.6923 | 8.7056 | -3.052–19.475 | 0.2496 | 0.0186 | 18.2404 | 0.6619 | 490 | 0.5224 |
| F6_market | ensemble | normal | platt | 8207 | 0.6923 | 8.5363 | 0.018–17.128 | 0.2496 | 0.0192 | 18.2558 | 0.5954 | 244 | 0.5123 |
| F3_pace_eff | ridge | normal | platt | 8207 | 0.6924 | 8.1552 | -0.062–15.729 | 0.2496 | 0.0123 | 18.2517 | 0.5701 | 31 | 0.5806 |
| F2_ratings | ridge | normal | platt | 8207 | 0.6924 | 8.0127 | 1.466–13.914 | 0.2496 | 0.0138 | 18.2592 | 0.5564 | 7 | 0.8571 |
| F5_rest_home | ensemble | normal | platt | 8207 | 0.6924 | 7.7913 | 1.105–14.815 | 0.2496 | 0.0123 | 18.2590 | 0.5700 | 19 | 0.6316 |
| F7_context | ensemble | normal | platt | 8207 | 0.6924 | 7.1721 | -2.206–16.143 | 0.2496 | 0.0104 | 18.2540 | 0.6068 | 330 | 0.5273 |
| F8_trends | ensemble | normal | platt | 8207 | 0.6925 | 6.8579 | -3.143–16.530 | 0.2497 | 0.0150 | 18.2526 | 0.6134 | 387 | 0.5245 |
| F4_matchup | ensemble | normal | platt | 8207 | 0.6925 | 6.8391 | 0.051–14.240 | 0.2497 | 0.0104 | 18.2593 | 0.5576 | 13 | 0.6154 |
| S_scores_core | ridge | normal | platt | 8207 | 0.6926 | 5.3525 | 0.958–9.929 | 0.2497 | 0.0130 | 18.2572 | 0.5376 | 0 | — |
| S_scores_full | ensemble | normal | platt | 8207 | 0.6927 | 4.6835 | 0.064–9.120 | 0.2498 | 0.0139 | 18.2684 | 0.5497 | 0 | — |
| F3_pace_eff | ensemble | normal | platt | 8207 | 0.6928 | 3.8061 | -1.918–9.355 | 0.2498 | 0.0128 | 18.2762 | 0.5532 | 2 | 0.0000 |
| S_scores_core | ensemble | normal | platt | 8207 | 0.6928 | 3.3401 | 0.336–6.386 | 0.2498 | 0.0128 | 18.2677 | 0.5280 | 0 | — |
| F1_naive_ppg | ridge | normal | platt | 8207 | 0.6928 | 3.3188 | -0.766–7.870 | 0.2498 | 0.0124 | 18.2685 | 0.5405 | 0 | — |
| F6_market | lgbm | normal | platt | 8207 | 0.6928 | 3.1136 | -2.940–9.131 | 0.2498 | 0.0074 | 18.3142 | 0.5598 | 21 | 0.5714 |
| F7_context | lgbm | normal | platt | 8207 | 0.6929 | 2.9049 | -2.916–9.251 | 0.2499 | 0.0084 | 18.3151 | 0.5650 | 28 | 0.5357 |
| S_scores_full | ridge | normal | isotonic | 8207 | 0.6929 | 2.4654 | -10.490–15.390 | 0.2497 | 0.0175 | 18.2491 | 0.9900 | 74 | 0.5811 |
| F8_trends | lgbm | normal | platt | 8207 | 0.6929 | 2.0857 | -3.950–8.602 | 0.2499 | 0.0081 | 18.3197 | 0.5670 | 43 | 0.4651 |
| F5_rest_home | lgbm | normal | platt | 8207 | 0.6930 | 1.4992 | -2.291–5.689 | 0.2499 | 0.0094 | 18.3265 | 0.5348 | 0 | — |
| F2_ratings | ensemble | normal | platt | 8207 | 0.6930 | 1.4373 | 0.233–2.555 | 0.2499 | 0.0079 | 18.2724 | 0.5172 | 0 | — |
| F4_matchup | lgbm | normal | platt | 8207 | 0.6930 | 1.0516 | -3.486–5.942 | 0.2500 | 0.0084 | 18.3270 | 0.5461 | 0 | — |
| S_scores_core | lgbm | normal | platt | 8207 | 0.6931 | 1.0058 | -0.441–2.435 | 0.2500 | 0.0124 | 18.2992 | 0.5168 | 0 | — |
| F8_trends | ridge | normal | none | 8207 | 0.6931 | 0.4782 | -23.468–21.843 | 0.2499 | 0.0255 | 18.2374 | 0.7579 | 1818 | 0.5314 |
| F1_naive_ppg | ensemble | normal | platt | 8207 | 0.6931 | 0.6877 | -0.229–1.579 | 0.2500 | 0.0125 | 18.2746 | 0.5181 | 0 | — |
| S_scores_full | lgbm | normal | platt | 8207 | 0.6931 | 0.3037 | -2.015–2.718 | 0.2500 | 0.0105 | 18.3121 | 0.5210 | 0 | — |
| F0_market_only | mean | normal | platt | 8207 | 0.6932 | 0.0000 | 0.000–0.000 | 0.2500 | 0.0123 | 18.2824 | 0.4986 | 0 | — |
| F3_pace_eff | lgbm | normal | platt | 8207 | 0.6932 | -0.1502 | -3.997–3.453 | 0.2500 | 0.0104 | 18.3299 | 0.5367 | 0 | — |
| F1_naive_ppg | lgbm | normal | platt | 8207 | 0.6932 | -0.2733 | -1.350–0.866 | 0.2500 | 0.0203 | 18.2921 | 0.5047 | 0 | — |
| F2_ratings | lgbm | normal | platt | 8207 | 0.6932 | -0.6435 | -2.102–0.876 | 0.2500 | 0.0176 | 18.3021 | 0.5098 | 0 | — |
| F8_trends | ridge | normal | isotonic | 8207 | 0.6956 | -25.9073 | -69.797–6.664 | 0.2503 | 0.0189 | 18.2374 | 0.9900 | 953 | 0.5194 |

**Locked model (pre-stated rule):** features `S_scores_full`, learner `ridge`, distribution `normal`, calibration `platt`. Gain vs market 9.7×10⁻⁴ (95% CI 2.9..17.0); statistically distinguishable from the market.

_Disclosure: the first development run applied the score-only preference without the positive-lower-bound requirement stated in the rule and locked an uncalibrated variant (gain CI −2.5..23.1). That implementation bug was fixed to match the stated rule before any holdout evaluation; no thresholds were changed._

### Ablation ladder (ridge, normal, Platt)

| features | logloss | gain_vs_mkt_x1e4 | gain_ci_x1e4 | rmse_resid | max_p_cal |
|---|---|---|---|---|---|
| F0_market_only | 0.6932 | 0.0000 | 0.000–0.000 | 18.2824 | 0.4986 |
| F1_naive_ppg | 0.6928 | 3.3188 | -0.766–7.870 | 18.2685 | 0.5405 |
| F2_ratings | 0.6924 | 8.0127 | 1.466–13.914 | 18.2592 | 0.5564 |
| F3_pace_eff | 0.6924 | 8.1552 | -0.062–15.729 | 18.2517 | 0.5701 |
| F4_matchup | 0.6918 | 13.2135 | 3.540–22.176 | 18.2325 | 0.5728 |
| F5_rest_home | 0.6918 | 13.6362 | 2.769–24.094 | 18.2345 | 0.6288 |
| F6_market | 0.6920 | 11.4965 | 0.324–21.928 | 18.2436 | 0.6477 |
| F7_context | 0.6923 | 8.7056 | -3.052–19.475 | 18.2404 | 0.6619 |
| F8_trends | 0.6922 | 8.9652 | -3.820–20.409 | 18.2374 | 0.6727 |

## 3. Calibration of the locked model (all calibrated development games)

Brier 0.2497, log loss 0.6925, ECE 0.0093, n=11623.

| bucket | n | pred | actual | ci_lo | ci_hi | cal_err |
|---|---|---|---|---|---|---|
| 0%-50% | 8115 | 0.484 | 0.490 | 0.479 | 0.501 | 0.005 |
| 50%-55% | 3479 | 0.510 | 0.520 | 0.504 | 0.537 | 0.010 |
| 55%-60% | 28 | 0.559 | 0.536 | 0.358 | 0.705 | -0.024 |
| 60%-65% | 1 | 0.610 | 1.000 | 0.207 | 1.000 | 0.390 |
| 65%-70% | 0 | — | — | — | — | — |
| 70%-75% | 0 | — | — | — | — | — |
| 75%-100% | 0 | — | — | — | — | — |

## 4. Bet buckets (every calibrated game treated as a 1u Over bet at 1.909)

### Probability buckets

| bucket | n | pred | win | ci | roi | cal_err |
|---|---|---|---|---|---|---|
| <50% | 8217 | 0.484 | 0.490 | 0.479–0.501 | -0.064 | 0.005 |
| 50–54 | 3521 | 0.510 | 0.520 | 0.504–0.537 | -0.007 | 0.010 |
| 55–59 | 28 | 0.559 | 0.536 | 0.358–0.705 | 0.023 | -0.024 |
| 60–64 | 1 | 0.610 | 1.000 | 0.207–1.000 | 0.909 | 0.390 |
| 65–69 | 0 | — | — | None | — | — |
| 70–74 | 0 | — | — | None | — | — |
| 75%+ | 0 | — | — | None | — | — |

### Projection edge buckets (model total − line, points)

| bucket | n | pred | win | ci | roi | cal_err |
|---|---|---|---|---|---|---|
| <0 | 5278 | 0.479 | 0.480 | 0.466–0.493 | -0.083 | 0.001 |
| 0–1 | 4035 | 0.497 | 0.510 | 0.494–0.525 | -0.027 | 0.013 |
| 1–2 | 1879 | 0.509 | 0.521 | 0.499–0.544 | -0.005 | 0.012 |
| 2–3 | 427 | 0.521 | 0.517 | 0.469–0.564 | -0.013 | -0.004 |
| 3–4 | 97 | 0.535 | 0.552 | 0.453–0.648 | 0.053 | 0.017 |
| 4–5 | 41 | 0.549 | 0.585 | 0.434–0.722 | 0.117 | 0.037 |
| 5+ | 10 | 0.572 | 0.700 | 0.397–0.892 | 0.336 | 0.128 |

### Line ranges (NBA scale)

| bucket | n | pred | win | ci | roi | cal_err |
|---|---|---|---|---|---|---|
| <200 | 3417 | 0.491 | 0.509 | 0.492–0.526 | -0.028 | 0.018 |
| 200–209.5 | 2910 | 0.493 | 0.488 | 0.470–0.506 | -0.068 | -0.005 |
| 210–219.5 | 2730 | 0.494 | 0.500 | 0.481–0.519 | -0.045 | 0.006 |
| 220–229.5 | 1958 | 0.493 | 0.504 | 0.481–0.526 | -0.038 | 0.010 |
| 230–239.5 | 693 | 0.489 | 0.488 | 0.450–0.525 | -0.069 | -0.001 |
| 240+ | 59 | 0.483 | 0.441 | 0.322–0.567 | -0.159 | -0.042 |

### Season phase (games already played by the less-experienced team)

| bucket | n | pred | win | ci | roi | cal_err |
|---|---|---|---|---|---|---|
| 5–9 games | 772 | 0.479 | 0.487 | 0.451–0.522 | -0.069 | 0.008 |
| 10–29 | 3044 | 0.494 | 0.502 | 0.484–0.520 | -0.042 | 0.008 |
| 30–59 | 4474 | 0.495 | 0.507 | 0.493–0.522 | -0.031 | 0.013 |
| playoffs/play-in | 841 | 0.482 | 0.491 | 0.457–0.525 | -0.062 | 0.009 |
| 60+ (late) | 2636 | 0.494 | 0.489 | 0.470–0.508 | -0.066 | -0.005 |

### Stability by season — Overs with calibrated P ≥ 55%

| season | period | bets | win | roi |
|---|---|---|---|---|
| 2011-12 | discovery | 1 | 1.000 | 0.909 |
| 2012-13 | discovery | 0 | — | — |
| 2013-14 | discovery | 0 | — | — |
| 2014-15 | discovery | 3 | 0.333 | -0.364 |
| 2015-16 | discovery | 0 | — | — |
| 2016-17 | discovery | 1 | 0.000 | -1.000 |
| 2017-18 | validation | 7 | 0.429 | -0.182 |
| 2018-19 | validation | 0 | — | — |
| 2019-20 | validation | 12 | 0.667 | 0.273 |
| 2020-21 | validation | 5 | 0.600 | 0.145 |

## 5. Dependence between same-slate games

Same-day pairs: 50261 over 2024 dates.

* Correlation of Over outcomes: 0.0076 (95% CI -0.0010..0.0165)
* Correlation of standardized model errors: 0.0020 (95% CI -0.0063..0.0119)
* P(both Over) − P(Over)²: +0.0019 (95% CI -0.0002..+0.0041)

Individual probability each pick needs for P(both) = 60% (Gaussian copula):

* rho = 0.000: **77.5%** per pick
* rho = 0.002: **77.4%** per pick
* rho = 0.050: **77.2%** per pick
* rho = 0.100: **76.8%** per pick

The highest calibrated P(Over) the locked model produced on any development game was 61.0%; 0 games reached the 77.4% needed.

## 6. Two-pick card engine — direct backtest (development)

**DISCOVERY** — slates 1200: TWO-PICK CARD 0.0%, ONE QUALIFYING PICK 0.0%, NO BET 100.0%; two-pick cards: 0

**VALIDATION** — slates 809: TWO-PICK CARD 0.0%, ONE QUALIFYING PICK 0.0%, NO BET 100.0%; two-pick cards: 0

Closest pair, conservative joint probability: median 23.8%, max 25.9% (target 60%).

### Single-pick standard (separately defined: conservative P ≥ 52.38% break-even)

* No single pick met the standard in development.

## 7. Diagnostics (NOT the engine): what if cards were forced?

Each slate, the two highest-probability Overs among games with calibrated P ≥ threshold. This measures the ceiling of 2/2 rates available from this model.

| min_p | period | cards | rate_2of2 | ci95 | avg_joint_cal | roi_double |
|---|---|---|---|---|---|---|
| 0.000 | discovery | 1008 | 0.238 | 0.213–0.265 | 0.249 | -0.098 |
| 0.000 | validation | 675 | 0.237 | 0.206–0.271 | 0.258 | -0.119 |
| 0.500 | discovery | 356 | 0.256 | 0.213–0.303 | 0.262 | -0.052 |
| 0.500 | validation | 440 | 0.241 | 0.203–0.283 | 0.266 | -0.113 |
| 0.520 | discovery | 22 | 0.318 | 0.164–0.527 | 0.283 | 0.160 |
| 0.520 | validation | 67 | 0.269 | 0.177–0.385 | 0.285 | 0.008 |
| 0.540 | discovery | 4 | 0.250 | 0.046–0.699 | 0.300 | -0.089 |
| 0.540 | validation | 11 | 0.273 | 0.097–0.566 | 0.310 | -0.006 |
| 0.560 | discovery | 0 | — | —–— | — | — |
| 0.560 | validation | 2 | 0.500 | 0.095–0.905 | 0.327 | 0.822 |
| 0.580 | discovery | 0 | — | —–— | — | — |
| 0.580 | validation | 0 | — | —–— | — | — |
| 0.600 | discovery | 0 | — | —–— | — | — |
| 0.600 | validation | 0 | — | —–— | — | — |

Monte Carlo of the forced nightly double (6 months): expected ROI -10.7% (5–95%: -16.8%..-4.6%), P(losing month) 87.8%, median max drawdown 201.4u.

Monte Carlo of 200 single Overs with P ≥ 55%: expected ROI 5.4% (5–95% -5.5%..16.4%), P(10-loss streak) 3.5%.

## 8. Lessons from the old manual system (Section 45), tested

* Recent raw scoring (naive PPG, F1) vs market only: +3.3×10⁻⁴ log-loss gain.
* Adding team Over/Under trends (F8 vs F7): +0.3×10⁻⁴.
* Opponent-adjusted ratings over naive PPG (F2 vs F1): +4.7×10⁻⁴.
* 'A 3–4 point projection edge is enough': 97 such Overs won 55.2% (CI 45.3%–64.8%), ROI 5.3%.
* Blowout risk — |spread| < 10: Over win 50.0% over 9903 games.
* Blowout risk — |spread| ≥ 10: Over win 49.5% over 1864 games.
* H2H: no reliable head-to-head feature was built separately; team O/U trend is the closest proxy and is tested above.

## 9. Red-team

| test | logloss | delta_x1e4 |
|---|---|---|
| remove x_naive | 0.6925 | 0.3410 |
| remove x_rating | 0.6930 | 5.0863 |
| remove rest_sum | 0.6927 | 1.8754 |
| remove b2b_any | 0.6925 | -0.2754 |
| remove abs_spread | 0.6925 | -0.2115 |
| remove line_tend_sum | 0.6926 | 1.5131 |
| remove lg_total_minus_line | 0.6924 | -0.5985 |
| remove line_rel | 0.6926 | 0.6810 |
| remove early_season | 0.6925 | -0.2474 |
| remove postseason | 0.6926 | 0.5510 |
| remove log_games | 0.6925 | -0.1589 |
| remove ou_trend_sum | 0.6927 | 1.9155 |
| permute x_rating within season | 0.6930 | 5.2652 |
| min games 3 | 0.6922 | — |
| min games 10 | 0.6924 | — |
| min games 20 | 0.6927 | — |

Positive delta = worse without the feature.

## 10. Failure analysis (losing Overs with calibrated P ≥ 55%)

| category | count |
|---|---|
| C_variance | 11 |
| F_game_state_blowout | 1 |
| A_model_error | 1 |

Mean total error -14.2 pts; mean pace error +0.7 poss; mean efficiency error -15.7 pts/100 (box seasons only).

