# Stage 3 — two-pick cards at combined odds ≥ 2.5 (legs like 1.62 × 1.57)

## The arithmetic first

A double at combined odds **O** breaks even when both legs win **1/O** of the time.

| combined odds | break-even 2/2 rate | ROI if 2/2 = 47% | ROI if 2/2 = 60% |
|---|---|---|---|
| 2.50 | 40.0% | +17.5% | +50% |
| 2.60 | 38.5% | +22.2% | +56% |
| 3.64 (two −110 legs) | 27.5% | +71% | +118% |

A 60% hit rate at 2.5 would be a +50% return on every card; no betting market allows
that for long. The engine therefore targets what can be **proved**: cards at ≥ 2.5 that win
**clearly more often than break-even**, at real (or explicitly stated) prices.

## What was built

* **Leg ladders:** for each game and side, the best book's opening number at its real
  price, plus alternate lines from −6 to +15 points priced from the market's own
  probability with a stated margin.
* **Book-outlier guard:** a book's opener more than 3 points from the cross-book median
  is treated as a data error and never used for line shopping. This was found by the
  live smoke test after the NBA test had run; see "Corrections" below.
* **Card rule (locked before testing):** two legs from different games, combined odds
  ≥ 2.5, legs 1.40–1.90. Choose the pair with the highest *conservative* chance that
  both win; release only if the conservative expected value is positive.
* **Second product:** the main-line double, two legs at the best book's real opening
  price (≈ 3.64 combined), with no modelled prices at all.
* **NBA engine:** same pipeline on NBA opening lines (6 books, real prices, 2021-26).
* **Feature store + model cache:** completed seasons are computed once and reused.

## Results

### NCAA basketball — target card (≈ 2.55 combined, legs ≈ 1.6)

| period | status | cards | both won | combined odds | break-even | ROI per card (95% CI) |
|---|---|---|---|---|---|---|
| 2011-18 | development | 870 | 45.9% | 2.56 | 39.2% | +16% (8–25%) |
| 2018-21 | development | 363 | 46.3% | 2.55 | 39.4% | +17% (4–30%) |
| **2021-26** | re-analysis (policy locked first) | **664** | **46.8%** | **2.57** | **39.1%** | **+20% (10–30%)** |
| 2021-26, alternates priced off the *closing* line | stress test | 664 | 46.8% | 2.35 | 43.5% | +9% (0–18%) |
| 2021-26, alternate margin 8% | sensitivity | 654 | 43.0% | 2.70 | 37.5% | +15% (5–26%) |
| 2021-26, alternates shopped at the best book | variant | 664 | 48.3% | 2.52 | 39.7% | +22% (13–31%) |

The model's predicted hit rate matched reality in every period (≈ 45–47%). Each
2021-26 season beat break-even except 2024-25, which was close to flat. The longest
losing run was 8 cards; the maximum drawdown was ~13 units at 1 unit per card.

### NCAA basketball — main-line double (real prices, no modelled prices)

| period | cards | both won | combined odds | break-even | ROI (95% CI) |
|---|---|---|---|---|---|
| 2021-26 (re-analysis) | 652 | 35.6% | 3.64 | 27.5% | +29% (16–43%) |

### NBA — opening lines (2023-26 was the one-time test; corrected figures shown)

| product | cards | both won | odds | break-even | ROI (95% CI) |
|---|---|---|---|---|---|
| target card | 543 | 34.6% | 3.08 | 33.3% | +4% (−8 to +16%) |
| main-line double | 490 | 28.2% | 3.64 | 27.5% | +2% (−14 to +16%) |
| singles, model P 55–60%, best book | 275 bets | 60.2% | ~1.91 | 52.4% | +15% |

The NBA model carries information at the opener: log-loss gain +24×10⁻⁴, and legs
moved our way 60% of the time. But none of the NBA **card** products beats break-even
with confidence: NBA openers are sharp. **Not recommended for cards.** Higher-confidence
NBA singles are worth tracking in the forward test.

## Corrections (disclosed)

The best-book selection originally took the best opener across books with no sanity
check. Running the live tool on a past date surfaced a 145.5 opener at one book when the
others opened 166.5. Applying the 3-point guard:

* NCAAB target card: 47.0% / +20.6% → **46.8% / +19.9%** (essentially unchanged).
* NCAAB main-line double: 38.3% / +38.7% → **35.6% / +29.0%**.
* NBA main-line double: 30.6% / +10.8% → **28.2% / +1.6%**. The NBA "edge" there was mostly bad data.
* Stage-2b best-book singles (55–60%): +10.5% → +10.2%; the line-shopping card variants
  were unchanged (65.5% and 66.9%).

The original reports are kept as they were (`stage3_nba_test.md`,
`stage3_ncaab_reanalysis.md`); the corrected figures are in `stage3_corrected.md`.
They are labelled post-test, because the originals had been seen.

## How to use it

```bash
python scripts/predict_cards.py --date 2026-11-20 --update --record            # target card (default)
python scripts/predict_cards.py --date 2026-11-20 --product main --record      # main-line double
python scripts/grade_ledger.py                                                 # forward record + ROI
```

For each leg the card shows the line to bet, the price (real for main lines, an
*estimate* for alternates), the model and conservative probabilities, and the minimum
acceptable price. It also prints the combined odds, the chance both win, break-even and
expected return. Take a card only at or above the minimum prices, and as close to the
opening line as possible.

## Honest bottom line

* **Yes:** the engine produces two-leg NCAAB cards at combined odds ≥ 2.5 that won ~47%
  against ~39% break-even, across development and the 2021-26 re-analysis. The model's
  stated probabilities matched what happened.
* **No:** 60% at 2.5 is not achievable. Expect to lose more cards than you win, and
  expect long losing runs (8+).
* **Conditions:** the edge is at the opening number; profit needs alternate lines priced
  near the opener at a modest margin. NBA openers are too efficient for this engine.
* **Next proof:** the 2026-27 forward ledger, the only data nobody has seen.
