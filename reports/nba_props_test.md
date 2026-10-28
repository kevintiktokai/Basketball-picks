# NBA player points props at real prices

Data: OddsPapi pre-game price histories for 192 NBA games (2026 playoffs: 86, 2026-27 so far: 56, 2025-26 Mar-Apr: 50), graded on ESPN box scores. A void (player did not play) is not counted.

## Summary

* **1xBet against Pinnacle (the line-shopping test).** 1 hour before tip-off, 23 1xBet prices in 55 games beat Pinnacle's fair price by 2%+ (about 0.4 a game). Against Pinnacle's last price they averaged +4.0%, the sign of a real edge, but on far too few bets to be sure; results so far: 8 won, 9 lost (ROI -11%, give or take 24%).
* **Our points model against Pinnacle.** On 1,755 lines the model adds nothing beyond Pinnacle's price (weight +0.07 ± 0.10); betting its side at 3%+ model value returned -3.4% ± 2.8% on 1191 bets, and those prices were -5.1% against Pinnacle's close. Its probabilities sit too far from the market: what it calls value is mostly its own error.
* Betway: the feed carries its points prices only until about 4-15 hours before tip-off, mostly before Pinnacle posts, so it could not be tested (the few prices on Pinnacle's line were about 6% below fair). DraftKings shows small value late but loses it on early prices, which Pinnacle moves away from; it is in the test only as a check (not a book we bet).

Prices by book:

| book | games | players | prices |
|---|---|---|---|
| 1xbet | 55 | 246 | 38256 |
| betway | 24 | 187 | 2484 |
| draftkings | 86 | 148 | 102895 |
| pinnacle | 192 | 309 | 147512 |

## Matching OddsPapi player ids to players

Ids with a name in OddsPapi's live feed are matched by name; an id matched this season keeps its player last season if he is in that season's games. The rest are matched by team and line. To check that, named ids were hidden a fifth at a time and matched like the rest. 'Gap' is how much better the best match fits than the next best; a season's matches are used from the smallest gap at which the check was 95%+ right (2026-27: 1, 2025-26: 3).

| season | gap at least | ids | correct |
|---|---|---|---|
| 2025-26 | 0.000 | 103 | 0.728 |
| 2025-26 | 0.500 | 82 | 0.817 |
| 2025-26 | 1.000 | 65 | 0.862 |
| 2025-26 | 2.000 | 44 | 0.932 |
| 2025-26 | 3.000 | 34 | 0.971 |
| 2025-26 | 5.000 | 20 | 0.950 |
| 2026-27 | 0.000 | 128 | 0.766 |
| 2026-27 | 0.500 | 102 | 0.853 |
| 2026-27 | 1.000 | 80 | 0.950 |
| 2026-27 | 2.000 | 66 | 0.985 |
| 2026-27 | 3.000 | 58 | 0.983 |
| 2026-27 | 5.000 | 35 | 1.000 |

Ids used, by how they were matched:

| season | carried | matched | name |
|---|---|---|---|
| 2025-26 | 16 | 8 | 126 |
| 2026-27 | 0 | 22 | 146 |

## Is Pinnacle's closing price honest?

Pinnacle's no-vig chance of the over at its last pre-game price, against what happened:

| bin | lines | predicted | happened |
|---|---|---|---|
| (0.0, 0.4] | 7 | 0.388 | 0.429 |
| (0.4, 0.45] | 75 | 0.436 | 0.480 |
| (0.45, 0.5] | 902 | 0.484 | 0.430 |
| (0.5, 0.55] | 728 | 0.520 | 0.544 |
| (0.55, 0.6] | 45 | 0.563 | 0.711 |
| (0.6, 1.0] | 1 | 0.607 | 0.000 |

## Test A: soft-book prices that beat Pinnacle's fair price by 2%+

Same player, same line; one bet per player, book and time; 1 unit each. 'Value vs close' is the price against Pinnacle's last pre-game fair price for the same line (blank when Pinnacle no longer had that line). Results count only the bets whose player id is matched; 'all bets' and its value against the close need no match.

| check | book | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) | all bets | value vs close, all bets |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 min before | 1xbet | 19.000 | 0.684 | 1.903 | 0.038 | 0.030 | 1.000 | 0.291 | 0.207 | 23 | 0.028 |
| 15 min before | draftkings | 14.000 | 0.357 | 1.963 | 0.032 | 0.032 | 1.000 | -0.280 | 0.268 | 27 | 0.030 |
| 1h before | 1xbet | 17.000 | 0.471 | 1.902 | 0.047 | 0.048 | 1.000 | -0.112 | 0.236 | 23 | 0.040 |
| 1h before | draftkings | 12.000 | 0.667 | 1.979 | 0.030 | 0.018 | 1.000 | 0.319 | 0.282 | 20 | 0.022 |
| 3h before | 1xbet | 10.000 | 0.600 | 1.898 | 0.058 | 0.051 | 0.909 | 0.130 | 0.309 | 17 | 0.044 |
| 3h before | draftkings | 22.000 | 0.682 | 1.929 | 0.032 | -0.012 | 0.826 | 0.312 | 0.196 | 30 | -0.006 |
| 8h before | 1xbet | 9.000 | 0.556 | 1.947 | 0.048 | 0.054 | 0.778 | 0.073 | 0.340 | 9 | 0.054 |
| 8h before | draftkings | 34.000 | 0.471 | 1.873 | 0.039 | -0.036 | 0.412 | -0.129 | 0.161 | 50 | -0.016 |

How each book prices against Pinnacle 1 hour before tip-off (every price on the same line as Pinnacle's, both sides; 'value' = price × Pinnacle's fair chance − 1):

| book | prices on Pinnacle's line | average value | share above fair | share 2%+ above |
|---|---|---|---|---|
| 1xbet | 840 | -0.079 | 0.056 | 0.027 |
| draftkings | 2081 | -0.059 | 0.039 | 0.010 |

1 hour before tip-off, by period:

| window | book | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|---|
| 2026 playoffs | draftkings | 12.000 | 0.667 | 1.979 | 0.030 | 0.018 | 1.000 | 0.319 | 0.282 |
| 2026-27 so far | 1xbet | 17.000 | 0.471 | 1.902 | 0.047 | 0.048 | 1.000 | -0.112 | 0.236 |

1 hour before tip-off, by how much value the price showed:

| ev band | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| 2-4% | 20.000 | 0.600 | 1.937 | 0.028 | 0.017 | 1.000 | 0.170 | 0.220 |
| 4-7% | 5.000 | 0.400 | 1.918 | 0.047 | 0.047 | 1.000 | -0.264 | 0.452 |
| 7-12% | 4.000 | 0.500 | 1.938 | 0.091 | 0.114 | 1.000 | -0.038 | 0.556 |

Checked and rejected: in the closing-price table Pinnacle's favoured side seems to come in more often than its price says. Bet at Pinnacle's own price 1 hour before tip-off it does not hold up period to period (and it was spotted after looking at results):

| window | bets | won % | avg odds | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|
| 2025-26 Mar-Apr | 314.000 | 0.519 | 1.790 | -0.072 | 0.051 |
| 2026 playoffs | 656.000 | 0.569 | 1.830 | 0.041 | 0.035 |
| 2026-27 so far | 461.000 | 0.551 | 1.770 | -0.024 | 0.041 |

## Test B: our points model against Pinnacle

Accuracy on 1,755 Pinnacle lines 1 hour before tip-off (Brier score, lower is better):

| Pinnacle no-vig | our model | half and half | always 50% |
|---|---|---|---|
| 0.2486 | 0.2591 | 0.2508 | 0.2500 |

Does the model add anything to Pinnacle's price? In a logistic regression of the result on Pinnacle's no-vig log-odds and the model's difference from it, the difference gets weight +0.07 (standard error 0.10); zero means no information beyond Pinnacle.

Betting the model's side at Pinnacle's own price when the model sees value of at least the threshold:

| thr | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| 0.000 | 1376.000 | 0.504 | 1.904 | 0.147 | -0.051 | 0.900 | -0.045 | 0.026 |
| 0.030 | 1191.000 | 0.508 | 1.907 | 0.168 | -0.051 | 0.893 | -0.034 | 0.028 |
| 0.060 | 987.000 | 0.503 | 1.909 | 0.194 | -0.050 | 0.892 | -0.043 | 0.030 |
| 0.100 | 767.000 | 0.516 | 1.911 | 0.227 | -0.050 | 0.885 | -0.017 | 0.034 |

At a 3% threshold, by period:

| window | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| 2025-26 Mar-Apr | 216.000 | 0.537 | 1.879 | 0.155 | -0.058 | 0.681 | 0.010 | 0.064 |
| 2026 playoffs | 607.000 | 0.509 | 1.920 | 0.162 | -0.044 | 0.913 | -0.027 | 0.039 |
| 2026-27 so far | 368.000 | 0.489 | 1.902 | 0.186 | -0.059 | 0.986 | -0.072 | 0.050 |

## Test A and the model together

Soft-book value bets 1 hour before, split by whether the model agrees with the side:

| model | bets | won % | avg odds | value at bet time | value vs close | close found | ROI | ROI ± (1 se) |
|---|---|---|---|---|---|---|---|---|
| agrees | 13.000 | 0.385 | 1.968 | 0.039 | 0.034 | 1.000 | -0.233 | 0.281 |
| disagrees | 16.000 | 0.688 | 1.906 | 0.041 | 0.036 | 1.000 | 0.310 | 0.229 |

