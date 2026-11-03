# NBA player points props at real prices

Data: OddsPapi pre-game price histories for 220 NBA games (2026 playoffs: 86, 2026-27 so far: 84, 2025-26 Mar-Apr: 50), graded on ESPN box scores. A void (player did not play) is not counted.

## Summary

* **1xBet against Pinnacle (the line-shopping test).** 1 hour before tip-off, 26 1xBet prices in 76 games beat Pinnacle's fair price by 2%+ (about 0.3 a game). Against Pinnacle's last price they averaged +3.6%, the sign of a real edge, but on far too few bets to be sure; results so far: 6 won, 11 lost (ROI -31%, give or take 23%).
* **Our points model against Pinnacle.** On 1,989 lines the model adds nothing beyond Pinnacle's price (weight +0.16 ± 0.09); betting its side at 3%+ model value returned -2.1% ± 2.6% on 1343 bets, and those prices were -5.3% against Pinnacle's close. Its probabilities sit too far from the market: what it calls value is mostly its own error.
* Betway: the feed carries its points prices only until about 4-15 hours before tip-off, mostly before Pinnacle posts, so it could not be tested (the few prices on Pinnacle's line were about 6% below fair). DraftKings shows small value late but loses it on early prices, which Pinnacle moves away from; it is in the test only as a check (not a book we bet).

Prices by book:

| book | games | players | prices |
|---|---|---|---|
| 1xbet | 76 | 256 | 51984 |
| betway | 24 | 187 | 2484 |
| draftkings | 86 | 148 | 102895 |
| pinnacle | 220 | 315 | 158256 |

## Matching OddsPapi player ids to players

Ids with a name in OddsPapi's live feed are matched by name; an id matched this season keeps its player last season if he is in that season's games. The rest are matched by team and line. To check that, named ids were hidden a fifth at a time and matched like the rest. 'Gap' is how much better the best match fits than the next best; a season's matches are used from the smallest gap at which the check was 95%+ right (2026-27: 3, 2025-26: 2).

| season | gap at least | ids | correct |
|---|---|---|---|
| 2025-26 | 0.000 | 105 | 0.724 |
| 2025-26 | 0.500 | 82 | 0.817 |
| 2025-26 | 1.000 | 65 | 0.862 |
| 2025-26 | 2.000 | 43 | 0.953 |
| 2025-26 | 3.000 | 34 | 0.971 |
| 2025-26 | 5.000 | 20 | 0.950 |
| 2026-27 | 0.000 | 137 | 0.796 |
| 2026-27 | 0.500 | 112 | 0.884 |
| 2026-27 | 1.000 | 93 | 0.946 |
| 2026-27 | 2.000 | 79 | 0.949 |
| 2026-27 | 3.000 | 66 | 0.970 |
| 2026-27 | 5.000 | 40 | 1.000 |

Ids used, by how they were matched:

| season | carried | matched | name |
|---|---|---|---|
| 2025-26 | 13 | 11 | 126 |
| 2026-27 | 0 | 13 | 156 |

## Is Pinnacle's closing price honest?

Pinnacle's no-vig chance of the over at its last pre-game price, against what happened:

| bin | lines | predicted | happened |
|---|---|---|---|
| (0.0, 0.4] | 11 | 0.387 | 0.273 |
| (0.4, 0.45] | 108 | 0.435 | 0.463 |
| (0.45, 0.5] | 1009 | 0.483 | 0.425 |
| (0.5, 0.55] | 810 | 0.520 | 0.523 |
| (0.55, 0.6] | 65 | 0.564 | 0.677 |
| (0.6, 1.0] | 2 | 0.610 | 0.500 |

## Test A: soft-book prices that beat Pinnacle's fair price by 2%+

Same player, same line; one bet per player, book and time; 1 unit each. 'Value vs close' is the price against Pinnacle's last pre-game fair price for the same line (blank when Pinnacle no longer had that line). Results count only the bets whose player id is matched; 'all bets' and its value against the close need no match.

| check | book | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) | all bets | value vs close, all bets |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 min before | 1xbet | 20.000 | 0.650 | 1.918 | 0.038 | 0.030 | 1.000 | 0.242 | 0.209 | 26 | 0.026 |
| 15 min before | draftkings | 15.000 | 0.333 | 1.963 | 0.032 | 0.031 | 1.000 | -0.328 | 0.254 | 27 | 0.030 |
| 1h before | 1xbet | 17.000 | 0.353 | 1.909 | 0.047 | 0.042 | 1.000 | -0.313 | 0.233 | 26 | 0.036 |
| 1h before | draftkings | 11.000 | 0.727 | 1.977 | 0.030 | 0.019 | 1.000 | 0.439 | 0.279 | 20 | 0.022 |
| 3h before | 1xbet | 10.000 | 0.600 | 1.937 | 0.056 | 0.053 | 0.909 | 0.169 | 0.318 | 19 | 0.044 |
| 3h before | draftkings | 22.000 | 0.682 | 1.929 | 0.034 | -0.012 | 0.792 | 0.312 | 0.196 | 30 | -0.006 |
| 8h before | 1xbet | 11.000 | 0.636 | 1.931 | 0.057 | 0.052 | 0.727 | 0.216 | 0.291 | 11 | 0.052 |
| 8h before | draftkings | 36.000 | 0.500 | 1.874 | 0.040 | -0.032 | 0.405 | -0.071 | 0.157 | 50 | -0.016 |

How each book prices against Pinnacle 1 hour before tip-off (every price on the same line as Pinnacle's, both sides; 'value' = price × Pinnacle's fair chance − 1):

| book | prices on Pinnacle's line | average value | share above fair | share 2%+ above |
|---|---|---|---|---|
| 1xbet | 1068 | -0.076 | 0.051 | 0.024 |
| draftkings | 2081 | -0.059 | 0.039 | 0.010 |

1 hour before tip-off, by period:

| window | book | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|---|
| 2026 playoffs | draftkings | 11.000 | 0.727 | 1.977 | 0.030 | 0.019 | 1.000 | 0.439 | 0.279 |
| 2026-27 so far | 1xbet | 17.000 | 0.353 | 1.909 | 0.047 | 0.042 | 1.000 | -0.313 | 0.233 |

1 hour before tip-off, by how much value the price showed:

| ev band | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| 2-4% | 20.000 | 0.550 | 1.930 | 0.028 | 0.014 | 1.000 | 0.086 | 0.226 |
| 4-7% | 4.000 | 0.250 | 1.963 | 0.048 | 0.049 | 1.000 | -0.515 | 0.485 |
| 7-12% | 4.000 | 0.500 | 1.938 | 0.091 | 0.114 | 1.000 | -0.038 | 0.556 |

Checked and rejected: in the closing-price table Pinnacle's favoured side seems to come in more often than its price says. Bet at Pinnacle's own price 1 hour before tip-off it does not hold up period to period (and it was spotted after looking at results):

| window | bets | won % | avg odds | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|
| 2025-26 Mar-Apr | 308.000 | 0.516 | 1.789 | -0.077 | 0.051 |
| 2026 playoffs | 674.000 | 0.570 | 1.829 | 0.042 | 0.035 |
| 2026-27 so far | 657.000 | 0.559 | 1.766 | -0.014 | 0.034 |

## Test B: our points model against Pinnacle

Accuracy on 1,989 Pinnacle lines 1 hour before tip-off (Brier score, lower is better):

| Pinnacle no-vig | our model | half and half | always 50% |
|---|---|---|---|
| 0.2483 | 0.2565 | 0.2492 | 0.2500 |

Does the model add anything to Pinnacle's price? In a logistic regression of the result on Pinnacle's no-vig log-odds and the model's difference from it, the difference gets weight +0.16 (standard error 0.09); zero means no information beyond Pinnacle.

Betting the model's side at Pinnacle's own price when the model sees value of at least the threshold:

| thr | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| 0.000 | 1544.000 | 0.511 | 1.903 | 0.151 | -0.053 | 0.903 | -0.032 | 0.024 |
| 0.030 | 1343.000 | 0.516 | 1.906 | 0.171 | -0.053 | 0.898 | -0.021 | 0.026 |
| 0.060 | 1116.000 | 0.515 | 1.908 | 0.197 | -0.052 | 0.896 | -0.021 | 0.029 |
| 0.100 | 872.000 | 0.529 | 1.911 | 0.230 | -0.052 | 0.885 | 0.006 | 0.032 |

At a 3% threshold, by period:

| window | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| 2025-26 Mar-Apr | 213.000 | 0.545 | 1.880 | 0.156 | -0.058 | 0.681 | 0.025 | 0.065 |
| 2026 playoffs | 623.000 | 0.514 | 1.920 | 0.166 | -0.044 | 0.910 | -0.018 | 0.038 |
| 2026-27 so far | 507.000 | 0.507 | 1.900 | 0.184 | -0.061 | 0.974 | -0.043 | 0.042 |

## Test A and the model together

Soft-book value bets 1 hour before, split by whether the model agrees with the side:

| model | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| agrees | 13.000 | 0.385 | 1.948 | 0.040 | 0.035 | 1.000 | -0.233 | 0.281 |
| disagrees | 15.000 | 0.600 | 1.925 | 0.041 | 0.030 | 1.000 | 0.169 | 0.255 |

