# Improvement study 4 — roster continuity (NCAAB)

_Pre-registered in `config/improvements.yaml` (`study_4`) before the candidate was fitted. Selection on 2011-21 only; a qualifying candidate is checked once on the sealed 2021-26 seasons._

Share of games with a continuity value, by season: 2011-12 83%, 2012-13 84%, 2013-14 84%, 2014-15 83%, 2015-16 83%, 2016-17 82%, 2017-18 83%, 2018-19 81%, 2019-20 82%, 2020-21 83%.

## Selection (2011-21)

| engine | era | games | log loss | matched bets | matched win | matched ROI @-110 | bets P>=55% | ROI @-110 at P>=55% |
|---|---|---|---|---|---|---|---|---|
| locked_v3 | dev 2011-18 | 16834 | 0.6881 | 4395 | 0.5780 | 0.1025 | 4395 | 0.1025 |
| locked_v3 | holdout 2018-21 | 12696 | 0.6895 | 2262 | 0.5673 | 0.0818 | 2262 | 0.0818 |
| locked_v3 | 2011-21 | 29530 | 0.6887 | 6657 | 0.5744 | 0.0954 | 6657 | 0.0954 |
| R1_continuity | dev 2011-18 | 16834 | 0.6881 | 4395 | 0.5813 | 0.1088 | 4391 | 0.1018 |
| R1_continuity | holdout 2018-21 | 12696 | 0.6894 | 2262 | 0.5715 | 0.0898 | 2224 | 0.0882 |
| R1_continuity | 2011-21 | 29530 | 0.6887 | 6657 | 0.5780 | 0.1023 | 6615 | 0.0972 |

Early-season games only (a team with < 6 games; secondary, not part of the rule):

| engine | early games | log loss | bets P>=55% | ROI @-110 |
|---|---|---|---|---|
| locked_v3 | 3801 | 0.6904 | 881 | 0.0991 |
| R1_continuity | 3801 | 0.6906 | 885 | 0.1037 |

Qualifies (lower log loss AND higher matched ROI in both eras): R1_continuity **False**. Selected: **none**.

No candidate qualified, so this study does not use the 2021-26 seasons.
