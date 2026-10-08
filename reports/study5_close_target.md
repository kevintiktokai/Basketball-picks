# Improvement study 5 — learn from the closing line (NCAAB)

_Pre-registered in `config/improvements.yaml` (`study_5`) before any candidate was fitted. Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._

## Selection (2011-21)

| engine | era | games | log loss | matched bets | matched win | matched ROI @-110 | bets P>=55% | ROI @-110 at P>=55% |
|---|---|---|---|---|---|---|---|---|
| locked_v3 | dev 2011-18 | 16834 | 0.6881 | 4395 | 0.5780 | 0.1025 | 4395 | 0.1025 |
| locked_v3 | holdout 2018-21 | 12696 | 0.6895 | 2262 | 0.5673 | 0.0818 | 2262 | 0.0818 |
| locked_v3 | 2011-21 | 29530 | 0.6887 | 6657 | 0.5744 | 0.0954 | 6657 | 0.0954 |
| M1_close_target | dev 2011-18 | 16834 | 0.6893 | 4395 | 0.5753 | 0.0973 | 2810 | 0.1306 |
| M1_close_target | holdout 2018-21 | 12696 | 0.6902 | 2262 | 0.5664 | 0.0804 | 2342 | 0.0904 |
| M1_close_target | 2011-21 | 29530 | 0.6897 | 6657 | 0.5723 | 0.0916 | 5152 | 0.1123 |
| M2_move_feature | dev 2011-18 | 16834 | 0.6881 | 4395 | 0.5775 | 0.1016 | 4383 | 0.0989 |
| M2_move_feature | holdout 2018-21 | 12696 | 0.6895 | 2262 | 0.5664 | 0.0801 | 2282 | 0.0807 |
| M2_move_feature | 2011-21 | 29530 | 0.6887 | 6657 | 0.5738 | 0.0943 | 6665 | 0.0927 |

Qualifies (lower log loss AND higher matched ROI in both eras): M1_close_target **False**, M2_move_feature **False**. Selected: **none**.

No candidate qualified, so this study does not use the 2021-26 seasons.
