# Stage 2 — Over AND Under, NCAA basketball, buffered two-pick cards

**Status: DRAFT — the stage-2b independent-test section is filled in after its one-time run.**

## The question

Can a two-pick card (both legs must win) hit **≥ 60%** out of sample, now that the
engine may pick **Over or Under**, any basketball market, and any line?

## Why stage 1 could not

Two independent legs need ≈ 77.5% each for a 60% joint result. At the bookmaker's
main line the best model never exceeds ~60–65% per leg (NBA close: 61%; NCAAB open:
~70% at the very top). Same-night games are independent (|corr| < 0.01 in both
leagues), so correlation cannot rescue the product.

## What changed in stage 2

| lever | what it does | effect |
|---|---|---|
| **NCAA data** (SBR archive 2007-21 + ESPN box scores) | 57k games, 14 seasons, opening AND closing totals, half-time lines | softer market, 50–100 games per night |
| **Opening line** as the bet | bet before the market sharpens | log-loss gain vs market 27–59×10⁻⁴ (NBA close: ~9) |
| **Tempo-free ratings + style matchups** | date-by-date ridge ratings (points, efficiency, tempo) + 3P/FT/ORB/TOV matchups | biggest model gains |
| **Over or Under** | both sides screened | ~2× the candidate pool |
| **Variance model + edge-aware calibration** | per-game SD; P(win) for ANY line, conservative bound by clustered sandwich | honest probabilities at alternate lines |
| **Buffered (alternate-line) cards** | each leg's line moved in the bettor's favour until the conservative joint ≥ target | makes 60% reachable — hit rate is bought with price |

## Iterations (development seasons only; full log in `ITERATIONS.md`)

| step | market | change | dev 2/2 (validation) |
|---|---|---|---|
| it01 | NCAAB open | base ratings | 57.2% |
| it02–04 | open | + market-memory features, variance model | 62.4–62.7% (later found to include a small leak) |
| fix | open | tempo centring leak removed | 59.5% |
| it10 (locked as v2) | open | + box-score style matchups | 64.0% |
| it07 | close | same model at the close | 60.6% but EV < 0 (no edge) |
| it08 | 2nd half | half-time market | 58.7%, no edge |
| v3 | open | recency-weighted model + calibration, J = 0.65 | 66.0% on 2018-21 |

## Out-of-sample results

| test | engine | cards | 2/2 | 95% CI |
|---|---|---|---|---|
| Stage-2 holdout NCAAB 2018-21 (run once) | v2 | 363 | **60.9%** | 55.8–65.8% |
| Stage-2b independent test NCAAB 2021-26 | v2 (primary) | _pending_ | _pending_ | _pending_ |
| Stage-2b independent test NCAAB 2021-26 | v3 (secondary) | _pending_ | _pending_ | _pending_ |

## Money: the part a hit rate does not tell you

A buffered leg at ~80% pays roughly 1.25 (−400). The card's double pays ~1.6–1.7.
Break-even 2/2 rate ≈ 1 / double odds ≈ 58–62%. Whether a card makes money depends on:

1. **Price timing.** The model's edge exists at the OPENING number. Alternate lines priced
   off the opener at a 4.5% margin: positive ROI in every test so far. Priced off the
   CLOSING number: about break-even to −7%.
2. **The book's alternate-line margin.** At 8% per leg the edge is mostly consumed.
3. **Line shopping.** Taking each leg at the best book's opener adds free buffer.

The CLI therefore prints, for each leg, the model's fair odds and the minimum double
odds at which the card is +EV. Only bet when the book's offer clears it.

## NBA

Buffered NBA cards on closing lines also reach 60–66% 2/2 (1,683 development slates),
but lose ~6% per card at a 4.5% margin: there is no information edge at the NBA close to
pay for the buffer. Not recommended.
