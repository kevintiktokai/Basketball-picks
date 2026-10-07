# Stage 2b — independent test on NCAAB 2021-22..2025-26 (run once)

_Run note: the first execution crashed in the SECONDARY real-price section (a duplicate `books_json` column from a merge) after printing the v2 card table. The merge was fixed and the script re-run unchanged otherwise; the computation is deterministic, so the v2 card results below are identical to the first execution. v3 had not been reached._

Data: {"archive_games": 57116, "archive_team_keys_espn_share": 0.999877442397927, "live_games": 30851, "live_box_matched": 0.8498589997082753, "live_team_keys_espn_share": 1.0}

Raw scrape provenance: 1612 JSON files, manifest sha256 `b7cd8dea843c0ee0…`

| season | games | open | close |
|---|---|---|---|
| 2021-22 | 5963 | 5408 | 5408 |
| 2022-23 | 6065 | 5576 | 5576 |
| 2023-24 | 6243 | 5690 | 5690 |
| 2024-25 | 6281 | 5579 | 5579 |
| 2025-26 | 6299 | 5749 | 5749 |

## Engine v2_primary — two-pick buffered cards

| season | cards | 2of2 | 1of2 | 0of2 | rate_2of2 | ci95 | leg_win | leg_pred | model_joint | avg_buffer | roi_open_px_4.5% | roi_close_px_4.5% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-22 | 130 | 75 | 53 | 2 | 0.577 | 0.491–0.658 | 0.781 | 0.797 | 0.634 | 10.319 | -0.015 | -0.082 |
| 2022-23 | 128 | 93 | 30 | 5 | 0.727 | 0.644–0.796 | 0.844 | 0.797 | 0.633 | 10.682 | 0.218 | 0.131 |
| 2023-24 | 136 | 85 | 44 | 7 | 0.625 | 0.541–0.702 | 0.787 | 0.796 | 0.633 | 10.393 | 0.061 | -0.008 |
| 2024-25 | 134 | 82 | 44 | 8 | 0.612 | 0.527–0.690 | 0.776 | 0.796 | 0.632 | 10.690 | 0.014 | -0.049 |
| 2025-26 | 136 | 89 | 38 | 9 | 0.654 | 0.571–0.729 | 0.794 | 0.796 | 0.632 | 10.616 | 0.093 | -0.031 |
| POOLED | 664 | 424 | 209 | 31 | 0.639 | 0.601–0.674 | 0.796 | 0.796 | 0.633 | 10.540 | 0.074 | -0.009 |

Leg independence: corr +0.043; product of leg rates 63.2% vs actual 63.9%.
* both Over: 345 cards, 2/2 65.2%
* both Under: 117 cards, 2/2 72.6%
* mixed: 202 cards, 2/2 56.4%

Open→close move in our direction: +1.57 pts; moved our way 75.2%, against 18.3%.

Line-shopping variant (same legs; each leg's alternate line moved by the best book's opener advantage): 2/2 435/664 = 65.5% (CI 61.8%–69.0%).

Main-line log loss model 0.69117 vs market-only 0.69312 over 25364 games.

| two-sided P | bets | win_at_median_open | ci95 | roi_median_open_real_price | roi_best_book_open_real_price |
|---|---|---|---|---|---|
| 50%-55% | 18655 | 0.519 | 0.512–0.526 | -0.010 | inf |
| 55%-60% | 3526 | 0.569 | 0.553–0.585 | 0.085 | 0.105 |
| 60%-100% | 80 | 0.550 | 0.441–0.654 | 0.049 | 0.099 |

## Engine v3_secondary — two-pick buffered cards

| season | cards | 2of2 | 1of2 | 0of2 | rate_2of2 | ci95 | leg_win | leg_pred | model_joint | avg_buffer | roi_open_px_4.5% | roi_close_px_4.5% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-22 | 130 | 75 | 51 | 4 | 0.577 | 0.491–0.658 | 0.773 | 0.815 | 0.663 | 10.610 | -0.034 | -0.099 |
| 2022-23 | 128 | 95 | 31 | 2 | 0.742 | 0.660–0.810 | 0.863 | 0.814 | 0.662 | 11.637 | 0.190 | 0.120 |
| 2023-24 | 136 | 84 | 46 | 6 | 0.618 | 0.534–0.695 | 0.787 | 0.815 | 0.662 | 10.901 | 0.021 | -0.049 |
| 2024-25 | 134 | 91 | 37 | 6 | 0.679 | 0.596–0.752 | 0.817 | 0.813 | 0.659 | 12.172 | 0.049 | 0.004 |
| 2025-26 | 136 | 83 | 47 | 6 | 0.610 | 0.526–0.688 | 0.783 | 0.813 | 0.660 | 11.895 | -0.041 | -0.124 |
| POOLED | 664 | 428 | 212 | 24 | 0.645 | 0.607–0.680 | 0.804 | 0.814 | 0.661 | 11.446 | 0.036 | -0.031 |

Leg independence: corr -0.013; product of leg rates 64.7% vs actual 64.5%.
* both Over: 268 cards, 2/2 62.7%
* both Under: 202 cards, 2/2 67.8%
* mixed: 194 cards, 2/2 63.4%

Open→close move in our direction: +1.44 pts; moved our way 72.5%, against 19.4%.

Line-shopping variant (same legs; each leg's alternate line moved by the best book's opener advantage): 2/2 444/664 = 66.9% (CI 63.2%–70.3%).

Main-line log loss model 0.69104 vs market-only 0.69312 over 25364 games.

| two-sided P | bets | win_at_median_open | ci95 | roi_median_open_real_price | roi_best_book_open_real_price |
|---|---|---|---|---|---|
| 50%-55% | 18345 | 0.522 | 0.515–0.530 | -0.004 | inf |
| 55%-60% | 3268 | 0.566 | 0.549–0.583 | 0.081 | 0.100 |
| 60%-100% | 223 | 0.587 | 0.522–0.650 | 0.121 | 0.129 |


_Addendum (after the run): the `inf` in the best-book column of the 50–55% row is caused by a
malformed `0` American price in the feed for one book; the parser now rejects prices with
|odds| < 100. That row is not a betting bucket; the median-price columns and all other cells
are finite._
