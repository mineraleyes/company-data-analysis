"""
Classify each mining company as producer or explorer, using revenue and the
company's own business description from Yahoo Finance.

    python src/fetch_fundamentals.py            # fetch, then classify
    python src/fetch_fundamentals.py --rebuild  # reclassify from cache only
    python src/fetch_fundamentals.py --limit 25 # trial run

In:     data/processed/mining_enriched.csv
Cache:  data/raw/fundamentals.csv                one row per ticker, resumable
Out:    data/processed/mining_enriched.csv       updated in place, new columns
        data/raw/enrichment/01_stage.csv         so a re-run of the enrich
                                                 script keeps the stage column

WHY REVENUE
A miner with revenue is producing something; one without is not. That is the
only part of "stage" that is a fact rather than a judgement, so it is decided
first and everything else is decided around it.

WHY THERE IS NO DEVELOPER BUCKET
Developer is a real stage — a proven deposit being permitted and built — but it
is not visible here. Across all 1,079 Yahoo business summaries the word
"feasibility" appears once, "construction" three times. The summaries say what a
company explores for, not how far along it is, so a developer bucket built from
them would be a handful of lucky keyword hits presented as a count. Everything
without revenue is therefore an explorer, and market cap is the honest way to
separate the advanced ones from the shells.

Requires: pip install yfinance     Needs internet.
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "mining_enriched.csv"
CACHE = ROOT / "data" / "raw" / "fundamentals.csv"
ENRICH_OUT = ROOT / "data" / "raw" / "enrichment" / "01_stage.csv"

# Below this, "revenue" is interest on the treasury, not production.
REVENUE_FLOOR = 1_000_000

# TMX lists the root ticker for a dual-class issuer; Yahoo only has the classes.
ALIASES = {"TECK.TO": "TECK-B.TO"}

PRODUCER_TERMS = [
    "produces", "producing", "production of", "operates the",
    "commercial production", "mines and", "operating mine",
]


def fetch(tickers, limit=None):
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("pip install yfinance")

    have = set()
    if CACHE.exists():
        c = pd.read_csv(CACHE).drop_duplicates(subset="ticker", keep="last")
        # A row with neither a summary nor a revenue figure is a failed fetch,
        # not a company with nothing to say. Caching the failure would make it
        # permanent, so those tickers go back on the list.
        have = set(c[c["summary"].notna() | c["revenue"].notna()]["ticker"])
    todo = [t for t in tickers if t not in have]
    if limit:
        todo = todo[:limit]
    print(f"{len(tickers)} tickers · {len(have)} cached · {len(todo)} to fetch")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    ok = fail = 0

    for i, t in enumerate(todo, 1):
        rec = {"ticker": t, "revenue": None, "revenue_year": None,
               "summary": None, "industry": None}
        try:
            tk = yf.Ticker(ALIASES.get(t, t))

            stmt = tk.income_stmt
            if stmt is not None and not stmt.empty:
                for row in ("Total Revenue", "Operating Revenue"):
                    if row in stmt.index:
                        vals = stmt.loc[row].dropna()
                        if len(vals):
                            rec["revenue"] = float(vals.iloc[0])
                            rec["revenue_year"] = str(vals.index[0])[:4]
                            break

            info = tk.info or {}
            rec["summary"] = (info.get("longBusinessSummary") or "").replace("\n", " ")
            rec["industry"] = info.get("industry")
            if rec["revenue"] is None and info.get("totalRevenue"):
                rec["revenue"] = float(info["totalRevenue"])
                rec["revenue_year"] = "info"
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  FAIL {t}: {type(e).__name__} {str(e)[:60]}")

        pd.DataFrame([rec]).to_csv(
            CACHE, mode="a", header=not CACHE.exists(), index=False)
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}  ok={ok} fail={fail}")
        time.sleep(0.4)

    print(f"fetched: ok={ok} fail={fail}")


def classify(row, fund):
    """Return (stage, basis). Basis records what actually decided it."""
    if row.get("shell_like") is True:
        return "Shell", "no commodity or property disclosed"
    if row.get("is_royalty_streamer") is True:
        return "Royalty/Streamer", "TMX royalty flag"

    rev = fund.get("revenue")
    if pd.notna(rev) and rev >= REVENUE_FLOOR:
        return "Producer", "revenue"

    # pd.isna, not `or ""`. A missing summary arrives as float nan, which is
    # truthy, so `or ""` never fires and the text becomes the literal string
    # "nan" — every blank row then fell through to Explorer. That is how Teck,
    # a producer with no Yahoo record under its root ticker, became an explorer.
    raw = fund.get("summary")
    text = "" if raw is None or pd.isna(raw) else str(raw).lower()
    if text:
        if any(k in text for k in PRODUCER_TERMS) and pd.notna(rev) and rev > 0:
            return "Producer", "summary + revenue"
        return "Explorer", "summary"

    if pd.notna(rev) and rev > 0:
        return "Producer", "revenue below floor"
    # No revenue figure and no description means nothing is known. Calling
    # these "Explorer" because most juniors are explorers would invent a
    # classification for the majority of the file.
    return "Unknown", "no data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    df = pd.read_csv(SRC)
    if not a.rebuild:
        fetch(df["ticker_full"].tolist(), a.limit)

    fund = {}
    if CACHE.exists():
        f = pd.read_csv(CACHE).drop_duplicates(subset="ticker", keep="last")
        fund = f.set_index("ticker").to_dict("index")

    stages, bases, revs = [], [], []
    for r in df.to_dict("records"):
        st, basis = classify(r, fund.get(r["ticker_full"], {}))
        stages.append(st)
        bases.append(basis)
        revs.append(fund.get(r["ticker_full"], {}).get("revenue"))

    df["stage"] = stages
    df["stage_basis"] = bases
    df["revenue"] = revs

    # Not a test — a list to eyeball. A distribution is not proof of production.
    # On the TSXV a payout is as often a return of capital, a spin-out of an
    # asset, or the proceeds of a settlement: Gold Reserve has never operated a
    # mine and paid its shareholders out of a Venezuelan arbitration award.
    prices = ROOT / "data" / "processed" / "price_milestones.csv"
    if prices.exists():
        p = pd.read_csv(prices)[["co_id", "div_total"]]
        chk = df.merge(p, on="co_id", how="left")
        # Royalty companies are paid out of someone else's mine, so they are
        # expected here and only the rest are worth looking at.
        expected = ["Producer", "Royalty/Streamer"]
        odd = chk[(chk["div_total"].fillna(0) > 0) & (~chk["stage"].isin(expected))]
        if len(odd):
            print(f"\n{len(odd)} non-producers made a distribution "
                  f"(return of capital, spin-out or settlement — not an error):")
            print(odd[["ticker_full", "name", "stage", "div_total"]]
                  .head(15).to_string(index=False))

    df.to_csv(SRC, index=False)

    ENRICH_OUT.parent.mkdir(parents=True, exist_ok=True)
    df[["ticker_full", "stage"]].to_csv(ENRICH_OUT, index=False)

    print("\n" + df["stage"].value_counts().to_string())
    print("\nbasis:")
    print(df["stage_basis"].value_counts().to_string())
    print(f"\nupdated -> {SRC.relative_to(ROOT)}")
    print(f"stage also written to {ENRICH_OUT.relative_to(ROOT)} so re-running "
          f"enrich_mining_dataset.py keeps it")


if __name__ == "__main__":
    main()
