# NBA player points: probability model, season by season

Each season forecast by a model fitted only on earlier seasons; every forecast uses only the player's earlier games. Prop universe: 5+ games this season, 20+ minutes and 8+ points a game recently. Errors are average absolute misses in points.

| season | player-games | per day | model error (avg pts) | recent average error | season average error | bias | inside 50% range | inside 80% range |
|---|---|---|---|---|---|---|---|---|
| 2022-23 | 13801 | 68.662 | 5.498 | 5.447 | 5.498 | -0.018 | 0.516 | 0.824 |
| 2023-24 | 13345 | 67.741 | 5.463 | 5.480 | 5.537 | -0.173 | 0.518 | 0.819 |
| 2024-25 | 13978 | 68.857 | 5.420 | 5.466 | 5.532 | 0.001 | 0.504 | 0.808 |
| 2025-26 | 14113 | 70.214 | 5.358 | 5.412 | 5.509 | -0.221 | 0.511 | 0.810 |

Are the probabilities honest? Lines at every half-point from 4 below to 3 above each player's recent average (where books set them), all seasons pooled:

| bin | predicted | happened | n |
|---|---|---|---|
| (0.0, 0.2] | 0.159 | 0.190 | 3202 |
| (0.2, 0.3] | 0.264 | 0.279 | 28374 |
| (0.3, 0.4] | 0.354 | 0.347 | 74062 |
| (0.4, 0.45] | 0.425 | 0.404 | 46144 |
| (0.45, 0.5] | 0.475 | 0.454 | 48052 |
| (0.5, 0.55] | 0.525 | 0.504 | 47686 |
| (0.55, 0.6] | 0.575 | 0.552 | 46810 |
| (0.6, 0.7] | 0.649 | 0.627 | 85604 |
| (0.7, 0.8] | 0.742 | 0.710 | 53519 |
| (0.8, 1.0] | 0.826 | 0.781 | 8443 |

Strong calls: the model said 60%+ for one side on 57% of those lines, and it happened 67.0% of the time. Against real book lines this share would be much smaller: books set lines nearer the true middle than a recent average does.

By scoring role:

| role | player-games | model error | spread (sd) | season |
|---|---|---|---|---|
| 8-12 pts | 5057.000 | 4.702 | 6.281 | 2022-23 |
| 12-18 pts | 4528.000 | 5.363 | 7.103 | 2022-23 |
| 18-24 pts | 2577.000 | 6.211 | 8.033 | 2022-23 |
| 24+ pts | 1639.000 | 7.201 | 8.691 | 2022-23 |
| 8-12 pts | 4280.000 | 4.540 | 6.108 | 2023-24 |
| 12-18 pts | 4804.000 | 5.478 | 6.949 | 2023-24 |
| 18-24 pts | 2659.000 | 6.150 | 8.012 | 2023-24 |
| 24+ pts | 1602.000 | 6.746 | 8.767 | 2023-24 |
| 8-12 pts | 5259.000 | 4.660 | 5.940 | 2024-25 |
| 12-18 pts | 4583.000 | 5.464 | 6.811 | 2024-25 |
| 18-24 pts | 2793.000 | 6.112 | 7.860 | 2024-25 |
| 24+ pts | 1343.000 | 6.806 | 8.723 | 2024-25 |
| 8-12 pts | 4847.000 | 4.692 | 5.997 | 2025-26 |
| 12-18 pts | 5458.000 | 5.389 | 6.852 | 2025-26 |
| 18-24 pts | 2641.000 | 5.941 | 7.839 | 2025-26 |
| 24+ pts | 1167.000 | 6.653 | 8.624 | 2025-26 |

Through the season (model error by month):

| month | player-games | model error | recent average error | season |
|---|---|---|---|---|
| 2022-10 | 268.000 | 5.902 | 5.847 | 2022-23 |
| 2022-11 | 2337.000 | 5.532 | 5.473 | 2022-23 |
| 2022-12 | 2511.000 | 5.443 | 5.353 | 2022-23 |
| 2023-01 | 2528.000 | 5.286 | 5.219 | 2022-23 |
| 2023-02 | 1930.000 | 5.564 | 5.536 | 2022-23 |
| 2023-03 | 2606.000 | 5.513 | 5.457 | 2022-23 |
| 2023-04 | 1192.000 | 5.675 | 5.700 | 2022-23 |
| 2023-05 | 369.000 | 5.843 | 5.855 | 2022-23 |
| 2023-06 | 60.000 | 5.136 | 5.435 | 2022-23 |
| 2023-11 | 2127.000 | 5.256 | 5.316 | 2023-24 |
| 2023-12 | 2311.000 | 5.455 | 5.439 | 2023-24 |
| 2024-01 | 2528.000 | 5.503 | 5.493 | 2023-24 |
| 2024-02 | 1949.000 | 5.493 | 5.518 | 2023-24 |
| 2024-03 | 2385.000 | 5.503 | 5.484 | 2023-24 |
| 2024-04 | 1534.000 | 5.617 | 5.683 | 2023-24 |
| 2024-05 | 451.000 | 5.535 | 5.587 | 2023-24 |
| 2024-06 | 60.000 | 4.430 | 5.020 | 2023-24 |
| 2024-10 | 4.000 | 5.333 | 5.084 | 2024-25 |
| 2024-11 | 2290.000 | 5.366 | 5.401 | 2024-25 |
| 2024-12 | 2229.000 | 5.375 | 5.364 | 2024-25 |
| 2025-01 | 2595.000 | 5.278 | 5.276 | 2024-25 |
| 2025-02 | 2048.000 | 5.659 | 5.791 | 2024-25 |
| 2025-03 | 2661.000 | 5.320 | 5.319 | 2024-25 |
| 2025-04 | 1594.000 | 5.649 | 5.773 | 2024-25 |
| 2025-05 | 480.000 | 5.565 | 5.799 | 2024-25 |
| 2025-06 | 77.000 | 4.531 | 4.828 | 2024-25 |
| 2025-10 | 52.000 | 4.572 | 4.694 | 2025-26 |
| 2025-11 | 2392.000 | 5.292 | 5.326 | 2025-26 |
| 2025-12 | 2269.000 | 5.438 | 5.421 | 2025-26 |
| 2026-01 | 2638.000 | 5.203 | 5.193 | 2025-26 |
| 2026-02 | 1950.000 | 5.559 | 5.769 | 2025-26 |
| 2026-03 | 2741.000 | 5.398 | 5.416 | 2025-26 |
| 2026-04 | 1567.000 | 5.383 | 5.547 | 2025-26 |
| 2026-05 | 447.000 | 5.046 | 5.144 | 2025-26 |
| 2026-06 | 57.000 | 5.720 | 5.505 | 2025-26 |

## What this says about betting, and the next step

* Points are noisy: even the best forecast misses by about 5.4 points a game (4.6 for 8-12 point
  scorers, 6.7 for 24+). The model beats a player's recent average by only about 0.05 points over a
  season, but by 0.1-0.2 points in February and April, when trades and rest change roles.
* Its probabilities run about 2 points high on overs; a calibration step would fix that.
* Books set prop lines with the same box scores plus injury news, confirmed lineups and minutes
  projections. A box-score model alone is unlikely to beat their main lines. The realistic edges in
  points props are (1) books disagreeing with each other (the European approach: bet the book that is
  out of line with the rest), and (2) late news, mainly a teammate ruled out.
* Profit cannot be measured without the books' lines. Live lines in our odds feed (28 Oct 2026):
  FanDuel, DraftKings, BetMGM and Bovada carry NBA player points; Pinnacle, 1xBet and Betway do not.
  Live: 1 credit per game. Historical (from May 2023): paid plans only, about 10 credits per game, so
  one season of lines (~1,230 games) needs the 20,000-credit month (about $30).
