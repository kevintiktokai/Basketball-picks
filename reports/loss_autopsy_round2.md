# Loss autopsy, round 2 (NCAAB straight bets, 2011-21; 2021-26 not read)

Ideas and their expected direction were written down in the script before it was first run. Same rule as round 1: |t| >= 2 in discovery and the same sign with |t| >= 1.5 in validation. t all games = predicts the miss against the engine's forecast; t our bets = predicts the bets' own margin.

## Ideas

| idea | expected | t all games (disc) | t our bets (disc) | games with a value (disc) | t all games (val) | t our bets (val) | games with a value (val) | lead? | direction as expected? | flagged games (disc) | miss when flagged (disc) | flagged games (val) | miss when flagged (val) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| venue factor (home floor ran over its closes) | + | 5.50 | 3.40 | 14835 | 4.95 | 2.23 | 11662 | True | True | — | — | — | — |
| venue split (home floor minus the team's road games) | + | 4.78 | 2.66 | 14835 | 4.23 | 1.49 | 11662 | True | True | — | — | — | — |
| key player out (25+ min, either team) | - | -1.91 | -0.34 | 14436 | -2.08 | -0.05 | 10849 | False | None | 1285.00 | -1.06 | 1371.00 | -1.45 |
| key minutes out (share of 200) | - | -1.94 | -0.25 | 14436 | -2.21 | -0.36 | 10849 | False | None | — | — | — | — |
| key player back after missing the last game | + | -0.83 | 0.82 | 14440 | -1.43 | -0.97 | 10850 | False | None | 561.00 | -0.77 | 536.00 | -1.58 |
| long layoff (both teams 7+ days off) | - | 0.90 | 0.95 | 17006 | -0.10 | 0.62 | 12845 | False | None | 700.00 | 0.38 | 761.00 | -0.68 |
| played yesterday (either team) | - | -0.77 | -0.90 | 17006 | 0.39 | 0.45 | 12845 | False | None | 1244.00 | -0.53 | 1179.00 | -0.44 |
| football-stadium venue (30,000+ seats) | - | -2.25 | -1.10 | 13496 | -0.70 | -0.33 | 10459 | False | None | 78.00 | -4.57 | 36.00 | -2.59 |
| senior night (home team's last home game) | none | -0.03 | -1.48 | 14448 | 1.39 | -0.57 | 10860 | False | None | 1034.00 | -0.20 | 853.00 | 0.24 |

Bets with and without each flag (win rate, ROI at -110):

| idea | era | side | flagged | bets | won | ROI @-110 |
|---|---|---|---|---|---|---|
| key player out (25+ min, either team) | discovery 2011-18 | Over | True | 302 | 0.546 | 0.043 |
| key player out (25+ min, either team) | discovery 2011-18 | Over | False | 2566 | 0.566 | 0.081 |
| key player out (25+ min, either team) | discovery 2011-18 | Under | True | 42 | 0.667 | 0.273 |
| key player out (25+ min, either team) | discovery 2011-18 | Under | False | 776 | 0.585 | 0.117 |
| key player out (25+ min, either team) | validation 2018-21 | Over | True | 204 | 0.539 | 0.029 |
| key player out (25+ min, either team) | validation 2018-21 | Over | False | 1473 | 0.561 | 0.072 |
| key player out (25+ min, either team) | validation 2018-21 | Under | True | 27 | 0.815 | 0.556 |
| key player out (25+ min, either team) | validation 2018-21 | Under | False | 163 | 0.613 | 0.171 |
| key player back after missing the last game | discovery 2011-18 | Over | True | 134 | 0.590 | 0.126 |
| key player back after missing the last game | discovery 2011-18 | Over | False | 2734 | 0.563 | 0.075 |
| key player back after missing the last game | discovery 2011-18 | Under | True | 25 | 0.680 | 0.298 |
| key player back after missing the last game | discovery 2011-18 | Under | False | 795 | 0.586 | 0.119 |
| key player back after missing the last game | validation 2018-21 | Over | True | 85 | 0.518 | -0.012 |
| key player back after missing the last game | validation 2018-21 | Over | False | 1592 | 0.561 | 0.071 |
| key player back after missing the last game | validation 2018-21 | Under | True | 10 | 0.800 | 0.527 |
| key player back after missing the last game | validation 2018-21 | Under | False | 180 | 0.633 | 0.209 |
| long layoff (both teams 7+ days off) | discovery 2011-18 | Over | True | 203 | 0.557 | 0.063 |
| long layoff (both teams 7+ days off) | discovery 2011-18 | Over | False | 3202 | 0.573 | 0.095 |
| long layoff (both teams 7+ days off) | discovery 2011-18 | Under | True | 28 | 0.571 | 0.091 |
| long layoff (both teams 7+ days off) | discovery 2011-18 | Under | False | 903 | 0.597 | 0.140 |
| long layoff (both teams 7+ days off) | validation 2018-21 | Over | True | 164 | 0.573 | 0.094 |
| long layoff (both teams 7+ days off) | validation 2018-21 | Over | False | 1850 | 0.557 | 0.064 |
| long layoff (both teams 7+ days off) | validation 2018-21 | Under | True | 11 | 0.636 | 0.215 |
| long layoff (both teams 7+ days off) | validation 2018-21 | Under | False | 203 | 0.645 | 0.232 |
| played yesterday (either team) | discovery 2011-18 | Over | True | 122 | 0.598 | 0.142 |
| played yesterday (either team) | discovery 2011-18 | Over | False | 3283 | 0.571 | 0.091 |
| played yesterday (either team) | discovery 2011-18 | Under | True | 160 | 0.550 | 0.050 |
| played yesterday (either team) | discovery 2011-18 | Under | False | 771 | 0.606 | 0.156 |
| played yesterday (either team) | validation 2018-21 | Over | True | 77 | 0.571 | 0.091 |
| played yesterday (either team) | validation 2018-21 | Over | False | 1937 | 0.558 | 0.065 |
| played yesterday (either team) | validation 2018-21 | Under | True | 60 | 0.650 | 0.241 |
| played yesterday (either team) | validation 2018-21 | Under | False | 154 | 0.643 | 0.227 |
| football-stadium venue (30,000+ seats) | discovery 2011-18 | Over | True | 13 | 0.462 | -0.119 |
| football-stadium venue (30,000+ seats) | discovery 2011-18 | Over | False | 2772 | 0.563 | 0.076 |
| football-stadium venue (30,000+ seats) | discovery 2011-18 | Under | True | 3 | 1.000 | 0.909 |
| football-stadium venue (30,000+ seats) | discovery 2011-18 | Under | False | 706 | 0.589 | 0.125 |
| football-stadium venue (30,000+ seats) | validation 2018-21 | Over | True | 5 | 0.400 | -0.236 |
| football-stadium venue (30,000+ seats) | validation 2018-21 | Over | False | 1663 | 0.559 | 0.066 |
| football-stadium venue (30,000+ seats) | validation 2018-21 | Under | True | 1 | 1.000 | 0.909 |
| football-stadium venue (30,000+ seats) | validation 2018-21 | Under | False | 151 | 0.636 | 0.214 |
| senior night (home team's last home game) | discovery 2011-18 | Over | True | 313 | 0.530 | 0.012 |
| senior night (home team's last home game) | discovery 2011-18 | Over | False | 2558 | 0.568 | 0.085 |
| senior night (home team's last home game) | discovery 2011-18 | Under | True | 10 | 0.400 | -0.236 |
| senior night (home team's last home game) | discovery 2011-18 | Under | False | 811 | 0.592 | 0.130 |
| senior night (home team's last home game) | validation 2018-21 | Over | True | 192 | 0.536 | 0.024 |
| senior night (home team's last home game) | validation 2018-21 | Over | False | 1488 | 0.562 | 0.073 |
| senior night (home team's last home game) | validation 2018-21 | Under | True | 6 | 0.667 | 0.273 |
| senior night (home team's last home game) | validation 2018-21 | Under | False | 185 | 0.643 | 0.228 |

## Does the closing total overshoot after big moves? (for middling)

If it did, the total would land on the far side of the close after big moves (t slope = slope of (total - close) on (close - open); negative = overshoot).

| era | games | t slope | total - close: close fell 3+ | n: close fell 3+ | total - close: fell 1-3 | n: fell 1-3 | total - close: within 1 | n: within 1 | total - close: rose 1-3 | n: rose 1-3 | total - close: rose 3+ | n: rose 3+ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| discovery 2011-18 | 17058 | 1.14 | 0.25 | 1568 | 0.45 | 3944 | 0.78 | 4876 | 0.92 | 4542 | 0.30 | 2128 |
| validation 2018-21 | 12854 | 2.40 | -0.10 | 1253 | -0.28 | 2622 | 0.66 | 3964 | 0.70 | 3437 | 1.30 | 1578 |

Overshoot lead: **False**.

## High-altitude venues: does the round-1 lead look physical?

| era | games | n | miss vs forecast | standard error |
|---|---|---|---|---|
| discovery 2011-18 | all other games (low venue, no altitude team) | 11325 | -0.22 | 0.16 |
| discovery 2011-18 | at altitude, visitor from low altitude | 475 | 1.89 | 0.77 |
| discovery 2011-18 | at altitude, visitor also based at altitude | 217 | 1.55 | 1.27 |
| discovery 2011-18 | altitude-based team on the road at low altitude | 521 | -0.90 | 0.77 |
| validation 2018-21 | all other games (low venue, no altitude team) | 9079 | -0.72 | 0.18 |
| validation 2018-21 | at altitude, visitor from low altitude | 280 | 1.59 | 0.92 |
| validation 2018-21 | at altitude, visitor also based at altitude | 168 | 1.70 | 1.43 |
| validation 2018-21 | altitude-based team on the road at low altitude | 303 | -0.70 | 0.99 |

By half (first-half share of regulation points at low venues 0.471; miss vs the forecast split by that share):

| era | high_altitude | first half | second half (regulation) |
|---|---|---|---|
| discovery 2011-18 | low venue | -1.04 | -0.85 |
| discovery 2011-18 | high-altitude venue | 0.09 | 0.13 |
| validation 2018-21 | low venue | -0.80 | -1.31 |
| validation 2018-21 | high-altitude venue | 0.27 | 0.12 |

Venues: 13 of 17 high-altitude floors ran above the forecast (2011-21, non-neutral games).

| city | games | miss vs forecast |
|---|---|---|
| orem | 21 | 6.47 |
| bozeman | 50 | 4.79 |
| ogden | 68 | 3.53 |
| denver | 66 | 3.42 |
| fort collins | 82 | 3.40 |
| colorado springs | 63 | 3.24 |
| pocatello | 51 | 3.11 |
| greeley | 60 | 2.90 |
| laramie | 78 | 2.65 |
| logan | 76 | 2.22 |
| boulder | 97 | 1.69 |
| reno | 75 | 1.11 |
| provo | 81 | 0.82 |
| cedar city | 59 | -0.46 |
| salt lake city | 94 | -0.74 |
| albuquerque | 74 | -2.38 |
| flagstaff | 45 | -2.44 |

