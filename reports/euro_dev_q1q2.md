# Europe development study: soft books against Pinnacle (Q1, Q2)

Development games (2025-26, from 2026-01-20) with any pre-game totals: **144**; matched to official results: 144. Games per book: 1xbet 104, bet365 4, betsson 1, betway 85, bwin 1, pinnacle 110, unibet 36, williamhill 1. Pinnacle closing fair line available for 110 games.

EV = probability x price - 1, with the probability from Pinnacle's no-vig ladder; **CLV** values the same bet against Pinnacle's *closing* ladder (positive = the market moved your way). One bet per game (the best EV), ROI per 1-unit bet with a game-clustered bootstrap CI.

## Q1 — soft-book opening lines against Pinnacle

At the first moment both are posted, bet the soft book's main line toward Pinnacle's fair line (Under if the soft line is higher). Gap = soft line - Pinnacle's fair line.

| soft book | gap >= pts (abs) | games | mean abs gap | close stays on Pinnacle's side | mean CLV | won | ROI | ROI 95% CI |
|---|---|---|---|---|---|---|---|---|
| 1xbet | 0.000 | 96 | 1.166 | 0.688 | -0.015 | 0.542 | 0.031 | -0.166–0.228 |
| 1xbet | 1.000 | 50 | 1.854 | 0.760 | 0.012 | 0.580 | 0.109 | -0.157–0.375 |
| 1xbet | 2.000 | 20 | 2.561 | 0.750 | 0.020 | 0.500 | -0.040 | -0.428–0.350 |
| 1xbet | 3.000 | 5 | 3.134 | 0.800 | 0.033 | 0.400 | -0.228 | -1.000–0.544 |
| betway | 0.000 | 77 | 1.022 | 0.701 | -0.017 | 0.584 | 0.108 | -0.108–0.324 |
| betway | 1.000 | 37 | 1.722 | 0.703 | -0.001 | 0.622 | 0.180 | -0.120–0.484 |
| betway | 2.000 | 12 | 2.328 | 0.750 | 0.019 | 0.583 | 0.111 | -0.370–0.592 |
| betway | 3.000 | 2 | 3.011 | 0.500 | -0.024 | 0.500 | -0.045 | -1.000–0.909 |
| unibet | 0.000 | 9 | 1.263 | 0.667 | -0.016 | 0.556 | 0.054 | -0.578–0.687 |
| unibet | 1.000 | 4 | 2.373 | 0.750 | -0.019 | 0.500 | -0.055 | -1.000–0.890 |
| unibet | 2.000 | 2 | 3.716 | 1.000 | 0.020 | 0.500 | -0.060 | -1.000–0.880 |
| unibet | 3.000 | 1 | 4.978 | 1.000 | -0.043 | 0.000 | -1.000 | -1.000–-1.000 |
| bet365 | 0.000 | 4 | 1.105 | 0.500 | -0.086 | 0.500 | -0.070 | -1.000–0.860 |
| bet365 | 1.000 | 2 | 1.509 | 0.500 | -0.112 | 0.500 | -0.070 | -1.000–0.860 |
| bet365 | 2.000 | 0 | — | — | — | — | — | —–— |
| bet365 | 3.000 | 0 | — | — | — | — | — | —–— |

## Q2 — soft-book prices above Pinnacle's fair price

| decision time | EV now > | odds 1.40-1.90 only | legs available | games (1 bet each) | mean EV now | mean CLV | CLV > 0 | won | ROI | ROI 95% CI |
|---|---|---|---|---|---|---|---|---|---|---|
| when Pinnacle opens | 0.000 | False | 894 | 74 | 0.048 | 0.019 | 0.649 | 0.527 | -0.041 | -0.246–0.177 |
| when Pinnacle opens | 0.000 | True | 408 | 64 | 0.044 | 0.019 | 0.719 | 0.531 | -0.077 | -0.296–0.143 |
| when Pinnacle opens | 0.020 | False | 557 | 50 | 0.066 | 0.031 | 0.700 | 0.520 | -0.009 | -0.279–0.266 |
| when Pinnacle opens | 0.020 | True | 263 | 47 | 0.057 | 0.026 | 0.723 | 0.511 | -0.102 | -0.354–0.165 |
| when Pinnacle opens | 0.040 | False | 301 | 35 | 0.081 | 0.045 | 0.714 | 0.457 | -0.096 | -0.420–0.236 |
| when Pinnacle opens | 0.040 | True | 131 | 29 | 0.074 | 0.037 | 0.759 | 0.517 | -0.072 | -0.408–0.252 |
| 6 h before tip | 0.000 | False | 276 | 52 | 0.021 | 0.017 | 0.673 | 0.635 | 0.043 | -0.176–0.276 |
| 6 h before tip | 0.000 | True | 125 | 39 | 0.020 | 0.015 | 0.718 | 0.590 | 0.010 | -0.249–0.277 |
| 6 h before tip | 0.020 | False | 85 | 15 | 0.053 | 0.048 | 0.867 | 0.733 | 0.406 | -0.048–0.810 |
| 6 h before tip | 0.020 | True | 41 | 11 | 0.051 | 0.048 | 1.000 | 0.545 | -0.037 | -0.539–0.458 |
| 6 h before tip | 0.040 | False | 34 | 8 | 0.076 | 0.068 | 1.000 | 0.625 | 0.184 | -0.505–0.766 |
| 6 h before tip | 0.040 | True | 17 | 5 | 0.079 | 0.067 | 1.000 | 0.600 | 0.015 | -0.711–0.740 |
| 1 h before tip | 0.000 | False | 277 | 45 | 0.025 | 0.026 | 0.822 | 0.556 | -0.118 | -0.351–0.121 |
| 1 h before tip | 0.000 | True | 131 | 31 | 0.026 | 0.028 | 0.871 | 0.516 | -0.143 | -0.416–0.153 |
| 1 h before tip | 0.020 | False | 103 | 18 | 0.050 | 0.049 | 0.944 | 0.389 | -0.316 | -0.702–0.106 |
| 1 h before tip | 0.020 | True | 59 | 14 | 0.048 | 0.044 | 0.929 | 0.429 | -0.261 | -0.682–0.220 |
| 1 h before tip | 0.040 | False | 35 | 9 | 0.070 | 0.070 | 1.000 | 0.556 | 0.010 | -0.603–0.622 |
| 1 h before tip | 0.040 | True | 19 | 7 | 0.067 | 0.065 | 1.000 | 0.571 | -0.051 | -0.739–0.521 |

