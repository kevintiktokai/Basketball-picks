# What the free EuroLeague / EuroCup data adds (official API, 2016-17 to 2025-26)

Point-in-time: ratings, referee tendencies and rest use only earlier dates. **No odds are used**, so this shows whether information exists beyond team strength, not whether the market already prices it. Scored seasons: 2019-20 to 2025-26.

## 1. Team-rating model accuracy

| competition | games | mean total | SD of totals (around season mean) | rating model residual SD | rating model MAE | mean residual |
|---|---|---|---|---|---|---|
| eurocup | 1323 | 164.7 | 18.4 | 17.5 | 14.0 | 1.1 |
| euroleague | 2270 | 163.1 | 17.4 | 17.1 | 13.3 | 0.7 |

## 2. Single factors (all games scored, not yet out of sample)

Group A/B = top/bottom quintile of the crew feature, or rested vs not.

| feature | corr with game FTA vs average | corr with total residual | group A: pts vs expected | group B | A minus B |
|---|---|---|---|---|---|
| crew free-throw tendency | 0.111 | 0.047 | 1.423 | -0.620 | 2.043 |
| crew foul tendency | 0.111 | 0.044 | 1.824 | -0.660 | 2.484 |
| crew past total-residual | 0.069 | 0.025 | 1.344 | 0.640 | 0.705 |
| home team on ≤2 days rest | — | -0.010 | 0.403 | 0.924 | -0.522 |
| away team on ≤2 days rest | — | -0.024 | -0.243 | 1.019 | -1.262 |

Referee free-throw tendency is persistent: a referee's season-to-season correlation is **-0.01** (n = 426 referee pairs with ≥15 games in consecutive seasons). Distinct referees: 111.

## 3. Out of sample: referees + rest on top of the rating model

Each season predicted by a regression fitted only on earlier seasons.

| season | games | baseline MSE | with referees+rest MSE | MSE reduction % |
|---|---|---|---|---|
| 2019-20 | 420 | 303.28 | 297.72 | 1.83 |
| 2020-21 | 513 | 310.67 | 309.35 | 0.43 |
| 2021-22 | 488 | 306.01 | 308.22 | -0.72 |
| 2022-23 | 523 | 259.80 | 259.47 | 0.12 |
| 2023-24 | 526 | 292.80 | 295.47 | -0.91 |
| 2024-25 | 526 | 287.52 | 287.99 | -0.16 |
| 2025-26 | 597 | 317.44 | 318.33 | -0.28 |
| all (out of sample) | 3593 | 296.89 | 296.91 | -0.01 |

Out-of-sample games grouped by the predicted adjustment (points vs the rating model):

| group | games | predicted adj (pts) | actual vs rating model (pts) | share above rating model |
|---|---|---|---|---|
| most Under-leaning 20% | 719 | -1.960 | -1.110 | 0.460 |
| 2nd | 718 | -0.408 | 0.620 | 0.499 |
| middle | 719 | 0.369 | -0.230 | 0.491 |
| 4th | 718 | 1.093 | 1.678 | 0.532 |
| most Over-leaning 20% | 719 | 2.138 | 0.875 | 0.519 |

Spread between the most Over- and most Under-leaning fifth: **+2.0 points** (residual SD 17.2). Near a fair line, 1 point is worth roughly 2.3 percentage points of win probability.

Fitted on all pre-2025-26 seasons, the coefficients (pts per unit) are: is_cup -0.27, crew_fta +0.61, crew_pf +1.29, crew_resid -0.07, short_rest_home +0.86, short_rest_away -2.10.

