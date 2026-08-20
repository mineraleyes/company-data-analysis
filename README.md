# TSX / TSXV Mining Analysis

Analysis of mining companies listed on the Toronto Stock Exchange (TSX) and
TSX Venture Exchange (TSXV).

## Status

Stage 1 — data exploration. One-off analysis, no recurring pipeline.

**Target output:** a single HTML document to read through — between a dashboard
and a slide deck. Sectioned and scrollable, charts inline, not a presentation
deck and not a live tool. The `notes/` markdown files are the source content
for it.

## Data

Source: TMX monthly issuer list, data as at 30-June-2026.

| Board | Companies | Mining |
|---|---|---|
| TSX  | 2,258 | 183 |
| TSXV | 1,503 | 896 |

Mining universe: **1,079 companies**, C$1,135.6B combined market cap.

## Layout

    data/raw/         source files as received — do not edit
    data/processed/   cleaned / derived datasets
    notes/            exploration notes, findings
    outputs/          charts, reports, deliverables
    src/              scripts and notebooks

## Key files

- `notes/stage1-dataset.md` — what the dataset is, columns, coverage, what's missing
- `notes/stage1-numbers.md` — the mining summary figures
- `notes/stage2.md` — candidate external datasets, open questions
- `data/processed/mining_clean.csv` — 1,079 mining rows, both boards, with derived columns

## Derived columns in mining_clean.csv

| Column | Definition |
|---|---|
| `board` | TSX or TSXV |
| `turnover` | H1 2026 value traded / market cap |
| `px` | implied share price = market cap / shares outstanding |
| `lyear` | listing year |
| `yrs` | years listed as at 2026 |
| `avg_trade` | value traded / number of trades |

## Known data limits

- No commodity field — 641 of 1,079 company names contain no commodity word
- Single snapshot — no price history, returns or volatility
- No financials — cannot distinguish funded from failing
- Live listings only — survivorship-biased
- 224 TSXV miners (25%) have no listing date
