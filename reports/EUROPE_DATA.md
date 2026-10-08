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
* **The best source found is OddsPapi.** Its free key serves, per finished fixture, the
  opening and closing price of every outcome at every book (Pinnacle and bet365 included).
  The adapter is built and tested (`data/oddspapi.py`). It needs only a key.

## Sources, checked in this session

| source | what it gives | cost / access | status |
|---|---|---|---|
| Official EuroLeague API (`api-live.euroleague.net`, `live.euroleague.net`) | results, box scores, quarter scores, referees, venue, attendance, play-by-play; EuroLeague since 2000, EuroCup since 2008 | free, no key | ✅ **in use**: 4,888 games loaded |
| [OddsPapi](https://oddspapi.io/sports/basketball/euroleague) | per fixture: opening and closing price for every outcome at each book (`/fixtures/odds/clv`), full price timelines (`/fixtures/odds/historical`), live odds; 350+ books incl. Pinnacle, bet365, exchanges; totals ladders | free key ("the free tier reads the same endpoints as the paid one"); 100 history requests/min | ✅ adapter built and tested offline. **History depth unknown until a key is used.** |
| [The Odds API](https://the-odds-api.com/historical-odds-data/) | snapshots of featured markets (incl. totals) since June 2020, by bookmaker region (e.g. European books) | paid; 10 credits per region per market per snapshot | EuroLeague covered; **EuroCup not in any coverage list found**. Their site was down (HTTP 509) during this session, so pricing is unconfirmed |
| [Betfair historical data](https://github.com/betfair/historic-data-workbook) | exchange price history (last traded price) | Basic tier is free; needs a Betfair account | basketball coverage not verified |
| OddsPortal / BetExplorer | EuroLeague results with historical odds back to 1998-99 | pages load odds dynamically | not used: automated collection conflicts with their terms |
| sportsbookreview.com (our NCAAB/NBA source) | — | — | ❌ no European leagues |

A full 2020-26 backfill from OddsPapi is about 3,200 fixtures, one request each: roughly
40 minutes at their rate limit, if the free tier's history reaches that far back.

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
  settings (environment menu in the session title bar → *Edit*). Use *Network secrets*
  (*API credentials* in older apps) if that section is offered; otherwise add an environment
  variable named **`ODDSPAPI_KEY`**. A new session picks it up. Please don't paste the key
  into the chat.
* Then: `python -m data.oddspapi probe`. This shows which seasons carry odds, in about 40
  requests (under a minute). If ≥ 3 seasons are available, the backfill and the pre-registered European test
  follow. If history is shallow, the same key collects live odds daily from now on.
* Optional cross-check: one month of The Odds API to backfill EuroLeague 2020-26 totals.

## Disclosure: a bug found along the way

The tempo part of the rating model (`features/ratings.py`) left the venue term out of
predicted possessions. With almost no neutral-site games (NBA, EuroLeague) that made
predicted possessions about half size: NBA 50.7 instead of ~103. The fix is an opt-in
switch (`venue_tempo=True`), used for all European work. The locked NCAAB/NBA engines keep
the old behaviour so their recorded results reproduce exactly.

A development-only re-run of the locked NBA engine shows no material change: log-loss gain
7.3 → 7.0 (×10⁻⁴), 2021-23 ([`nba_tempo_fix_check.md`](nba_tempo_fix_check.md)). The 2023-26
NBA test seasons were not reopened. The NBA conclusion stands.
