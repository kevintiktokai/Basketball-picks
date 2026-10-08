# Stage 2 — two-pick cards that hit 60%+: Over AND Under, NCAA basketball, buffered lines

## Bottom line

**Yes, with one condition.** A two-pick card can hit 2/2 more than 60% of the time on
seasons the engine never saw: **63.9% over 664 cards (95% CI 60.1–67.4%)** on NCAA
basketball 2021-22 to 2025-26. That is the pre-registered primary engine, locked before
those seasons' odds were downloaded. The condition is that the 60% is reached by
**buying points**: each leg is an *alternate* total about 10.5 points better than the
opening number, so each leg wins ~80% and the double pays only ~1.6–1.7. Profit then
depends on the price you get for those alternate lines (see "Money" below).

At the bookmaker's **main** line no version of the engine gets near 60%: the best
top-two-per-night card wins 2/2 about 35% of the time.

## Out-of-sample record (each test run exactly once, engine locked beforehand)

| test | engine | cards | 2/2 | 2/2 rate | 95% CI | leg win (predicted) |
|---|---|---|---|---|---|---|
| Holdout, NCAAB 2018-21 (SBR archive odds) | v2 | 363 | 221 | **60.9%** | 55.8–65.8% | 78.7% (79.8%) |
| Independent test, NCAAB 2021-26 (6 US books) | **v2, primary** | 664 | 424 | **63.9%** | **60.1–67.4%** | 79.6% (79.6%) |
| Independent test, NCAAB 2021-26 | v3, secondary | 664 | 428 | 64.5% | 60.7–68.0% | 80.4% (81.4%) |
| v2, both tests combined | v2 | 1,027 | 645 | 62.8% | 59.8–65.7% | |

Per season (v2, 2021-26): 57.7% · 72.7% · 62.5% · 61.2% · 65.4%. One season in five fell below
60%, so expect losing stretches. The longest run of non-2/2 cards in the 2018-21 holdout was 6.

**Line shopping** (same legs, each leg's alternate line taken from the book with the best
opener): v2 **65.5%** (CI 61.8–69.0%), v3 **66.9%** (CI 63.2–70.3%).

Other checks on the 2021-26 test:

* **The two legs win independently** (outcome correlation +0.04), so the 2/2 rate is
  close to the product of the leg rates.
* **The market moved toward the pick** between open and close on 75% of legs (+1.6 points
  on average). This is closing-line value: sharper money later agreed with the engine.
* **The engine bets both sides:** both-Under cards won 72.6%, both-Over 65.2%, mixed 56.4%.

> **Erratum (stage 3):** best-book figures now ignore any book whose opener is more than 3 points from the cross-book median (stale/erroneous numbers). The 55–60% best-book singles ROI moves from +10.5% to +10.2%; the line-shopping card variants are unchanged (65.5%, 66.9%). See [`stage3_corrected.md`](stage3_corrected.md).

## Money: what a hit rate does not tell you

The 60% card is not free. A leg at ~80% is priced around 1.25 (−400). A 1-unit double
pays ~1.65, so the break-even 2/2 rate is about 60%. No historical alternate-line prices
exist, so ROI is reported under explicit pricing scenarios. Each scenario takes the
market's own (no-model) probability at that alternate line and subtracts a margin per leg.

| pricing scenario | 2018-21 v2 | 2021-26 v2 | 2021-26 v3 |
|---|---|---|---|
| alternates priced off the **opening** line, 4.5% margin | +6.0% | **+7.4%** | +3.6% |
| alternates priced off the **closing** line, 4.5% margin | −6.9% | −0.9% | −3.1% |
| opening line, 8% margin | −1.6% | n/a | n/a |

The edge lives at the **opening number**. The engine reads stale openers, and by the close
the market has mostly caught up. To profit you need alternate lines (or bought points)
near the opener, at a fair margin. Shopping across books helps. The CLI prints the
break-even double odds for every card; do not bet below them.

### A second, simpler product: single bets at the main line, real prices

On the 2021-26 test, using the books' actual opening prices:

| engine's two-sided P at the opener | bets | win | ROI at median-book price | ROI at best-book line+price |
|---|---|---|---|---|
| 55–60% (v2) | 3,526 | 56.9% | **+8.5%** | **+10.5%** |
| 60%+ (v2) | 80 | 55.0% | +4.9% | +9.9% |
| 55–60% (v3) | 3,268 | 56.6% | +8.1% | +10.0% |
| 60%+ (v3) | 223 | 58.7% | +12.1% | +12.9% |

The 55–60% bucket clears the −110 break-even (52.4%) with z ≈ 5.4 over 3,526 bets.
This is the cleanest evidence that the engine has a real edge at NCAAB openers. Caveat:
limits on opening lines are low.

## How we got here (development only; every configuration is logged in `ITERATIONS.md`)

| step | what changed | result |
|---|---|---|
| Stage 1 | NBA, Over only, closing line | 0 cards; top-2 card 2/2 ≈ 24–28% |
| it01 | NCAAB opening line, Over **or** Under, ratings | log-loss gain 27×10⁻⁴; buffered cards 57–60% |
| it02–03 | market-memory features, variance model | gain 47×10⁻⁴; cards 62–63% |
| leak fix | tempo centring used future dates; fixed | validation fell to 59.5%, now honest |
| it10 (**v2**) | box-score style matchups (3P, FT, ORB, TOV) | gain 59×10⁻⁴; validation 64.0% |
| it07 / it08 | closing line / half-time line | hit rate buyable, but no edge, so EV < 0 |
| policy | max 15-pt buffer; J = 0.625 (smallest target with a dev lower bound ≥ 60%) | dev 65.7% |
| v3 | recency-weighted model and calibration, J = 0.65 | 2018-21 (dev for v3): 66.0% |
| NBA | the same buffering on closing lines | 61–66% 2/2, but ROI ≈ −6%: no edge |

## Safeguards

* Splits were pre-registered and committed before modelling (`config/stage2.yaml`,
  `config/stage2b.yaml`). Engines were locked and committed before each test
  (`config/stage2_locked.yaml`, `config/stage3_v3_locked.yaml`).
* Leakage tests corrupt future results and lines and require earlier features to be
  bit-identical, for all three markets (`tests/test_ncaab_leakage.py`).
* Calibration is edge-aware, with a conservative bound from a date-clustered sandwich
  covariance. Cards require the **conservative** joint probability to clear the target.
* Bugs found along the way were fixed and disclosed: a leak in the tempo feature, a
  pair-search masking bug, close-price coverage, and a reporting merge bug in the 2b
  script. The 2b script crashed after printing the v2 table; it was re-run and the
  deterministic v2 numbers reproduced exactly.
* Disclosed note: three sample dates from the 2021-26 odds source were fetched only to
  inspect the JSON format before the stage-2b pre-registration. No outcomes were analysed.

## Limitations

* **No historical alternate-line prices.** The hit rates are measured; the ROI figures are scenarios.
* **Opening-line availability and limits:** openers move fast and limits are low; alternate
  lines may not be posted at the opener everywhere.
* **Variance:** single seasons ranged from 57.7% to 72.7%.
* **Edge decay:** the model's information edge halved between the 2011-18 and 2018-21
  periods. A forward test is the only remaining truth (`scripts/grade_ledger.py`).
* No injury or lineup data. NBA is not supported for cards because it has no edge.
