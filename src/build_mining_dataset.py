"""
Build the cleaned TSX/TSXV mining dataset from the TMX monthly issuer list.

Input:  data/raw/tmx_issuers_2026-06-30.xlsx
Output: data/processed/mining_clean.csv

The two sheets have different column sets, so they are normalised to a common
schema before concatenation. Column names in the source contain embedded
newlines and carry the data date, so they are matched by prefix where possible.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "tmx_issuers_2026-06-30.xlsx"
OUT = ROOT / "data" / "processed" / "mining_clean.csv"

HEADER_ROW = 9  # real header is row 10; rows 1-9 are disclaimer + subtotals
DATA_YEAR = 2026


def _find(cols, *, startswith=None, contains=None):
    """Locate a column by prefix or substring, tolerating embedded newlines."""
    for c in cols:
        flat = " ".join(str(c).split())
        if startswith and flat.startswith(startswith):
            return c
        if contains and contains in flat:
            return c
    raise KeyError(f"no column matching startswith={startswith!r} contains={contains!r}")


def load_board(sheet_name, board):
    df = pd.read_excel(SRC, sheet_name=sheet_name, skiprows=HEADER_ROW)
    mining = df[df["Sector"] == "Mining"].copy()

    cols = mining.columns
    rename = {
        _find(cols, startswith="Market Cap"): "mcap",
        _find(cols, startswith="O/S Shares"): "shares",
        _find(cols, startswith="Volume"): "vol_ytd",
        _find(cols, startswith="Value"): "value_ytd",
        _find(cols, contains="Trades"): "trades_ytd",
        _find(cols, contains="Month"): "months",
        _find(cols, startswith="Root"): "ticker",
        _find(cols, startswith="HQ Location"): "hq_location",
        _find(cols, startswith="HQ Region"): "hq_region",
    }
    mining = mining.rename(columns=rename)
    mining["board"] = board

    # Derived fields
    mining["turnover"] = mining["value_ytd"] / mining["mcap"]
    mining["px"] = mining["mcap"] / mining["shares"]
    mining["avg_trade"] = mining["value_ytd"] / mining["trades_ytd"]

    ldate = pd.to_numeric(mining["Listing Date"], errors="coerce")
    mining["lyear"] = (ldate // 10000).where(ldate > 19000000)
    mining["yrs"] = DATA_YEAR - mining["lyear"]

    return mining


def main():
    tsx = load_board("TSX Issuers June 2026", "TSX")
    tsxv = load_board("TSXV Issuers June 2026", "TSXV")
    both = pd.concat([tsx, tsxv], ignore_index=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    both.to_csv(OUT, index=False)

    print(f"TSX  mining: {len(tsx):>5}  C${tsx['mcap'].sum()/1e9:>8.1f}B")
    print(f"TSXV mining: {len(tsxv):>5}  C${tsxv['mcap'].sum()/1e9:>8.1f}B")
    print(f"combined:    {len(both):>5}  C${both['mcap'].sum()/1e9:>8.1f}B")
    print(f"written -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
