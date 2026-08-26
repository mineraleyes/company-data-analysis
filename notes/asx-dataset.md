# ASX — The dataset

*775 companies in the GICS Materials group, as at 26 August 2026.*

## What arrived

| File | Source | As at | Rows | Cols |
|---|---|---|---|---|
| ASX listed companies | ASX company directory export | 26 Aug 2026 | 1,843 | 5 |

Five columns: **ASX code, company name, GICS industry group, listing date, market cap.** That is the whole file.

## What it can and cannot answer

The TMX exports arrive pre-filtered to mining and carry commodity, property location and value traded. This one does not. Set against the TSX/TSXV work, here is what survives:

| | TSX / TSXV | ASX |
|---|---|---|
| Company count | ✓ | ✓ |
| Market cap, size distribution | ✓ | ✓ |
| Concentration | ✓ | ✓ |
| Listing date, listings by year | ✓ | ✓ |
| Commodity | ✓ | — |
| Where the assets are | ✓ | — |
| Where the company is based | ✓ | — |
| Value traded, turnover | ✓ | — |
| Producer / explorer stage | ✓ | — |
| Price history and returns | ✓ | not yet fetched |

Four of ten. The ASX tabs are shorter than the TSX ones because the data is, not because the work stopped early.

## Who counts as a miner

**There is no mining flag in this file.** The TMX exports come pre-filtered; this one has to be filtered by hand, and GICS industry group is the only classification available. Its **Materials** group is where miners sit — alongside chemicals, packaging and building products. The sub-industry level that would isolate Metals & Mining is not in the export.

Two candidate definitions were tested and they disagree:

| | Companies |
|---|---|
| Materials (GICS) | 775 |
| … and a mining word in the name | 610 |
| … but no mining word in the name | 165 |
| Mining word in the name, not Materials | 41 |

**Name-matching looks tempting and is a trap.** The 165 Materials companies whose names say nothing about mining include:

| | |
|---|---|
| BHP Group | A$344B |
| Newmont Corporation | A$194B |
| Fortescue | A$55B |
| South32 | A$23B |
| Alcoa | A$18B |
| PLS Group | A$17B |
| IGO | A$6B |

Filtering on names discards the seven largest miners on the exchange — A$797B of the A$1,180B total.

**So the population is all 775 Materials companies.** It is a real classification rather than a guess, and both flags are kept in `asx_clean.csv` so it can be narrowed later.

## What that costs

Two distortions, stated rather than corrected:

1. **Materials contains genuine non-miners.** Amcor A$31B, James Hardie A$25B, BlueScope A$14B, Orica A$10B, Dyno Nobel A$7B, Sims A$5B — roughly **A$92B, about 8% of the sector total**. Every market cap figure on the Numbers tab is inflated by that much.
2. **Coal and uranium miners are excluded.** GICS puts them in Energy: Yancoal A$7.9B, Whitehaven Coal A$6.7B. The TMX mining file includes coal and uranium, so **the two populations are not defined the same way** and counts are not strictly comparable.

## Handling notes

- **26 Materials companies show `--` for market cap** — suspended or unpriced lines. Read as blank, never as zero: a zero would drag every median and total it touches.
- **Listing dates are DD/MM/YYYY**, confirmed by day values above 12 in the first field. All 1,843 rows have one.
- **Market cap is Australian dollars and is never converted.** Size bands use the same numeric thresholds as the TSX side so the distributions have the same shape, but a band is A$ here and C$ there.
- **Survivorship, as everywhere.** Only companies listed on 26 August 2026 are in the file, so every historical count is of survivors.
