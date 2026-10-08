# Europe development study: the model and the 2.5 cards (Q3, Q4)

Development games with Pinnacle's opening and closing ladders and a model total: **108** (2025-26, from 2026-01-20). Small sample: read for direction.

## Q3 — does the rating model add information to Pinnacle's opener?

Disagreement = model total - Pinnacle's no-vig opening line, centred on the average disagreement of earlier dates (no look-ahead).

| games | mean raw disagreement (pts) | SD of disagreement | corr with Pinnacle's open->close move |   95% CI | corr with result vs Pinnacle's open |   95% CI  | log-loss gain x1e4 (model alone) | log-loss gain x1e4 (half weight) |
|---|---|---|---|---|---|---|---|---|
| 108 | -0.217 | 3.387 | 0.177 | 0.019–0.324 | 0.017 | -0.159–0.211 | 9.018 | 35.493 |

Betting the model's side at Pinnacle's opening main line and price:

| model disagrees by >= pts | games | line moved toward model | mean CLV | won | ROI | ROI 95% CI |
|---|---|---|---|---|---|---|
| 0 | 108 | 0.528 | -0.036 | 0.537 | 0.027 | -0.150–0.204 |
| 3 | 34 | 0.529 | -0.036 | 0.559 | 0.067 | -0.270–0.402 |
| 5 | 14 | 0.571 | -0.029 | 0.571 | 0.093 | -0.452–0.514 |
| 8 | 4 | 0.500 | -0.019 | 0.750 | 0.431 | -0.523–0.913 |

## Q4 — two-leg cards at combined odds >= 2.5 from real soft-book prices

Legs 1.40-1.90 from 1xBet/Betway/Unibet/bet365 whose price beats Pinnacle's fair price at the decision time; per date, the pair of games with the highest joint EV (released only if > 0). Joint CLV values the card at Pinnacle's closing fair prices.

| decision time | leg EV > | cards | mean odds | break-even | mean joint EV | mean joint CLV | CLV > 0 | both won | ROI | ROI 95% CI |
|---|---|---|---|---|---|---|---|---|---|---|
| when Pinnacle opens | 0.000 | 17 | 3.116 | 0.322 | 0.120 | 0.073 | 0.882 | 0.294 | -0.058 | -0.681–0.684 |
| when Pinnacle opens | 0.020 | 14 | 3.094 | 0.325 | 0.130 | 0.078 | 0.929 | 0.286 | -0.100 | -0.778–0.646 |
| 6 h before tip | 0.000 | 11 | 3.043 | 0.331 | 0.043 | 0.045 | 0.909 | 0.273 | -0.192 | -1.000–0.617 |
| 6 h before tip | 0.020 | 1 | 3.291 | 0.304 | 0.112 | 0.074 | 1.000 | 1.000 | 2.291 | 2.291–2.291 |

