# Europe: can the card prices actually be caught? (development games)

Pinnacle opens a game's totals a median **28 hours** before tip-off, typically around **13:00 Madrid time** the day before.

## 1. How long the value prices last

| value legs at Pinnacle's opening | median minutes until the price changed | still there after 15 min | still there after 30 min | still there after 60 min | still there after 120 min |
|---|---|---|---|---|---|
| 721.000 | 39.658 | 0.574 | 0.534 | 0.466 | 0.391 |

## 2. Acting 0-120 minutes after Pinnacle opens

| executed | rule | cards | mean odds | mean CLV | both won |
|---|---|---|---|---|---|
| Pinnacle open +0 min | locked | 9 | 3.682 | 0.128 | 0.556 |
| Pinnacle open +0 min | baseline | 17 | 3.116 | 0.073 | 0.294 |
| Pinnacle open +0 min | user_band | 22 | 2.886 | 0.043 | 0.273 |
| Pinnacle open +15 min | locked | 10 | 3.831 | 0.076 | 0.200 |
| Pinnacle open +15 min | baseline | 15 | 3.037 | 0.048 | 0.267 |
| Pinnacle open +15 min | user_band | 14 | 2.833 | 0.037 | 0.143 |
| Pinnacle open +30 min | locked | 10 | 3.770 | 0.065 | 0.300 |
| Pinnacle open +30 min | baseline | 17 | 3.092 | 0.025 | 0.294 |
| Pinnacle open +30 min | user_band | 13 | 2.817 | 0.020 | 0.308 |
| Pinnacle open +60 min | locked | 11 | 3.803 | 0.061 | 0.364 |
| Pinnacle open +60 min | baseline | 17 | 3.028 | 0.021 | 0.235 |
| Pinnacle open +60 min | user_band | 15 | 2.781 | 0.041 | 0.267 |
| Pinnacle open +120 min | locked | 10 | 3.818 | 0.050 | 0.300 |
| Pinnacle open +120 min | baseline | 12 | 3.044 | 0.039 | 0.333 |
| Pinnacle open +120 min | user_band | 11 | 2.744 | 0.041 | 0.364 |

## 3. Acting at fixed clock times

| decision time | rule | cards | mean CLV |
|---|---|---|---|
| pinnacle_open | locked | 9 | 0.128 |
| pinnacle_open | baseline | 17 | 0.073 |
| pinnacle_open | user_band | 22 | 0.043 |
| 24h | locked | 3 | 0.043 |
| 24h | baseline | 5 | 0.042 |
| 24h | user_band | 4 | 0.028 |
| 12h | locked | 2 | 0.025 |
| 12h | baseline | 7 | -0.002 |
| 12h | user_band | 7 | -0.009 |
| game_day_10am | locked | 2 | 0.025 |
| game_day_10am | baseline | 7 | 0.004 |
| game_day_10am | user_band | 7 | -0.011 |
| 6h | locked | 3 | 0.095 |
| 6h | baseline | 11 | 0.045 |
| 6h | user_band | 7 | 0.048 |
| 3h | locked | 2 | 0.103 |
| 3h | baseline | 9 | 0.045 |
| 3h | user_band | 8 | 0.018 |
| 1h | locked | 1 | 0.073 |
| 1h | baseline | 6 | 0.040 |
| 1h | user_band | 6 | 0.043 |

Reading: the value is largest in the first minutes after Pinnacle opens and about halves for a person acting 30-60 minutes later; at mid-morning on game day it is mostly gone, and some returns in the last hours before tip-off.
