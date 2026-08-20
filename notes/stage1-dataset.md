# Stage 1 — The dataset

*TMX data. One-off analysis.*

## What it is

**Two TMX files, joined on `Co_ID`. The issuer list gives size and trading; the mining properties list gives commodity and asset location.**

| File | Source | As at | Rows | Cols | Mining |
|---|---|---|---|---|---|
| TSX/TSXV issuer list | [Current Market Statistics → Issuer Lists](https://www.tsx.com/en/listings/current-market-statistics) | 30 Jun 2026 | 3,761 | 35 / 32 | 1,079 |
| Mining companies list | [Sector Profiles → Mining](https://www.tsx.com/en/listings/listing-with-us/sector-and-product-profiles/mining) | 31 Jul 2026 | 1,074 | 53 / 52 | 1,074 |

Both are published by TMX and free. The issuer-list page also hosts **archived monthly versions**, which is the source for any historical work (see Stage 2).

The issuer list covers all listed companies with mining flagged by a `Sector` column. The mining list is pre-filtered to miners and adds the columns that matter most.

**1,069 of 1,079 match across the two files.** The 10 that don't are companies that left the market between June and July.

**Working universe: 1,079 companies.**

## What the columns describe

### From the issuer list

**Identity** — `Co_ID`, `Name`, `Root Ticker`, `Exchange`. ID schemes differ between boards, so `Co_ID` is the only reliable cross-file key; ticker is not stable across name changes.

**Size** — `Market Cap (C$)` and `O/S Shares`.

**Location of the office** — `HQ Location` (province, US state, or country mixed in one column), `HQ Region`.

**Listing history** — `Listing Type` (IPO, RTO, Qualifying Transaction, TSXV graduation, TSX comedown) and `Listing Date`.

**Status flags** (presence-only) — `Interlisted`, `Trading on OTC`, `TSX Venture Grad`, `CPC / Former CPC`, index membership, `TSX30` / `Venture 50`.

**Trading activity** — `Volume`, `Value (C$)`, `Number of Trades`, YTD, plus months traded. Aggregates only.

### From the mining properties list

**20 commodity flags** — Gold, Silver, Copper, Nickel, Diamond, Molybdenum, Platinum/PGM, Iron, Lead, Zinc, Rare Earths, Potash, Lithium, Uranium, Coal, Tungsten, Oil and Gas, plus `Base & Precious Metals`, `Other Properties`, and `Royalty Streaming`. Multi-flag — most companies carry more than one.

**8 property region columns** — Africa, Asia, Aus/NZ/PNG, Canada, Latin America, Other, UK/Europe, USA. These hold **jurisdiction text**, not flags: `"NU, ON"`, `"Cote D'Ivoire, Ethopia, Mali"`, `"ID, NV"`. 128 distinct jurisdictions.

**`Royalty Streaming`** doubles as a business-model flag — royalty and streaming companies own no mines and have completely different economics.

## Coverage

| | Companies | Share |
|---|---|---|
| Named commodity | 987 | 91% |
| Disclosed property location | 1,009 | 94% |
| Neither commodity nor property | 51 | 5% |

| Field | TSX | TSXV |
|---|---|---|
| Listing Date | 183/183 | 672/896 (75%) |
| Listing Type | 161/183 (88%) | 656/896 (73%) |
| Trading data | 182/183 | 877/896 |

Listing history remains the weak spot, and only on the TSXV.

## What we can derive

| Metric | Formula |
|---|---|
| Turnover | Value YTD ÷ Market Cap |
| Attention ratio | share of sector trading value ÷ share of sector market cap |
| Implied share price | Market Cap ÷ Shares |
| Average trade size | Value YTD ÷ Number of Trades |
| Commodity set | fixed-order list of all commodities held |
| Property regions / jurisdictions | fixed-order list of where the assets are |
| HQ matches assets | does the company hold property where it is based |
| Size band, days listed, dormancy | — |

Commodity is deliberately **not** collapsed to a single "primary" — that needs revenue data this file doesn't have. Instead there are two views: `commodities` as a fixed-order set that partitions the universe, and 20 `comm_*` booleans that overlap, so "any gold exposure" is answerable.

## What isn't in it

1. **Time series** — single snapshot. No returns, volatility or history.
2. **Financials** — no cash, burn or debt. Can't distinguish funded from failing.
3. **Stage** — no explorer / developer / producer split. The most valuable remaining gap.
4. **Corporate actions** — no financings, placements or dilution history.
5. **Price** — no OHLC, spread or 52-week range.
6. **Delisted issuers** — live listings only, so survivorship-biased.
7. **Project detail** — jurisdictions but no named projects, resources, grades or tonnages.

*Commodity and asset location are no longer gaps — the mining properties file closed both.*

## Handling notes

- **The two files are a month apart.** Only commodity and property columns are joined across. Market cap, shares and trading stay on the 30-June basis so nothing mixes dates.
- **Jurisdiction text mixes separators** in source — commas within a region, separate columns between. Normalised to one pipe-separated list.
- **`CA` in a jurisdiction list is California**, not Canada. Region attribution comes from the source column.
- `HQ Location` mixes province, state and country codes.
- 19 TSXV nulls in trading data — not zeros.
