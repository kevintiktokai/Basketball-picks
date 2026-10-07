# Data schema and provenance

## Sources (pinned, checksummed — see `config/config.yaml`)

| name | what | coverage | licence |
|---|---|---|---|
| `odds` | kyleskom/NBA-Machine-Learning-Sports-Betting `Data/OddsData.sqlite` @ `8e36b0b` | NBA 2007-08 → 2026-01-07: date, teams, total line (`OU`), spread, moneylines, final total, margin | no licence file — **fetched, never committed** |
| `box_regular`, `box_playoffs` | NocturneBear/NBA-Data-2010-2024 team game totals @ `a5f108b` | NBA 2010-11 → 2023-24 regular season + playoffs | MIT |

Raw files land in `data/raw/` (git-ignored) via `python -m data.sources`.

### What the total line is
For 2023-24 onward the scraper (`sbrscrape`, FanDuel) stored the book's
*current* line read after the game, i.e. effectively the **closing line**. For
earlier seasons the provenance is an archive whose timestamp is undocumented;
we treat every line as a closing/last pre-game line. **No Over/Under price is
stored**, so a standard −110 (1.909) price is assumed for every bet. Because
only one line per game exists, **CLV cannot be measured** and opening-line
strategies cannot be simulated.

## AVAILABLE / UNAVAILABLE / PROXY

| requested variable | status |
|---|---|
| date, teams, final scores, total | AVAILABLE (all seasons) |
| closing total line | AVAILABLE (single book / archive) |
| opening total, line movement, Over/Under prices | UNAVAILABLE |
| spread, moneyline | AVAILABLE (used as blowout-risk / game-state proxy) |
| rest days, back-to-backs | DERIVED from schedule |
| possessions, pace, ORtg/DRtg, eFG%, 3PA rate, FT rate, ORB%, TOV% (for & against) | AVAILABLE 2010-11 → 2023-24 only |
| player minutes / usage / injuries / lineups / suspensions | UNAVAILABLE (player box scores exist in the box repo but were not wired in; no injury feed) |
| travel distance, coach changes | UNAVAILABLE |
| other leagues (EuroLeague, ACB, NBL, WNBA, …) | UNAVAILABLE — no free historical totals data reachable |
| H2H | DERIVABLE but not built separately; team O/U trend used as the proxy |

## `data/processed/games.parquet` (one row per game)

| column | meaning |
|---|---|
| game_id | `YYYYMMDD_AWAY@HOME` |
| season | NBA season label, e.g. `2015-16` |
| date | game date (US) |
| home, away | franchise codes (Sonics→OKC, NJ Nets→BKN, Bobcats→CHA, NO Hornets→NOP) |
| line | bookmaker total |
| home_spread | expected home margin (positive = home favoured); sign normalised per season |
| ml_home, ml_away | American moneylines |
| home_pts, away_pts, total | final score |
| is_postseason | after the regular-season end date (play-in + playoffs) |
| box_game_id | NBA game id when matched to box scores |
| quality_flags | `implausible_line` (outside 150–300), `placeholder_line` (identical line+spread on ≥3 games of a date), `score_mismatch_vs_box`, `no_result`, `duplicate` |
| clean | no flags → used for modelling |

Quality rules use **pre-game information only** (never the result), so
exclusions cannot bias win rates. 23,575 of 23,612 games are clean.

## `data/processed/team_box.parquet` (one row per team-game)
NBA box totals for the team and its opponent (`*_opp`), plus `poss`
(average of both teams' FGA − ORB + TOV + 0.44·FTA) and `minutes`.

## `data/processed/features.parquet`
Games + point-in-time features (`features/pit.py`). `feature_asof` is the last
game date whose results entered the features; the pipeline asserts
`feature_asof < date` for every row.
