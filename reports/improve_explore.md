# Exploratory follow-up to improvement study 1 (does not change the engine)

_Run after the pre-registered decision in `reports/improve_calibration.md` (none adopted). Anything here is a lead for a new pre-registered study, not evidence for adoption._

## 1. Better probabilities, not better bets: what the side term changes

Bets at calibrated P >= 55%, locked calibrator (C0) vs side-aware (C1):

| era | group | bets | win | predicted | ROI @-110 | Under share |
|---|---|---|---|---|---|---|
| dev | kept by both | 3800 | 0.584 | 0.578 | 0.116 | 0.243 |
| dev | dropped by C1 (C0 only) | 553 | 0.533 | 0.554 | 0.018 | 0.022 |
| dev | added by C1 (C1 only) | 663 | 0.546 | 0.558 | 0.042 | 0.919 |
| holdout | kept by both | 1858 | 0.568 | 0.575 | 0.084 | 0.115 |
| holdout | dropped by C1 (C0 only) | 372 | 0.565 | 0.553 | 0.078 | 0.000 |
| holdout | added by C1 (C1 only) | 1135 | 0.567 | 0.568 | 0.083 | 0.999 |
| reanalysis | kept by both | 2863 | 0.568 | 0.574 | 0.085 | 0.108 |
| reanalysis | dropped by C1 (C0 only) | 628 | 0.565 | 0.553 | 0.079 | 0.000 |
| reanalysis | added by C1 (C1 only) | 967 | 0.535 | 0.561 | 0.021 | 1.000 |
| POOLED | kept by both | 8521 | 0.575 | 0.576 | 0.098 | 0.170 |
| POOLED | dropped by C1 (C0 only) | 1553 | 0.554 | 0.553 | 0.057 | 0.008 |
| POOLED | added by C1 (C1 only) | 2765 | 0.551 | 0.563 | 0.052 | 0.980 |

Same number of bets per season as the locked engine (each calibrator's most confident games), ROI at -110:

| calibrator | dev | holdout | reanalysis | POOLED |
|---|---|---|---|---|
| C0_locked | 0.1034 | 0.0830 | 0.0839 | 0.0921 |
| C1_side | 0.1012 | 0.0667 | 0.0708 | 0.0830 |
| C2_side_buffer | 0.1083 | 0.0684 | 0.0790 | 0.0893 |

Total units at -110 over 2011-26 at the 55% threshold: C0_locked +928, C1_side +982, C2_side_buffer +1045.

Reading: the side term moves about 1,550 marginal Overs out and about 2,750 marginal Unders in. Both groups are only slightly profitable (about +5% at -110), so the average ROI falls while the total rises with volume. At equal volume the locked ranking does better pooled (and in every era except C2 in 2011-18), so the Over tilt from overtime skew distorts probability levels without hurting the choice of games. Re-testing this on total units would be a new hypothesis, and the forward season would have to confirm it.

## 2. Residual scan of the mean model (out of sample, per era)

t-statistic of the slope of (total - opener - mu) on each signal; abs(t) > 2 is conventional significance for one test, but about 22 signals were scanned, so expect about one false hit per era.

| signal | t dev | t holdout | t reanalysis | same sign in all eras | weakest abs(t) |
|---|---|---|---|---|---|
| mu (model's own edge) | -4.30 | -2.02 | -5.53 | True | 2.02 |
| tempo gap (fast vs slow team) | -1.33 | -2.03 | -2.94 | True | 1.33 |
| efficiency mismatch | -2.31 | -1.19 | -1.35 | True | 1.19 |
| December | 0.88 | 0.31 | 0.54 | True | 0.31 |
| away team-total gap vs spread | -0.76 | -0.15 | -0.43 | True | 0.15 |
| games-played gap | 2.17 | 1.74 | -3.06 | False | 1.74 |
| home team-total gap vs spread | -2.03 | 1.64 | -1.28 | False | 1.28 |
| neutral site | -0.91 | 1.63 | 0.87 | False | 0.87 |
| Monday | -0.78 | -2.78 | 1.34 | False | 0.78 |
| model SD | 1.13 | -2.62 | -0.74 | False | 0.74 |
| March | -1.02 | -0.70 | 0.94 | False | 0.70 |
| opening total (level) | 0.68 | -2.54 | 1.11 | False | 0.68 |
| late season (both 25+ games) | -0.63 | -0.82 | 1.91 | False | 0.63 |
| February | 0.65 | -0.81 | 0.57 | False | 0.57 |
| January | -0.53 | 0.38 | -1.53 | False | 0.38 |
| Friday | 0.15 | 0.64 | -2.23 | False | 0.15 |
| Sunday | -0.23 | 1.54 | -0.13 | False | 0.13 |
| November | -0.10 | 1.17 | -0.36 | False | 0.10 |
| rest difference (home - away) | -0.80 | 1.07 | 0.05 | False | 0.05 |
| longest rest | 1.65 | -0.05 | 0.15 | False | 0.05 |
| slate size | 0.75 | -0.04 | -0.47 | False | 0.04 |
| spread size | -0.04 | 1.31 | 0.99 | False | 0.04 |

Realised slope of (total - opener) on the model's mu (1.0 = perfectly scaled): dev 0.79, holdout 0.88, reanalysis 0.70.

## 3. Leads for the next pre-registered study

* **The model's edge is about 20-30% too large in points** (realised slope 0.70-0.88 in every era). The calibrator already shrinks it in probability space, so the ranking of games is unaffected; it matters mainly for the projected totals shown on the card. Low expected profit.
* **Tempo mismatch goes under** (same sign in all eras, t -1.3 to -2.9): when a fast team meets a slow one, totals come in below the additive tempo forecast, consistent with the slower team controlling pace. A candidate feature for the possessions forecast, to be pre-registered with its own adoption rule (ROI at matched volume in every era).
* **Efficiency mismatches go under** (same sign, weaker): blowouts with bench minutes. Overlaps with the spread size, which is already in the model.
* Nothing else (rest, day of week, month, neutral site, slate size, total level) is consistent across eras: the engine already uses what these data contain.
* The larger untapped sources are outside these data: injuries and lineups (decisive in the NBA/WNBA), and the time the bet is placed (lines moved toward the engine's side in 67-80% of bets; the edge decays after the opener, so speed of execution is worth more than any of the leads above).
