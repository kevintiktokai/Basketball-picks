# Loss autopsy and creative-edge screen (NCAAB straight bets, 2011-21; 2021-26 not read)

## 1. Why the bets lost

After each game, its total is split into what pushed it away from the line. Positive numbers helped the bet, negative hurt it (points; shooting is measured against that season's league averages, pace against the engine's own possession forecast). Games with a box score only.

| era | bets | n | points beaten by (+) / missed by (-) | 3-point shooting vs league rate | 2-point shooting vs league rate | free-throw shooting vs league rate | pace vs the engine's forecast | overtime points |
|---|---|---|---|---|---|---|---|---|
| discovery 2011-18 | won | 2104 | 15.16 | 3.36 | 1.39 | 0.40 | 1.48 | 1.80 |
| discovery 2011-18 | lost | 1588 | -12.33 | -5.14 | -5.38 | -0.88 | -6.43 | -0.36 |
| validation 2018-21 | won | 1062 | 15.71 | 3.88 | 1.53 | 0.13 | 2.34 | 2.33 |
| validation 2018-21 | lost | 809 | -12.10 | -5.18 | -5.15 | -0.67 | -5.46 | -0.02 |

Lost bets by side (average points each factor cost):

| side | 3-point shooting vs league rate | 2-point shooting vs league rate | free-throw shooting vs league rate | pace vs the engine's forecast | overtime points | missed by |
|---|---|---|---|---|---|---|
| Over | -5.01 | -5.21 | -0.70 | -5.81 | 0.27 | -12.11 |
| Under | -5.86 | -5.78 | -1.37 | -7.53 | -2.78 | -12.92 |

Which factor hurt most in each lost bet:

| factor | share of losses where it hurt most (%) |
|---|---|
| pace vs the engine's forecast | 35.7 |
| 3-point shooting vs league rate | 30.9 |
| 2-point shooting vs league rate | 30.3 |
| free-throw shooting vs league rate | 2.0 |
| overtime points | 1.1 |

Overtime happened in 2.8% of all lost bets and 9.1% of lost Unders.

## 2. Pre-game ideas

t = how strongly the idea predicts the miss against the engine's forecast (all games) and the bets' own margin (our bets). A lead needs |t| >= 2 in discovery and the same sign with |t| >= 1.5 in validation (rule fixed before running).

| idea | t all games (disc) | t our bets (disc) | n games (disc) | t all games (val) | t our bets (val) | n games (val) | lead? |
|---|---|---|---|---|---|---|---|
| rematch (2nd+ meeting this season) | -2.76 | -1.58 | 17060 | -1.35 | -0.83 | 12855 | False |
| 3rd+ meeting (conference tournament rematches) | -3.88 | -0.37 | 17060 | -1.44 | 0.19 | 12855 | False |
| last meeting beat its closing total by more | 1.05 | 2.21 | 5385 | 0.16 | -0.07 | 4428 | False |
| both teams' last game beat its closing total by more | 1.78 | 0.43 | 15546 | 2.28 | 0.72 | 12124 | False |
| early tip on the away team's body clock (< 1 pm) | -0.84 | -0.70 | 14448 | 1.03 | -0.84 | 10860 | False |
| late tip on the away team's body clock (9 pm+) | -0.29 | -1.23 | 14448 | -2.00 | -1.72 | 10860 | False |
| time zones crossed by the away team | 1.38 | 0.26 | 17060 | 1.77 | 0.52 | 12855 | False |
| high-altitude venue | 3.48 | -0.86 | 14448 | 2.82 | 0.71 | 10860 | True |
| close game expected (spread 3 or less) | -0.36 | 0.28 | 17060 | -2.33 | 1.02 | 12855 | False |
| blowout expected (spread 18+) | 0.85 | -0.37 | 17060 | 0.48 | 0.98 | 12855 | False |
| 3-point-heavy matchup (style) | -0.75 | 0.60 | 17027 | -2.13 | -1.94 | 12854 | False |
| opening total (level) | 0.68 | 0.71 | 17060 | -2.54 | -2.31 | 12855 | False |

Close-game and blowout checks, by side:

| era | side | game type | check | bets | won | ROI @-110 |
|---|---|---|---|---|---|---|
| discovery 2011-18 | Over | close game expected | close game expected | 973 | 0.569 | 0.087 |
| discovery 2011-18 | Over | other games | close game expected | 2445 | 0.574 | 0.095 |
| discovery 2011-18 | Over | blowout expected | blowout expected | 104 | 0.587 | 0.120 |
| discovery 2011-18 | Over | other games | blowout expected | 3314 | 0.572 | 0.092 |
| discovery 2011-18 | Under | close game expected | close game expected | 205 | 0.620 | 0.183 |
| discovery 2011-18 | Under | other games | close game expected | 730 | 0.592 | 0.130 |
| discovery 2011-18 | Under | blowout expected | blowout expected | 94 | 0.543 | 0.036 |
| discovery 2011-18 | Under | other games | blowout expected | 841 | 0.604 | 0.153 |
| validation 2018-21 | Over | close game expected | close game expected | 594 | 0.552 | 0.054 |
| validation 2018-21 | Over | other games | close game expected | 1422 | 0.562 | 0.073 |
| validation 2018-21 | Over | blowout expected | blowout expected | 114 | 0.614 | 0.172 |
| validation 2018-21 | Over | other games | blowout expected | 1902 | 0.556 | 0.061 |
| validation 2018-21 | Under | close game expected | close game expected | 53 | 0.679 | 0.297 |
| validation 2018-21 | Under | other games | close game expected | 161 | 0.634 | 0.209 |
| validation 2018-21 | Under | blowout expected | blowout expected | 12 | 0.750 | 0.432 |
| validation 2018-21 | Under | other games | blowout expected | 202 | 0.639 | 0.219 |

