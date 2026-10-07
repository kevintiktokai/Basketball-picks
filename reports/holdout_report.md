# OVER ENGINE — Final holdout and live-simulated report

Locked model: `{'feature_set': 'S_scores_full', 'learner': 'ridge', 'dist': 'normal', 'calib': 'platt'}` (locked at revision `43e1e7e`). Selection: `{'joint_target': 0.6, 'individual_floor': 0.6, 'single_cons_min': 0.5238, 'min_edge_points': 0.0, 'conservative_quantile': 0.05}`. Holdout ['2021-22', '2022-23', '2023-24']; live-sim ['2024-25', '2025-26']. Run once.

## 1. Card engine — slate outcomes by stage

| stage | slates | two_pick_cards | pct_card | pct_one_pick | pct_no_bet | rate_2of2 | ci95 |
|---|---|---|---|---|---|---|---|
| DISCOVERY | 1200 | 0 | 0.000 | 0.000 | 1.000 | — | —–— |
| VALIDATION | 809 | 0 | 0.000 | 0.000 | 1.000 | — | —–— |
| FINAL HOLDOUT | 596 | 0 | 0.000 | 0.000 | 1.000 | — | —–— |
| LIVE-SIMULATED | 291 | 0 | 0.000 | 0.000 | 1.000 | — | —–— |

Holdout closest pair, conservative joint probability: median 24.9%, max 26.9% (target 60%).

## 2. Single-pick standard (reported separately, never mixed with cards)

* No single pick met the standard in any stage.

## 3. Individual-probability calibration, holdout

**FINAL HOLDOUT** n=3622: Brier 0.2496, log loss 0.6923 (coin flip 0.6931), ECE 0.0159, max P 60.1%

| bucket | n | pred | actual | ci_lo | ci_hi | cal_err |
|---|---|---|---|---|---|---|
| 0%-50% | 1784 | 0.482 | 0.494 | 0.471 | 0.518 | 0.012 |
| 50%-55% | 1757 | 0.518 | 0.505 | 0.481 | 0.528 | -0.013 |
| 55%-60% | 80 | 0.561 | 0.613 | 0.503 | 0.712 | 0.052 |
| 60%-65% | 1 | 0.601 | 1.000 | 0.207 | 1.000 | 0.399 |
| 65%-70% | 0 | — | — | — | — | — |
| 70%-75% | 0 | — | — | — | — | — |
| 75%-100% | 0 | — | — | — | — | — |

**LIVE-SIMULATED** n=1704: Brier 0.2503, log loss 0.6938 (coin flip 0.6931), ECE 0.0471, max P 56.5%

| bucket | n | pred | actual | ci_lo | ci_hi | cal_err |
|---|---|---|---|---|---|---|
| 0%-50% | 948 | 0.485 | 0.504 | 0.472 | 0.536 | 0.019 |
| 50%-55% | 754 | 0.512 | 0.512 | 0.476 | 0.547 | -0.000 |
| 55%-60% | 2 | 0.564 | 0.500 | 0.095 | 0.905 | -0.064 |
| 60%-65% | 0 | — | — | — | — | — |
| 65%-70% | 0 | — | — | — | — | — |
| 70%-75% | 0 | — | — | — | — | — |
| 75%-100% | 0 | — | — | — | — | — |

## 4. Holdout bet buckets (each calibrated game as a 1u Over at 1.909)

| bucket | n | pred | win | ci | roi | cal_err |
|---|---|---|---|---|---|---|
| <50% | 1800 | 0.482 | 0.494 | 0.471–0.518 | -0.056 | 0.012 |
| 50–54 | 1770 | 0.518 | 0.505 | 0.481–0.528 | -0.036 | -0.013 |
| 55–59 | 80 | 0.561 | 0.613 | 0.503–0.712 | 0.169 | 0.052 |
| 60–64 | 1 | 0.601 | 1.000 | 0.207–1.000 | 0.909 | 0.399 |
| 65–69 | 0 | — | — | None | — | — |
| 70–74 | 0 | — | — | None | — | — |
| 75%+ | 0 | — | — | None | — | — |

| bucket | n | pred | win | ci | roi | cal_err |
|---|---|---|---|---|---|---|
| <0 | 1367 | 0.478 | 0.490 | 0.463–0.517 | -0.064 | 0.012 |
| 0–1 | 985 | 0.501 | 0.488 | 0.457–0.519 | -0.069 | -0.013 |
| 1–2 | 735 | 0.517 | 0.508 | 0.471–0.544 | -0.031 | -0.009 |
| 2–3 | 375 | 0.532 | 0.524 | 0.473–0.575 | 0.001 | -0.008 |
| 3–4 | 148 | 0.548 | 0.565 | 0.484–0.642 | 0.077 | 0.017 |
| 4–5 | 31 | 0.564 | 0.710 | 0.534–0.839 | 0.355 | 0.146 |
| 5+ | 10 | 0.584 | 0.800 | 0.490–0.943 | 0.527 | 0.216 |

Holdout Overs with calibrated P ≥ 55% (pre-declared diagnostic threshold): {'bets': 81, 'wins': 50, 'losses': 31, 'pushes': 0, 'win_rate': 0.6172839506172839, 'win_ci95': (np.float64(0.508410467539316), np.float64(0.7155362755678389)), 'avg_pred': 0.5614125736287048, 'cal_err': 0.055871376988579136, 'avg_edge_pts': 4.222626647398802, 'roi': 0.17839506172839506, 'profit_units': 14.45, 'max_drawdown': 5.546000000000001, 'longest_losing_streak': 3, 'brier': 0.23788387287612747, 'log_loss': 0.6687473087081057}

Monte Carlo (200 such bets): {'horizon_bets': 200, 'expected_roi': 0.178238618, 'roi_p5_p95': (np.float64(0.06903999999999998), np.float64(0.28857499999999997)), 'p_10_loss_streak': 0.0086, 'median_max_drawdown': 7.092000000000002}

## 5. Dependence in the holdout

Same-day pairs 13119: Over-outcome corr 0.0071 (CI -0.0107..0.0291); error corr 0.0022 (CI -0.0142..0.0185); joint−product +0.0018.

Required individual P for 60% joint at holdout rho: 77.4%.

## 6. Diagnostics (NOT the engine): forced nightly top-2 Overs

| min_p | stage | cards | rate_2of2 | ci95 | avg_joint_cal | roi_double |
|---|---|---|---|---|---|---|
| 0.000 | FINAL HOLDOUT | 524 | 0.277 | 0.240–0.317 | 0.267 | 0.027 |
| 0.000 | LIVE-SIMULATED | 240 | 0.208 | 0.162–0.264 | 0.261 | -0.209 |
| 0.500 | FINAL HOLDOUT | 379 | 0.280 | 0.237–0.327 | 0.276 | 0.039 |
| 0.500 | LIVE-SIMULATED | 165 | 0.194 | 0.141–0.261 | 0.267 | -0.259 |
| 0.520 | FINAL HOLDOUT | 155 | 0.303 | 0.236–0.380 | 0.292 | 0.142 |
| 0.520 | LIVE-SIMULATED | 36 | 0.111 | 0.044–0.253 | 0.280 | -0.489 |
| 0.540 | FINAL HOLDOUT | 46 | 0.370 | 0.245–0.514 | 0.309 | 0.347 |
| 0.540 | LIVE-SIMULATED | 2 | 0.000 | 0.000–0.658 | 0.306 | -1.000 |
| 0.560 | FINAL HOLDOUT | 8 | 0.625 | 0.306–0.863 | 0.328 | 1.278 |
| 0.560 | LIVE-SIMULATED | 0 | — | —–— | — | — |

## 7. Failure analysis — holdout losing Overs with P ≥ 55%

| category | count |
|---|---|
| C_variance | 22 |
| F_game_state_blowout | 7 |
| A_model_error | 2 |

