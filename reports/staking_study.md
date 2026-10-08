# Staking study — how much to put on each NCAAB single (locked v3 engine)

_A decision layer on top of the unchanged engine. Bets: calibrated P >= 55% at the opener. Chosen on 2011-21 at -110; 2021-26 at the best real price is a check, not used for the choice. Fixed 100-unit bankroll (1 unit = 1%), no compounding; Kelly stakes capped at 25% of the bankroll per day._

## Win rate and ROI by the engine's probability

| period | P | bets | win | predicted | ROI flat |
|---|---|---|---|---|---|
| 2011-21 (choose here) | 55%-57% | 3582 | 0.560 | 0.559 | 0.068 |
| 2011-21 (choose here) | 57%-59% | 1836 | 0.572 | 0.579 | 0.092 |
| 2011-21 (choose here) | 59%-62% | 965 | 0.617 | 0.602 | 0.176 |
| 2011-21 (choose here) | 62%-100% | 274 | 0.627 | 0.638 | 0.195 |
| 2021-26 (check, real prices) | 55%-57% | 2132 | 0.570 | 0.559 | 0.085 |
| 2021-26 (check, real prices) | 57%-59% | 935 | 0.597 | 0.579 | 0.136 |
| 2021-26 (check, real prices) | 59%-62% | 372 | 0.593 | 0.600 | 0.130 |
| 2021-26 (check, real prices) | 62%-100% | 71 | 0.543 | 0.634 | 0.035 |

## Staking schemes

| period | scheme | bets | avg stake (units) | staked | profit (units) | ROI per unit staked | max drawdown (units) | profit / max drawdown |
|---|---|---|---|---|---|---|---|---|
| 2011-21 (choose here) | flat 1u | 6657 | 1.000 | 6657.000 | 635.273 | 0.095 | 29.091 | 21.837 |
| 2011-21 (choose here) | tiered 1-2.5u | 6657 | 1.345 | 8951.000 | 969.000 | 0.108 | 39.591 | 24.475 |
| 2011-21 (choose here) | Kelly 1/8 | 6657 | 1.085 | 7221.248 | 843.259 | 0.117 | 27.640 | 30.509 |
| 2011-21 (choose here) | Kelly 1/4 | 6657 | 1.749 | 11642.134 | 1446.334 | 0.124 | 39.272 | 36.828 |
| 2021-26 (check, real prices) | flat 1u | 3510 | 1.000 | 3510.000 | 359.966 | 0.103 | 29.915 | 12.033 |
| 2021-26 (check, real prices) | tiered 1-2.5u | 3510 | 1.270 | 4456.000 | 475.945 | 0.107 | 32.724 | 14.544 |
| 2021-26 (check, real prices) | Kelly 1/8 | 3510 | 0.979 | 3437.242 | 393.963 | 0.115 | 28.891 | 13.636 |
| 2021-26 (check, real prices) | Kelly 1/4 | 3510 | 1.488 | 5224.043 | 617.210 | 0.118 | 70.399 | 8.767 |

Tiers: P >= 55%: 1.0u, P >= 57%: 1.5u, P >= 59%: 2.0u, P >= 62%: 2.5u.
