# Paid-for odds caches (OddsPapi)

The raw OddsPapi caches under `data/raw/` are not tracked (`.gitignore`), but they cost monthly
request allowance to rebuild, so compressed copies are kept here. They hold prices only.

| file | contents | requests |
|---|---|---|
| `oddspapi_euro_138_141.tar.xz` | EuroLeague (138) and EuroCup (141) fixtures and slimmed pre-game totals histories | a month's allowance or more |
| `oddspapi_nba_props.tar.xz` | NBA (132) player-points price histories, 192 games, and the player-name map | 220 |

Restore into a fresh checkout (the scripts then read them as cache and request nothing again):

```
tar -xJf data/archive/oddspapi_euro_138_141.tar.xz -C data/raw/oddspapi/
mkdir -p data/raw/oddspapi/132 && tar -xJf data/archive/oddspapi_nba_props.tar.xz -C data/raw/oddspapi/132/
```
