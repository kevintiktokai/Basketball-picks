# OVER ENGINE — Research summary (stage 1)

> **Update — stage 2:** allowing Over *or* Under, moving to NCAA basketball opening lines and buffered (alternate) lines produced two-pick cards that hit **63.9% 2/2 over 664 never-seen cards (2021-26, 95% CI 60.1–67.4%)**. See [`STAGE2_SUMMARY.md`](STAGE2_SUMMARY.md). The stage-1 conclusion below (NBA, Overs, main line) still stands.

**Bottom line: the available evidence does not support a 60% two-pick success
rate. It does not come close.** In 2,896 historical slates across discovery,
validation, final holdout and live-simulated testing, the engine released
**zero** two-pick cards. That is correct behaviour, not a bug: no pair of NBA
Overs ever had a defensible joint probability above ~27%.

Detailed tables: [`development_report.md`](development_report.md) (discovery +
validation) and [`holdout_report.md`](holdout_report.md) (run once, after the
model was locked and committed in `d8e60c3`).

---

## What was built

| module | file |
|---|---|
| A/B data ingestion + cleaning (pinned, checksummed, outcome-blind quality rules) | `data/sources.py`, `data/ingest.py`, `data/SCHEMA.md` |
| C/D/E feature engineering: point-in-time opponent-adjusted scoring ratings, pace × efficiency, four-factor matchups, rest, market tendencies, season phase, trends | `features/pit.py`, `models/total_models.py::add_derived` |
| E/F expected-residual models (mean, ridge, LightGBM, ensemble) + Normal / empirical predictive distributions → P(total > line) with push handling | `models/total_models.py` |
| N calibration (Platt / isotonic / none) fitted walk-forward; conservative Beta lower bound | `calibration/calibrate.py` |
| dependence model (same-slate correlation, Gaussian copula, date-clustered bootstrap) | `backtest/dependence.py` |
| K two-pick selection engine (all pairs, conservative joint ≥ 60%, card / one pick / no bet) | `backtest/cards.py` |
| L/M walk-forward backtest (season refit, calibrator only sees earlier seasons) | `backtest/walkforward.py`, `backtest/engine.py` |
| O reporting: buckets, ROI, drawdown, streaks, Monte Carlo, failure analysis | `backtest/analysis.py`, `scripts/run_research.py`, `scripts/run_holdout.py` |
| P live prediction CLI using the identical engine | `scripts/predict.py`, `models/live.py` |
| leakage + engine tests (17) | `tests/` |

## Data used

* NBA only, 2007-08 → 2026-01-07: 23,575 clean games with a closing total and final score.
* Box-score team stats 2010-11 → 2023-24.
* **Not available:** any non-NBA league's historical totals, opening lines, line
  movement, actual Over prices (−110 assumed), injuries/lineups, travel. Therefore
  no CLV, no league-specific/hierarchical comparison, no roster model.

## Assumptions

* Bets are struck at the stored line (≈ closing line) at 1.909.
* Features use only games on earlier dates (enforced in code and tested by
  corrupting future results and checking past features are bit-identical).
* Periods were pre-registered in the first commit: discovery 2007-08…2016-17,
  validation 2017-18…2020-21, holdout 2021-22…2023-24, live-sim 2024-25…2025-26.
* A pushed leg is **not** a win for the 2/2 metric.

---

## Answers to the final research questions (Section 48)

**Can this system produce two-pick cards with a 2/2 rate ≥ 60% out of sample?**
No. Holdout: **0 cards** in 596 slates (3 seasons). There is no 2/2 rate or
confidence interval to report because nothing qualified; the closest pair on
any holdout slate had a conservative joint probability of **26.9%** (median
24.9%).

**What is the highest 2/2 rate at which the model remains statistically credible?**
About **25–28%**, which is roughly 0.5 × 0.5 plus a small edge. If the engine is
*forced* to take its top-two Overs every night (diagnostic only), the 2/2 rate is:

| stage | cards | 2/2 rate | 95% CI | ROI as a double |
|---|---|---|---|---|
| discovery | 1,008 | 23.8% | 21.3–26.5% | −9.8% |
| validation | 675 | 23.7% | 20.6–27.1% | −11.9% |
| **final holdout** | **524** | **27.7%** | **24.0–31.7%** | +2.7% |
| live-simulated | 240 | 20.8% | 16.2–26.4% | −20.9% |

Restricting to higher-probability pairs raises the rate only on samples too
small to mean anything. For example, holdout pairs with both P ≥ 56% went 5 of 8
(62.5%, CI 31–86%), while development had only 2 such cards. This is the "70%
from 20 cards" trap described in Section 1.19.

**What individual probability did released picks need, and how far from independence were pairs?**
Same-slate NBA totals are essentially independent. Over-outcome correlation was
0.008 in development (CI −0.001…0.017) and 0.007 in the holdout (CI −0.011…0.029).
So P(both) ≈ P(A)·P(B), and each pick needs about **77.4%**. The highest calibrated
P(Over) the model gave any game was **61.0%** in development, **60.1%** in the
holdout and **56.5%** in live-sim. The gap is about 16 percentage points.

**How often does a qualifying card occur?**
Never. Every stage was 0% cards, 0% one-pick and 100% NO BET.

**Historical 2/2 rate in discovery / validation / holdout / live-sim?**
The engine had no cards at any stage. The forced-pair diagnostic is shown above.

**Expected ROI as two singles and as a double?**
Undefined for the engine, since it never bet. Forced doubles are negative in 3 of
4 stages. A Monte Carlo of the forced nightly double over 6 months (development)
gives an expected ROI of −10.7% and an 88% chance of a losing month.

**When should the engine release one pick, and when should it make no bet?**
Release one pick only when the conservative (5% lower-bound) calibrated probability
beats the −110 break-even of 52.38%. That never happened, because the calibration
history around 55–60% is too thin to be confident. Otherwise, NO BET.

**Honest best achievable 2/2 rate — is it worth betting?**
About 25–28% on a forced nightly card. At −110 a double pays 3.64×, so break-even
is 27.5%. The holdout landed right on break-even and every other stage was below
it. **Not worth betting.**

---

## What the backtest showed beyond the card question

* **The closing line is very hard to beat.** Its mean absolute error is about 14
  points. The best model improves log loss over a coin flip by only 9.7×10⁻⁴
  (95% CI 2.9–17.0) in development. In the holdout its log loss was 0.6923 vs a
  coin flip's 0.6931; in live-sim it was *worse* than a coin flip (0.6938).
* **Model ranking (Section 35).** Regularised ridge beats LightGBM and the
  ensemble every time; the tree models add noise. Opponent-adjusted ratings beat
  raw PPG. Box-score pace and four-factor matchup features help slightly in
  development but are unavailable after 2023-24.
* **Section 45 lessons, tested.** Raw recent scoring is a weak signal. Team
  Over/Under trends add nothing (+0.3×10⁻⁴). Blowout risk (|spread| ≥ 10) does not
  change the Over rate (49.5% vs 50.0%). A "3–4 point edge" won 55.2% in
  development (CI 45–65%), so it was not reliable.
* **A lead, not a result.** Projection edges of 3+ points won about 57% in
  development (148 bets) and about 60% in the holdout (189 bets). Holdout Overs
  with calibrated P ≥ 55% went 50–31 (61.7%, CI 50.8–71.6%, +17.8% ROI). But the
  same bucket was only 53.6% on 28 bets in development, live-sim produced just 2
  such bets, and the prices are assumed rather than real. This is a **single-bet
  hypothesis for prospective tracking**, not a validated strategy, and it has
  nothing to do with 60% two-pick cards.
* **Failure analysis (Section 44).** Of the 31 losing holdout Overs with
  P ≥ 55%, 22 (71%) are plain variance (a miss within 1.5 SD), 7 (23%) are
  blowouts and 2 (6%) are model errors. Development showed the same pattern
  (11/1/1 of 13). Pace errors average under 1 possession; the misses come from
  shooting efficiency (about −15 pts/100), which no pre-game feature here predicts.
* **Red team (Section 46).** The edge rests almost entirely on the
  opponent-adjusted rating feature. Permuting it within a season removes about
  half the gain (+5.3×10⁻⁴ worse). That is consistent with a real but weak signal, not
  leakage: the leakage tests pass and the feature uses only past games.

## Recommended threshold

Keep the 60% conservative joint target. On this data it correctly produces
**NO BET** on every NBA slate. Lowering it to "find" cards would mean betting
pairs whose true 2/2 rate is about 25%.

## Recommended improvements (in order of expected value)

1. **Real prices and multiple lines.** Buy historical odds with opening and
   closing totals plus Over prices from several books (e.g. The Odds API
   historical endpoint from 2020). This enables CLV, best-price shopping, and
   betting at the opener, where the market is softer than at the close.
2. **Softer markets.** The NBA closing total is one of the most efficient
   numbers in sports. Lower-tier European and Asian leagues, the original target
   of the brief, may have larger edges, but only paid data exists. Re-run this
   exact pipeline on them before believing any edge.
3. **Injury/lineup feed.** Late scratches are the main information the close
   absorbs that this model lacks.
4. **Forward-test the 3+ point edge single-bet hypothesis** with real prices,
   paper-traded, for at least 300 bets before staking anything.
5. Even with all of the above, expect individual probabilities around 55–58% at
   best. Two-pick cards at 60% would still be out of reach, because that needs
   about 77% per pick from independent games.
