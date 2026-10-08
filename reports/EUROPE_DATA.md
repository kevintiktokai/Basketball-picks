# European basketball data: what exists, what was tested, what would make a difference

*October 2026. EuroLeague and EuroCup.*

## Bottom line

* **Free data exists and is now in the engine.** The official EuroLeague API covers results,
  box scores, the three referees and attendance for every game. This session loaded
  **3,049 EuroLeague and 1,839 EuroCup games (2016-17 to 2025-26)**, cached locally
  (`data/euroleague.py`).
* **On its own it does not create an edge.** A point-in-time team-rating model predicts
  totals with a residual SD of about 17 points (average bias under 1.1 points), and tuning
  barely moves that.
  Referee crews clearly change free-throw counts, but they move totals only about ±1 point
  at the extremes. That signal does not carry over from season to season. Adding referees
  and rest to the model improved out-of-sample error by **0.0%**
  ([`euro_info_study.md`](euro_info_study.md)).
* **What would make a difference is odds history:** opening and closing totals at
  several books, including Pinnacle, plus the alternate-line ladders. Our NCAAB edge was
  built on exactly this: stale openers, a market-memory record of each team, and checks
  against the close. Without it, nothing European can be tested or priced honestly.
* **The best free source is OddsPapi's free key, and it is now in use.** One request returns a
  finished game's full price timeline at up to three books, giving the opening line, the
  closing line and the alternate ladder. The free tier allows about 200 requests a month and
  its archive starts on **20 January 2026** (measured). October's quota fetched 144 games
  (20 Jan – 20 Mar 2026); the rest of 2025-26 takes about two more months, then the current
  season costs about 80 requests a month. First results are below.

## Sources, checked in this session

**Free:**

| source | what it gives | access | status |
|---|---|---|---|
| Official EuroLeague API | results, box scores, quarter scores, referees, venue, attendance, play-by-play; EuroLeague since 2000, EuroCup since 2008 | no key | ✅ **in use**: 4,888 games loaded |
| [OddsPapi](https://oddspapi.io/sports/basketball/euroleague) free tier (v4 API) | `/historical-odds`: each book's full price timeline per game (≤ 3 books per request), every market incl. totals ladders; Pinnacle, bet365 and 350+ others; live odds | free key; ~200 requests/month ([their figures vary: 200–250](https://oddspapi.io/blog/the-odds-api-free-tier-limits/)); history "from our archive ingestion start date" | ✅ adapter built and tested offline; `probe` measures the real history depth in ≤ 8 requests |
| [Betfair historical data](https://github.com/betfair/historic-data-workbook), Basic plan | exchange last-traded prices, 1-minute steps, monthly files; basketball sits in the ["Other Sports" files](https://support.developer.betfair.com/hc/en-us/articles/8085210924957-Which-Sports-Are-Included-in-the-Other-Sports-package) | free, needs a Betfair account (not available in every country) | possibly the deepest free history; parser not built until a sample file confirms the basketball market format |
| [API-Basketball](https://api-sports.io/sports/basketball) | odds from several books | free key, 100 requests/day | EuroLeague odds and how long odds are kept on the free plan are unconfirmed; at best a way to collect current odds |

**Checked and ruled out:**

| source | why not |
|---|---|
| [The Odds API](https://the-odds-api.com/historical-odds-data/) | historical odds on paid plans only (EuroLeague since June 2020; no EuroCup found) |
| odds-api.io, SportsGameOdds | free tiers have no historical odds |
| [Kaggle "European Basketball & FIBA Betting Odds"](https://www.kaggle.com/datasets/oliviersportsdata/european-basketball-and-fiba-betting-odds) | only a 50-row sample is free; the full set is sold; closing odds only, totals unconfirmed |
| Public GitHub/Zenodo/Hugging Face datasets | none with EuroLeague odds (e.g. [sportsdb](https://github.com/Sergio20/sportsdb) states that the basketball sources publish no odds) |
| OddsPortal / BetExplorer | have the history back to 1998-99, but automated collection conflicts with their terms |
| sportsbookreview.com (our NCAAB/NBA source) | no European leagues |

### The free budget, in practice

| item | requests |
|---|---|
| `probe` (key, catalogue, depth check) | ≤ 8, once |
| fixture lists (9 per season per competition, cached) | ~54, once |
| backfill 2025-26 from the archive start (20 Jan 2026; ~400 games) | one per game; 144 done in October |
| current season, as games finish | ~80 a month |

`python -m data.oddspapi update` spends whatever is left of the month, oldest games first
(in case the archive is a rolling window), and stops at the budget. Each month the quota is
unused, ~200 games are not collected.

## October 2026: the free key in use

**What the free tier really gives** (measured, not from the marketing pages):

* v4 API, about 200 requests a month, and a ~5-second cooldown between history requests.
  One request returns one game's full price history at up to three books (~20 MB, almost
  all of it in-game; the cache keeps the pre-game part, ~0.4 MB per game).
* **The archive starts on 20 January 2026** (nothing on 15 January or earlier). It may be a
  rolling ~9-month window, so games are fetched oldest first.
* Book coverage grows through 2025-26. Pinnacle's pre-game prices start in late January.
  1xBet has the fullest archive, then Betway; Unibet is patchy until March; bet365 has almost
  nothing before 2026-27. The soft books tracked are therefore **1xBet and Betway**, with
  Pinnacle as the reference ([`config/europe.yaml`](../config/europe.yaml), changed before
  any result was looked at).

**What was fetched:** 144 development games (EuroLeague and EuroCup, 20 Jan – 20 Mar 2026,
plus three later samples), all matched to official results; 110 have Pinnacle's closing
line. The pre-registration was committed before any of it was analysed.

**First development numbers** ([`euro_dev_q1q2.md`](euro_dev_q1q2.md)). Small samples, so
read them as direction, not proof:

| finding | numbers |
|---|---|
| Soft books' main line vs Pinnacle's fair line, when both are first posted | 1.0–1.2 points apart on average |
| Betting the soft line toward Pinnacle when the gap is ≥ 2 points | closing-line value **+2%** (1xBet 20 games, Betway 12); the close stays on Pinnacle's side ~75% of the time |
| Best soft price per game above Pinnacle's fair price, when Pinnacle opens | +4.8% expected, **+1.9% CLV** (74 games); with ≥ 4% expected: +4.5% CLV (35 games) |
| Same, 6 h / 1 h before tip, expected ≥ 2% | **+4.8% / +4.9% CLV**, beating the close in 87% / 94% of games (15 / 18 games) |
| Actual results | too few games to tell: ROI confidence intervals are ±25 to ±60 points wide |

Q3 and Q4 ([`euro_dev_q3q4.md`](euro_dev_q3q4.md), 108 games with both Pinnacle ladders):

| finding | numbers |
|---|---|
| Does Pinnacle's line move toward our rating model? | slightly: correlation +0.18 (95% CI 0.02–0.32) between the model's disagreement and the open-to-close move |
| Betting the model's side at Pinnacle's own price | CLV −3.6%: the model cannot beat Pinnacle's margin |
| Two-leg cards (combined ≥ 2.5) from soft prices above Pinnacle's fair price, when Pinnacle opens | 17 cards, mean odds 3.1 (break-even 32%), **joint CLV +7.3%**, 88% of cards beat the close; 5 of 17 won (too few to judge) |

The pattern a real price edge leaves is there: soft-book prices that beat Pinnacle's fair
price keep beating its close. In Europe the edge comes from prices, not from out-predicting
the market. It is small (2–5% per bet), and it is not yet proven by
results. Two such legs per card would make roughly +5–10% expected per card at the
user's odds. That is a long way from a 60% hit rate, but a positive-expectation process.

**Next:** each month's ~200 requests continue the backfill (21 Mar – May 2026, then
2026-27). Then the model (Q3) and cards with real ladder prices (Q4) are developed, the
engine is locked, and it is tested once on 2026-27.

## What the free data showed (details: [`euro_info_study.md`](euro_info_study.md))

| question | answer |
|---|---|
| How well do team ratings predict totals? | Residual SD 17.1 (EuroLeague), 17.5 (EuroCup). Totals vary 17.4 / 18.4 around the season mean. A grid of rating settings improves this by at most a quarter of a point. |
| Do referee crews matter? | They change free throws (correlation 0.11 with the game's FTA, t ≈ 6.7). The total moves only +2.0 to +2.5 points between the highest- and lowest-whistling fifth of crews. A referee's tendency in one season does not predict the next (correlation −0.01). |
| Does short rest (double-game weeks) matter? | An away team on ≤2 days' rest scores ~1.3 points fewer in total. Small. |
| Out of sample, referees + rest on top of ratings? | **No improvement** (MSE −0.01%). The most extreme fifths of games differ by ~2 points (46% vs 52% above the rating line). That is a small signal worth re-testing against real lines once odds exist. |

## What the European engine should look like

1. **Pinnacle as the reference price.** In Europe the cleanest edge is a soft book whose
   line or price beats Pinnacle's no-vig probability, ideally near the opening number. The
   OddsPapi data measures this directly, per book and per line.
2. **The rating model as a second opinion.** It supplies the variance model and market-memory
   features, as for NCAAB.
3. **Real ladder prices.** The two-leg card (combined ≥ 2.5) is built from posted alternate
   totals, so the modelled alternate prices of the US results disappear.
4. **The same protocol:** pre-registered splits, development on early seasons, lock, a
   one-time test, a CLV check, then a forward ledger.

## What is needed from you

* **The OddsPapi key, rotated.** The first key was used once and removed from this session;
  add the new one in this cloud environment's settings (environment menu in the session
  title bar → *Edit*) as **`ODDSPAPI_KEY`**, *Network secrets* (*API credentials* in older
  apps) if offered, otherwise an environment variable. A new session picks it up; please
  don't paste keys into the chat.
* Then, once a month: `python -m data.oddspapi update` (spends that month's quota, oldest
  games first) and `python scripts/euro_dev_study.py` (refreshes the development numbers).
* Optional and also free: a Betfair account would unlock exchange price files that may reach
  back much further. Send one downloaded basketball file and the parser will be built against it.
* Protocol ([`config/europe.yaml`](../config/europe.yaml)): develop on 2025-26 (from 20 Jan
  2026), lock, test once on 2026-27, then the forward ledger.

## Disclosure: a bug found along the way

The tempo part of the rating model (`features/ratings.py`) left the venue term out of
predicted possessions. With almost no neutral-site games (NBA, EuroLeague) that made
predicted possessions about half size: NBA 50.7 instead of ~103. The fix is an opt-in
switch (`venue_tempo=True`), used for all European work. The locked NCAAB/NBA engines keep
the old behaviour so their recorded results reproduce exactly.

A development-only re-run of the locked NBA engine shows no material change: log-loss gain
7.3 → 7.0 (×10⁻⁴), 2021-23 ([`nba_tempo_fix_check.md`](nba_tempo_fix_check.md)). The 2023-26
NBA test seasons were not reopened. The NBA conclusion stands.
