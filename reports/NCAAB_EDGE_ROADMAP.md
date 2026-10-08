# NCAAB edge roadmap: what pushes the edge further, and what we've already tested

## 1. Where the edge comes from today

* **The engine beats the opening total.** On its bets the line then moved toward our side
  67–80% of the time, by +1.1 to +2.0 points on average. The edge is information the opener
  has not priced yet: team ratings (efficiency, tempo) set against the opener.
* **It is calibrated and stable.** 10,074 out-of-sample singles at P ≥ 55% won 57.2%; the engine
  predicted 57.3%. ROI was +9.2% at −110 and +9.9% at the best real price (2021-26)
  ([`bet_diagnostics.md`](bet_diagnostics.md)).
* **The conference season is its core.** About 70% of bets, +9.4% ROI in both 2011-18 and
  2018-21 ([`ncaab_stage_map.md`](ncaab_stage_map.md)).

## 2. Stage playbook (2011-21; 2021-26 kept sealed)

| stage | priced games / season | total vs opener | engine ROI 2011-18 / 2018-21 | what it means |
|---|---|---|---|---|
| non-conference, campus | ~530 | +0.6 (Over 50.6%) | +13.5% / +0.4% | least reliable stage for the engine in the later era |
| non-conference, neutral (events) | ~130 | −1.4 (Over 46.1%) | +9.6% / +10.7% | Unders; the engine already leans Under here (77% of bets) |
| conference regular season | ~2,030 | +1.0 (Over 51.0%, OT 6.8%) | +9.4% / +9.4% | the core |
| conference tournaments | ~180 | −0.5 (Over 47.2%) | +10.4% / +12.1% | the engine's forecast runs 1–2 pts high here |
| NCAA tournament | ~60 | −0.2 (Over 48.6%) | +17.5% / +73.6% (89 bets) | sharpest openers of any stage; too few bets to judge |
| NIT / CBI / CIT | ~56 | +3.5 (Over 56.3%, OT 11.6%) | +10.6% / +23.5% | Overs; softest openers (largest line moves) |

Every stage was profitable for the engine, but building explicit stage terms into the model
did not survive the later era (study 2). For now the stage rules are: one engine everywhere,
with conference tournaments (Unders) and the minor postseason (Overs) on a watch list for
the forward season.

## 3. What has been tested (each one pre-registered before it was fitted)

| study | idea | result |
|---|---|---|
| 1 | side-aware calibration (overtime skews totals) | better probabilities in every era, not better bets → not adopted |
| 2 | stage indicators, tempo and efficiency mismatch, fatigue | better in 2011-18, worse in 2018-21 (matched ROI 5.1–5.5% vs 8.2%) → not adopted |
| 3 | ratings on shooting-luck-neutral points (league-average 3P% and FT%) | matched ROI lower in both eras (10.1% vs 10.2%, 6.8% vs 8.2%) → not adopted: the engine's ratings, and the market, already discount shooting luck |
| 4 | roster continuity and transfers (player box scores) | matched ROI up in both eras (+0.6, +0.8 pts) and log loss better in 2018-21, but 2011-18 log loss was 0.04×10⁻⁴ worse, so the strict rule says no. It matters most in the transfer-portal era, so it is the best candidate for a forward shadow test |
| 5 | learn from the closing line (train on close − open, or add the predicted move) | probabilities worse (close target) or unchanged (move feature); matched ROI not better → not adopted. The engine's outcome model already carries what the market's move would teach it |
| 6 | the home floor's "park factor" (does it run over or under its closing totals?), and high-altitude venues; from the loss autopsy | **passed 2011-21** (matched ROI 12.0% vs 10.3% and 10.5% vs 8.2%, log loss better in both eras), then **failed its one-time 2021-26 check**: log loss slightly better, but straight bets at matched volume 7.9% vs 8.3% (-110) and 9.8% vs 10.3% (real prices). The 2.5+ card and the main-line double did better with it (ROI 24.0% vs 19.9%, 33.4% vs 29.0%), which the rule does not count → not adopted; forward shadow candidate for cards ([`study6_venue.md`](study6_venue.md), [`loss_autopsy.md`](loss_autopsy.md)) |
| staking | size by the engine's edge (1/8 Kelly, fixed bankroll) | +11.7% per unit staked vs +9.5% flat (2011-21); +11.5% vs +10.3% (2021-26); drawdown no larger → **adopted as the staking rule** |

The lesson: on the data we already have, model tweaks are close to exhausted. Six studies and nine
candidates each moved the backtest by a fraction of a point to two points, and none held up on the
seasons it had not seen (continuity and the venue factor came closest). The loss autopsy says why: won and
lost bets looked the same when they were placed (+4.7 vs +4.6 points of expected edge), and 97% of losses
were driven mainly by shooting or pace swings after tip-off. The remaining gains are in execution and in
information the engine does not yet have.

## 4. Levers, ranked by expected value

1. **Execution (proven).**
   * Bet at the opener, fast: the edge is the move that follows.
   * Shop the number and the price: the best of 6+ books instead of −110 added
     +1.5 pts of ROI in 2021-26.
   * Stake by edge (1/8 Kelly): +1.2 to +2.2 pts per unit staked. Now in the CLI
     (`--product singles`).
2. **New information.**
   * Injuries and availability: a missing star moves a total by several points. Historically
     we can see absences only after the fact, from box scores. Live use needs a news or lineup feed.
   * Referees: crews differ in fouls called, and so in free throws and totals. ESPN lists
     officials on game day, after the opener, so this would be a late-bet product judged
     against the closing line.
   * Roster continuity (study 4): forward shadow test.
   * Venue park factor (study 6): forward shadow test for the 2.5+ card. Its information is real in all
     three eras (the locked engine's bets against a strong venue factor won 55.2% and 53.9%, against
     57-59% for the rest), but as a model feature it did not improve the straight bets on 2021-26.
   * Before an Over, check for a missing starter: Overs placed right after a 25+ minute player sat
     won about 2.5-3 points less often (2011-21; not significant, not a rule).
3. **New markets.**
   * First-half totals and team totals are thinner and softer markets. They need SBR
     first-half lines; ESPN has scores by half for 2023 onward.
4. **More volume.**
   * The engine skips each team's first two games (both teams need 3+ games). Continuity data
     could unlock the opening weeks, when markets are least settled.

## 5. The forward test: 2026-27 is the real judge

* The season starts in early November. Run daily:
  `python scripts/predict_cards.py --date YYYY-MM-DD --update --product singles --record`,
  plus the target card (`--product target --record`).
* Grade with `python scripts/grade_ledger.py`.
* Checkpoints: about 500 singles (mid-December) and season end. The locked engine stays the
  engine until a shadow arm beats it there.

## 6. Then the other leagues, each with its own rules

* **NBA:** no reliable edge without injury and rest information (load management drives NBA
  totals).
* **WNBA:** no edge ([`stage3_wnba_test.md`](stage3_wnba_test.md)).
* **Europe:** a different kind of edge. It is market-based: soft books lag Pinnacle, rather than
  a team-ratings model beating the opener. Holdout in November.
