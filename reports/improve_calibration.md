# Improvement study 1 — side-aware calibration (NCAAB, locked v3 engine)

_Pre-registered in `config/improvements.yaml` before any candidate was fitted. Every season 2011-26 was used before, so this is a re-analysis; the 2026-27 forward ledger is the real test._

Only the calibrator changes (walk-forward, same history and season weights as the locked one; the refitted C0 reproduces the locked calibrators exactly, max |Δβ| = 0.0e+00).

## Primary: log loss of P(over) at the opener, every calibrated game

| calibrator | dev | holdout | reanalysis | pooled | mean P(over) | over rate |
|---|---|---|---|---|---|---|
| C0_locked | 0.68811 | 0.68954 | 0.69104 | 0.68979 | 0.51931 | 0.50608 |
| C1_side | 0.68810 | 0.68884 | 0.69083 | 0.68953 | 0.50717 | 0.50608 |
| C2_side_buffer | 0.68809 | 0.68888 | 0.69086 | 0.68955 | 0.50417 | 0.50608 |

Improvement over C0 (×10⁻⁴; positive = better):

| calibrator | dev | holdout | reanalysis | pooled |
|---|---|---|---|---|
| C0_locked | 0.000 | 0.000 | 0.000 | 0.000 |
| C1_side | 0.100 | 7.000 | 2.100 | 2.600 |
| C2_side_buffer | 0.200 | 6.500 | 1.800 | 2.400 |

## Alternate-line pricing: log loss over all pseudo-bets (both sides, buffers -6..+18)

| calibrator | dev | holdout | reanalysis |
|---|---|---|---|
| C0_locked | 0.59525 | 0.59541 | 0.59278 |
| C1_side | 0.59523 | 0.59488 | 0.59277 |
| C2_side_buffer | 0.59523 | 0.59483 | 0.59275 |

## Singles at the opener, calibrated P >= 55%

| calibrator | era | bets | win | ci95 | predicted | ROI @-110 | ROI real price | Over bets | Over win - predicted | Under bets | Under win - predicted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C0_locked | dev | 4353 | 0.578 | 0.563–0.593 | 0.575 | 0.103 | — | 3418 | -0.003 | 935 | 0.023 |
| C0_locked | holdout | 2230 | 0.567 | 0.547–0.588 | 0.572 | 0.083 | — | 2016 | -0.013 | 214 | 0.078 |
| C0_locked | reanalysis | 3491 | 0.568 | 0.551–0.584 | 0.570 | 0.084 | 0.099 | 3181 | -0.010 | 310 | 0.074 |
| C0_locked | POOLED | 10074 | 0.572 | 0.562–0.582 | 0.573 | 0.092 | 0.099 | 8615 | -0.008 | 1459 | 0.042 |
| C1_side | dev | 4463 | 0.579 | 0.564–0.593 | 0.577 | 0.105 | — | 2931 | 0.003 | 1532 | -0.001 |
| C1_side | holdout | 2993 | 0.568 | 0.550–0.585 | 0.575 | 0.084 | — | 1645 | -0.016 | 1348 | 0.005 |
| C1_side | reanalysis | 3830 | 0.560 | 0.544–0.575 | 0.571 | 0.069 | 0.085 | 2553 | -0.012 | 1277 | -0.009 |
| C1_side | POOLED | 11286 | 0.569 | 0.560–0.578 | 0.574 | 0.087 | 0.085 | 7129 | -0.007 | 4157 | -0.001 |
| C2_side_buffer | dev | 4414 | 0.580 | 0.565–0.594 | 0.577 | 0.107 | — | 2739 | 0.006 | 1675 | -0.002 |
| C2_side_buffer | holdout | 3210 | 0.566 | 0.549–0.583 | 0.576 | 0.081 | — | 1565 | -0.018 | 1645 | -0.003 |
| C2_side_buffer | reanalysis | 4004 | 0.565 | 0.549–0.580 | 0.571 | 0.078 | 0.094 | 2396 | -0.011 | 1608 | 0.000 |
| C2_side_buffer | POOLED | 11628 | 0.571 | 0.562–0.580 | 0.575 | 0.090 | 0.094 | 6700 | -0.006 | 4928 | -0.002 |

Share of these bets that are Unders:

| calibrator | dev Under share | holdout Under share | reanalysis Under share |
|---|---|---|---|
| C0_locked | 0.215 | 0.096 | 0.089 |
| C1_side | 0.343 | 0.450 | 0.333 |
| C2_side_buffer | 0.379 | 0.512 | 0.402 |

## 2.5+ target cards and main-line doubles, 2021-26 at real prices (locked products; re-analysis)

| calibrator | product | cards | hit | model_hit | leg_win | leg_p | roi | roi_ci95 |
|---|---|---|---|---|---|---|---|---|
| C0_locked | TARGET CARD | 664 | 0.468 | 0.447 | 0.676 | 0.669 | 0.199 | 0.104–0.295 |
| C0_locked | MAIN-LINE DOUBLE | 652 | 0.356 | 0.348 | 0.590 | 0.589 | 0.290 | 0.163–0.426 |
| C1_side | TARGET CARD | 664 | 0.464 | 0.459 | 0.670 | 0.678 | 0.179 | 0.081–0.275 |
| C1_side | MAIN-LINE DOUBLE | 653 | 0.355 | 0.355 | 0.587 | 0.595 | 0.287 | 0.161–0.424 |
| C2_side_buffer | TARGET CARD | 664 | 0.470 | 0.460 | 0.674 | 0.679 | 0.194 | 0.093–0.289 |
| C2_side_buffer | MAIN-LINE DOUBLE | 654 | 0.362 | 0.357 | 0.595 | 0.597 | 0.313 | 0.180–0.455 |

## Decision (pre-registered rule)

* C1_side qualifies: **False**; C2_side_buffer qualifies: **False** (log loss lower than C0 in each era and pooled ROI @-110 not lower).
* Adopted for the 2026-27 forward ledger next to C0: **none**.

Calibrator coefficients (b0, b_model, b_buf, b_buf², b_model×buf, side terms…) for three seasons:

```
C0_locked:
  2011-12: [-0.0035, 1.1553, 1.6772, 0.0021, 0.2659]
  2018-19: [-0.0027, 1.1977, 1.6844, 0.0369, 0.2759]
  2025-26: [-0.0074, 0.9242, 1.7124, 0.093, 0.2156]
C1_side:
  2011-12: [-0.0006, 1.2124, 1.6726, 0.0012, 0.2533, -0.0623]
  2018-19: [-0.0004, 1.3565, 1.6811, 0.0357, 0.2758, -0.0604]
  2025-26: [-0.0068, 1.0777, 1.7115, 0.0926, 0.2164, -0.0371]
C2_side_buffer:
  2011-12: [-0.0007, 1.2195, 1.6718, 0.0039, 0.2394, -0.0718, -0.0129, 0.0531]
  2018-19: [-0.0009, 1.3994, 1.679, 0.0423, 0.1549, -0.0773, -0.0061, 0.074]
  2025-26: [-0.007, 1.1174, 1.711, 0.0946, 0.1026, -0.0471, -0.0034, 0.0441]
```
