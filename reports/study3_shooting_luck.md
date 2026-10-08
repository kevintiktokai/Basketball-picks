# Improvement study 3 — shooting-luck-neutral ratings (NCAAB)

_Pre-registered in `config/improvements.yaml` (`study_3`) before the candidate was fitted. Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._

How similar the new features are to the engine's (2011-21 correlations):

| index | x_pts | x_pts_n | x_eff | x_eff_n |
|---|---|---|---|---|
| x_pts | 1.000 | 0.847 | 0.929 | 0.804 |
| x_pts_n | 0.847 | 1.000 | 0.759 | 0.953 |
| x_eff | 0.929 | 0.759 | 1.000 | 0.827 |
| x_eff_n | 0.804 | 0.953 | 0.827 | 1.000 |

## Selection (2011-21)

| engine | era | games | log loss | matched bets | matched win | matched ROI @-110 | bets P>=55% | ROI @-110 at P>=55% |
|---|---|---|---|---|---|---|---|---|
| locked_v3 | dev 2011-18 | 16834 | 0.6881 | 4395 | 0.5780 | 0.1025 | 4395 | 0.1025 |
| locked_v3 | holdout 2018-21 | 12696 | 0.6895 | 2262 | 0.5673 | 0.0818 | 2262 | 0.0818 |
| locked_v3 | 2011-21 | 29530 | 0.6887 | 6657 | 0.5744 | 0.0954 | 6657 | 0.0954 |
| L1_shooting_neutral | dev 2011-18 | 16834 | 0.6882 | 4395 | 0.5773 | 0.1011 | 4641 | 0.0954 |
| L1_shooting_neutral | holdout 2018-21 | 12696 | 0.6894 | 2262 | 0.5601 | 0.0683 | 2073 | 0.0749 |
| L1_shooting_neutral | 2011-21 | 29530 | 0.6887 | 6657 | 0.5715 | 0.0900 | 6714 | 0.0891 |

Qualifies (lower log loss AND higher matched ROI in both eras): L1_shooting_neutral **False**. Selected: **none**.

No candidate qualified, so the 2021-26 seasons stay sealed.
