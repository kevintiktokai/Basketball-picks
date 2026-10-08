# Improvement study 2 — stage and matchup features (NCAAB)

_Pre-registered in `config/improvements.yaml` (`study_2`) before any candidate was fitted. Selection on 2011-21 only; the selected candidate is checked once on the sealed 2021-26 seasons._

Matched volume: in each season, each engine's N most confident games, N = the locked engine's number of P >= 55% bets that season (the choice of games never looks at results).

## Selection (2011-21)

| engine | era | games | log loss | matched bets | matched win | matched ROI @-110 | bets P>=55% | ROI @-110 at P>=55% |
|---|---|---|---|---|---|---|---|---|
| locked_v3 | dev 2011-18 | 16834 | 0.6881 | 4395 | 0.5780 | 0.1025 | 4395 | 0.1025 |
| locked_v3 | holdout 2018-21 | 12696 | 0.6895 | 2262 | 0.5673 | 0.0818 | 2262 | 0.0818 |
| locked_v3 | 2011-21 | 29530 | 0.6887 | 6657 | 0.5744 | 0.0954 | 6657 | 0.0954 |
| S1_stage | dev 2011-18 | 16834 | 0.6876 | 4395 | 0.5818 | 0.1096 | 4740 | 0.1077 |
| S1_stage | holdout 2018-21 | 12696 | 0.6896 | 2262 | 0.5531 | 0.0551 | 2301 | 0.0613 |
| S1_stage | 2011-21 | 29530 | 0.6885 | 6657 | 0.5721 | 0.0911 | 7041 | 0.0925 |
| S2_stage_matchup | dev 2011-18 | 16834 | 0.6878 | 4395 | 0.5837 | 0.1133 | 4540 | 0.1169 |
| S2_stage_matchup | holdout 2018-21 | 12696 | 0.6896 | 2262 | 0.5510 | 0.0513 | 2279 | 0.0527 |
| S2_stage_matchup | 2011-21 | 29530 | 0.6885 | 6657 | 0.5726 | 0.0922 | 6819 | 0.0954 |
| S3_stage_matchup_fatigue | dev 2011-18 | 16834 | 0.6878 | 4395 | 0.5815 | 0.1092 | 4501 | 0.1128 |
| S3_stage_matchup_fatigue | holdout 2018-21 | 12696 | 0.6896 | 2262 | 0.5519 | 0.0530 | 2266 | 0.0528 |
| S3_stage_matchup_fatigue | 2011-21 | 29530 | 0.6886 | 6657 | 0.5715 | 0.0901 | 6767 | 0.0927 |

Qualifies (lower log loss AND higher matched ROI in both eras): S1_stage **False**, S2_stage_matchup **False**, S3_stage_matchup_fatigue **False**. Selected: **none**.

No candidate qualified, so the 2021-26 seasons stay sealed.
