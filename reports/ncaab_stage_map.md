# NCAAB stage map (2011-12 .. 2020-21; 2021-26 sealed for confirmation)

Every eligible game the locked v3 engine priced out of sample, split by stage of the season (ESPN schedule labels). *Market error* = average miss of the opening (closing) total in points; *line move* = average size of the open-to-close move; *model gain* = how much better the engine's probabilities are than the market-only model (log loss ×10⁻⁴, positive = better); bets = singles at calibrated P >= 55% on the opener, ROI at -110; CLV = points the line moved toward the bet.

## Pooled 2011-21

| stage | games | market error (open) | market error (close) | line move | total - opener | Over rate | OT rate | model gain x1e4 | bets | bet win | win 95% CI | predicted | ROI @-110 | CLV pts | Under share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| non-conference, campus site | 5316 | 13.360 | 13.203 | 1.759 | 0.598 | 0.506 | 0.049 | 34.380 | 1103 | 0.569 | 0.540–0.598 | 0.574 | 0.087 | 1.397 | 0.257 |
| non-conference, neutral site (events) | 1293 | 13.642 | 13.515 | 1.894 | -1.382 | 0.461 | 0.056 | 32.840 | 278 | 0.576 | 0.517–0.632 | 0.580 | 0.099 | 1.263 | 0.773 |
| conference regular season | 20294 | 13.355 | 13.199 | 1.743 | 1.024 | 0.510 | 0.068 | 51.099 | 4631 | 0.573 | 0.559–0.587 | 0.574 | 0.094 | 1.846 | 0.101 |
| conference tournaments | 1841 | 13.224 | 13.007 | 1.785 | -0.504 | 0.472 | 0.060 | 28.068 | 331 | 0.580 | 0.526–0.632 | 0.572 | 0.107 | 0.914 | 0.269 |
| NCAA tournament | 599 | 12.781 | 12.568 | 1.892 | -0.185 | 0.486 | 0.050 | 65.555 | 89 | 0.652 | 0.548–0.743 | 0.573 | 0.244 | 1.213 | 0.618 |
| NIT / CBI / CIT | 559 | 13.665 | 13.285 | 2.428 | 3.539 | 0.563 | 0.116 | 64.283 | 143 | 0.587 | 0.505–0.665 | 0.575 | 0.121 | 2.367 | 0.266 |

## By era (a stage pattern should hold in both)

| era | stage | games | market error (open) | market error (close) | line move | total - opener | Over rate | OT rate | model gain x1e4 | bets | bet win | win 95% CI | predicted | ROI @-110 | CLV pts | Under share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev 2011-18 | non-conference, campus site | 2818 | 13.391 | 13.235 | 1.840 | 0.639 | 0.515 | 0.053 | 54.212 | 700 | 0.594 | 0.557–0.630 | 0.576 | 0.135 | 1.309 | 0.357 |
| dev 2011-18 | non-conference, neutral site (events) | 720 | 13.908 | 13.723 | 1.990 | -2.283 | 0.452 | 0.054 | 42.314 | 209 | 0.574 | 0.506–0.639 | 0.583 | 0.096 | 1.239 | 0.770 |
| dev 2011-18 | conference regular season | 11199 | 13.386 | 13.261 | 1.712 | 1.130 | 0.512 | 0.072 | 56.253 | 2964 | 0.573 | 0.555–0.591 | 0.575 | 0.094 | 1.659 | 0.123 |
| dev 2011-18 | conference tournaments | 1381 | 13.522 | 13.288 | 1.756 | -0.225 | 0.478 | 0.069 | 21.786 | 268 | 0.578 | 0.519–0.636 | 0.572 | 0.104 | 0.817 | 0.295 |
| dev 2011-18 | NCAA tournament | 466 | 12.717 | 12.559 | 1.817 | -0.052 | 0.501 | 0.041 | 59.894 | 78 | 0.615 | 0.504–0.716 | 0.575 | 0.175 | 1.019 | 0.615 |
| dev 2011-18 | NIT / CBI / CIT | 463 | 13.457 | 13.064 | 2.488 | 3.824 | 0.573 | 0.119 | 83.581 | 126 | 0.579 | 0.492–0.662 | 0.576 | 0.106 | 2.187 | 0.262 |
| holdout 2018-21 | non-conference, campus site | 2498 | 13.325 | 13.168 | 1.668 | 0.553 | 0.495 | 0.046 | 12.112 | 403 | 0.526 | 0.477–0.574 | 0.570 | 0.004 | 1.550 | 0.084 |
| holdout 2018-21 | non-conference, neutral site (events) | 573 | 13.309 | 13.253 | 1.773 | -0.250 | 0.473 | 0.059 | 20.817 | 69 | 0.580 | 0.462–0.689 | 0.568 | 0.107 | 1.333 | 0.783 |
| holdout 2018-21 | conference regular season | 9095 | 13.318 | 13.123 | 1.781 | 0.894 | 0.507 | 0.063 | 44.757 | 1667 | 0.573 | 0.549–0.596 | 0.572 | 0.094 | 2.179 | 0.062 |
| holdout 2018-21 | conference tournaments | 460 | 12.327 | 12.162 | 1.871 | -1.342 | 0.453 | 0.035 | 46.820 | 63 | 0.587 | 0.464–0.700 | 0.570 | 0.121 | 1.325 | 0.159 |
| holdout 2018-21 | NCAA tournament | 133 | 13.008 | 12.602 | 2.158 | -0.654 | 0.432 | 0.083 | 85.242 | 11 | 0.909 | 0.623–0.984 | 0.558 | 0.736 | 2.591 | 0.636 |
| holdout 2018-21 | NIT / CBI / CIT | 96 | 14.667 | 14.354 | 2.135 | 2.167 | 0.516 | 0.104 | -28.958 | 17 | 0.647 | 0.413–0.827 | 0.567 | 0.235 | 3.706 | 0.294 |

## Early season vs established teams

| era | phase | games | market error (open) | market error (close) | line move | total - opener | Over rate | OT rate | model gain x1e4 | bets | bet win | win 95% CI | predicted | ROI @-110 | CLV pts | Under share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev 2011-18 | early (a team < 6 games) | 2236 | 13.305 | 13.183 | 1.914 | -0.337 | 0.491 | 0.050 | 31.926 | 635 | 0.583 | 0.544–0.620 | 0.579 | 0.112 | 1.099 | 0.532 |
| dev 2011-18 | established | 14824 | 13.417 | 13.264 | 1.753 | 1.019 | 0.511 | 0.071 | 56.582 | 3718 | 0.577 | 0.561–0.593 | 0.574 | 0.102 | 1.616 | 0.161 |
| holdout 2018-21 | early (a team < 6 games) | 1604 | 13.336 | 13.201 | 1.804 | 0.068 | 0.480 | 0.057 | 21.579 | 238 | 0.559 | 0.495–0.620 | 0.569 | 0.067 | 1.319 | 0.412 |
| holdout 2018-21 | established | 11251 | 13.284 | 13.093 | 1.763 | 0.779 | 0.503 | 0.060 | 39.516 | 1992 | 0.568 | 0.546–0.590 | 0.572 | 0.085 | 2.113 | 0.058 |
| 2011-21 | early (a team < 6 games) | 3840 | 13.318 | 13.190 | 1.868 | -0.168 | 0.487 | 0.053 | 27.601 | 873 | 0.576 | 0.543–0.609 | 0.576 | 0.100 | 1.159 | 0.499 |
| 2011-21 | established | 26075 | 13.359 | 13.190 | 1.757 | 0.915 | 0.508 | 0.066 | 49.214 | 5710 | 0.574 | 0.561–0.587 | 0.574 | 0.096 | 1.789 | 0.125 |

