# Improvement study 6 — venue park factor and high altitude (NCAAB)

_Pre-registered in `config/improvements.yaml` (`study_6`) before any candidate was fitted. Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._

Non-neutral games with a venue history: 87% of 2011-21 games; venue factor sd 1.40 points; high-altitude venues 3.9% of games.

## Selection (2011-21)

| engine | era | games | log loss | matched bets | matched win | matched ROI @-110 | bets P>=55% | ROI @-110 at P>=55% |
|---|---|---|---|---|---|---|---|---|
| locked_v3 | dev 2011-18 | 16834 | 0.6881 | 4395 | 0.5780 | 0.1025 | 4395 | 0.1025 |
| locked_v3 | holdout 2018-21 | 12696 | 0.6895 | 2262 | 0.5673 | 0.0818 | 2262 | 0.0818 |
| locked_v3 | 2011-21 | 29530 | 0.6887 | 6657 | 0.5744 | 0.0954 | 6657 | 0.0954 |
| V1_venue | dev 2011-18 | 16834 | 0.6874 | 4395 | 0.5874 | 0.1201 | 4630 | 0.1201 |
| V1_venue | holdout 2018-21 | 12696 | 0.6884 | 2262 | 0.5796 | 0.1050 | 2803 | 0.0920 |
| V1_venue | 2011-21 | 29530 | 0.6879 | 6657 | 0.5847 | 0.1149 | 7433 | 0.1095 |
| V2_venue_altitude | dev 2011-18 | 16834 | 0.6873 | 4395 | 0.5860 | 0.1175 | 4739 | 0.1250 |
| V2_venue_altitude | holdout 2018-21 | 12696 | 0.6881 | 2262 | 0.5781 | 0.1024 | 2928 | 0.1021 |
| V2_venue_altitude | 2011-21 | 29530 | 0.6876 | 6657 | 0.5833 | 0.1123 | 7667 | 0.1163 |

Locked engine's bets by venue factor (secondary, 2011-21):

| venue factor | bets | won | ROI @-110 |
|---|---|---|---|
| strong, agrees with the bet | 1577 | 0.591 | 0.128 |
| strong, against the bet | 1481 | 0.552 | 0.054 |
| weak or neutral site | 3525 | 0.576 | 0.100 |

Qualifies (lower log loss AND higher matched ROI in both eras): V1_venue **True**, V2_venue_altitude **True**. Selected: **V1_venue**.

## Confirmation on the sealed 2021-26 seasons (run once)

| engine | games | log loss | matched bets | matched win | matched ROI @-110 | matched ROI real price | bets P>=55% | ROI @-110 at P>=55% |
|---|---|---|---|---|---|---|---|---|
| locked_v3 | 25364 | 0.6910 | 3510 | 0.5677 | 0.0834 | 0.1026 | 3510 | 0.0834 |
| V1_venue | 25364 | 0.6908 | 3510 | 0.5652 | 0.0785 | 0.0980 | 4147 | 0.0694 |

Season by season:

| engine | season | games | log loss | matched bets | matched win | matched ROI @-110 | matched ROI real price | bets P>=55% | ROI @-110 at P>=55% |
|---|---|---|---|---|---|---|---|---|---|
| locked_v3 | 2021-22 | 4872 | 0.6902 | 1380 | 0.5703 | 0.0883 | 0.1037 | 1380 | 0.0883 |
| locked_v3 | 2022-23 | 5026 | 0.6885 | 503 | 0.6248 | 0.1919 | 0.2144 | 503 | 0.1919 |
| locked_v3 | 2023-24 | 5160 | 0.6927 | 1331 | 0.5450 | 0.0402 | 0.0610 | 1331 | 0.0402 |
| locked_v3 | 2024-25 | 5073 | 0.6932 | 208 | 0.5144 | -0.0179 | 0.0012 | 208 | -0.0179 |
| locked_v3 | 2025-26 | 5233 | 0.6906 | 88 | 0.6705 | 0.2800 | 0.3131 | 88 | 0.2800 |
| V1_venue | 2021-22 | 4872 | 0.6909 | 1380 | 0.5648 | 0.0779 | 0.0930 | 1564 | 0.0585 |
| V1_venue | 2022-23 | 5026 | 0.6881 | 503 | 0.6108 | 0.1654 | 0.1819 | 556 | 0.1607 |
| V1_venue | 2023-24 | 5160 | 0.6926 | 1331 | 0.5485 | 0.0467 | 0.0681 | 1530 | 0.0392 |
| V1_venue | 2024-25 | 5073 | 0.6926 | 208 | 0.5577 | 0.0647 | 0.0921 | 333 | 0.0663 |
| V1_venue | 2025-26 | 5233 | 0.6899 | 88 | 0.5795 | 0.1064 | 0.1619 | 164 | 0.1524 |

Locked engine's 2021-26 bets by venue factor (secondary):

| venue factor | bets | won | ROI @-110 |
|---|---|---|---|
| strong, agrees with the bet | 885 | 0.572 | 0.092 |
| strong, against the bet | 671 | 0.539 | 0.030 |
| weak or neutral site | 1935 | 0.576 | 0.099 |

2.5+ target cards and main-line doubles at real prices, 2021-26:

| engine | product | cards | hit | leg_win | roi | roi_ci95 |
|---|---|---|---|---|---|---|
| locked_v3 | TARGET CARD | 664 | 0.468 | 0.676 | 0.199 | 0.104–0.295 |
| locked_v3 | MAIN-LINE DOUBLE | 652 | 0.356 | 0.590 | 0.290 | 0.163–0.426 |
| V1_venue | TARGET CARD | 664 | 0.485 | 0.691 | 0.240 | 0.143–0.337 |
| V1_venue | MAIN-LINE DOUBLE | 653 | 0.368 | 0.602 | 0.334 | 0.199–0.466 |

**Confirmation passed: False** (lower log loss, matched ROI not lower at -110 and at the best real price).
