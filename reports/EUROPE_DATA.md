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
* **The best free source is OddsPapi's free key.** One request returns a finished game's full
  price timeline at up to three books (Pinnacle and bet365 included), giving the opening line,
  the closing line and the alternate ladder. The free tier allows about 200 requests a month,
  and its history probably starts in 2024 (the company was founded then). Backfilling 2024-26
  (1,123 games) therefore takes about **6 months of free quota**; the current season costs about
  80 requests a month. The adapter is built for the free API, never exceeds the budget, and is
  tested offline (`data/oddspapi.py`). It needs only the key.

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
| backfill 2024-25 and 2025-26 (EuroLeague 732 + EuroCup 391 games) | 1,123, one per game |
| current season, as games finish | ~80 a month |

At 200 a month that is about 6 months to cover 2024-26 while keeping the current season
complete. `python -m data.oddspapi update` spends whatever is left of the month, newest games
first, and stops at the budget. Each month the quota is unused, ~200 games of history are
not collected.

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

* **A free OddsPapi key** (sign up at oddspapi.io). Add it in this cloud environment's
  settings (environment menu in the session title bar → *Edit*) under the name
  **`ODDSPAPI_KEY`**: *Network secrets* (*API credentials* in older apps) if offered,
  otherwise an environment variable. A new session picks it up. Please don't paste the key
  into the chat.
* Then: `probe` (≤ 8 requests) shows how far back the free history goes; `update` once a month
  spends that month's quota; `parse` builds the opening/closing/ladder tables.
* Optional and also free: a Betfair account would unlock exchange price files that may reach
  back much further. Send one downloaded basketball file and the parser will be built against it.
* With two seasons the protocol is: develop on 2024-25, test once on 2025-26, then the forward
  ledger. First question to answer: do soft-book openers beat Pinnacle's fair price often enough?

## Disclosure: a bug found along the way

The tempo part of the rating model (`features/ratings.py`) left the venue term out of
predicted possessions. With almost no neutral-site games (NBA, EuroLeague) that made
predicted possessions about half size: NBA 50.7 instead of ~103. The fix is an opt-in
switch (`venue_tempo=True`), used for all European work. The locked NCAAB/NBA engines keep
the old behaviour so their recorded results reproduce exactly.

A development-only re-run of the locked NBA engine shows no material change: log-loss gain
7.3 → 7.0 (×10⁻⁴), 2021-23 ([`nba_tempo_fix_check.md`](nba_tempo_fix_check.md)). The 2023-26
NBA test seasons were not reopened. The NBA conclusion stands.
