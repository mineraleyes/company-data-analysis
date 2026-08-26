# ASX — The numbers

*775 GICS Materials companies, A$1,180B, as at 26 August 2026. Includes ~A$92B of packaging, steel and chemicals; excludes coal and uranium.*

## Headline

**One company is 29% of the sector. The top ten are 70%.**

| | ASX Materials |
|---|---|
| Companies | 775 |
| Total market cap | A$1,179.6B |
| Median market cap | A$33.4M |
| BHP alone | 29.2% |
| Top 3 | 51.2% |
| Top 10 | 69.8% |

## Concentration

**The ASX is more concentrated than either Canadian board.** TSX mining's top ten are 54.8% of that board; here the top ten are **69.8%**, and three companies — BHP, Newmont, Fortescue — are more than half the sector between them.

That is a different market structure, not a bigger version of the same one. Canada's weight sits in a few dozen mid-to-large producers; Australia's sits in three global majors with a long tail beneath them.

## Size distribution

**43% of the sector is below A$25M, and those 334 companies are worth A$3.9B between them — 0.3% of the total.**

{{chart:asx_size}}

The shape is the same story as the TSXV: a very large number of very small companies, and essentially all the value somewhere else. The difference is that Australia keeps its majors on the same board rather than splitting them across a senior and a venture exchange, so this single distribution spans what takes two boards in Canada.

## Listings by year

**2021 was extraordinary: 106 of the surviving companies listed that year, more than the previous eight years combined.**

{{chart:asx_listings}}

The 2021 spike is the lithium and battery-metals float wave. Whether it was a good vintage is exactly the question the price data would answer, and that has not been fetched.

109 surviving companies listed before 2000 and are not shown; the oldest goes back to 1885.

## What is missing

Everything else. There is no commodity, no project location, no domicile, no value traded and no revenue in this export, so there is no ASX equivalent of:

- the commodity bars
- the assets-by-region bars
- the domicile-versus-operations heatmap
- turnover and the attention ratio
- producer / explorer stage
- the whole post-listing returns analysis

**The gap that would close the most, cheapest:** price history. The file already has a ticker and a listing date for every company, which is exactly what the existing `fetch_prices.py` needs — the codes are stored as `.AX` symbols ready for it. That one run would bring the milestone-return analysis across, and it is the most interesting part of the TSX work. Nothing else here is a one-script job.

## Caveats

- **Population is GICS Materials, not mining** — ~A$92B of non-miners in, coal and uranium out. Not comparable to the TMX mining population on a like-for-like basis.
- **26 companies have no market cap** — suspended lines, excluded from totals and medians rather than counted as zero.
- **Australian dollars, never converted.** Do not read an A$ band as equal to the C$ band with the same label.
- **Survivorship.** Every listing-year count is of companies that are still listed today, so early years are undercounted by everything that has since failed or been acquired.
- **One date only.** A single snapshot, so nothing here is a trend.
