"""
Fetch price history for every mining company and extract prices at milestones
keyed to each company's own listing date.

    python src/fetch_prices.py              # fetch, then build the extract
    python src/fetch_prices.py --rebuild    # rebuild from cache, no fetching
    python src/fetch_prices.py --limit 25   # trial run on the first 25

In:    data/processed/mining_enriched.csv
Cache: data/raw/price_history.csv       one file, appended as it goes, resumable
Out:   data/processed/price_milestones.csv

Requires: pip install yfinance     Needs internet.

COLUMNS
  px_base   mean adjusted close over the first BASE_DAYS trading days from listing.
            Day zero alone is the least reliable price a junior ever prints, and
            every return divides by this, so a short mean is used instead.
  px_dN     adjusted close on the first trading day at least N days after listing,
            accepted only within TOLERANCE days of the target; blank if none.
  ret_dN    px_dN / px_base - 1.
  split_factor  product of all share splits since listing. Below 1 means a
            consolidation — 0.1 is a 10:1 rollback. Taken from Yahoo's splits
            series, because its Close is already split-adjusted and so hides them.
            Coverage of Canadian junior corporate actions is incomplete, so 1.0
            does not prove none occurred.
  consolidated  split_factor < 1.
  div_total  dividends per share paid since listing.

CAVEATS
  'Listing date' is TMX's, which is not always a first-ever trade: for TSXV
  graduates it is the move to the TSX, and for QT/RTO listings it is a shell
  relisting. 224 TSXV companies have no listing date and cannot be anchored.

  Survivorship: only companies still listed at 30 June 2026 are present. Longer
  milestones are progressively more selected, so long-horizon returns overstate
  the typical outcome.

  Prices are Yahoo Finance via yfinance — free, and unreliable on thin juniors.
  Non-positive adjusted quotes are discarded (see load_cache), so a company that
  paid out more per share than it was trading at loses those milestones rather
  than reporting a negative price.
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "mining_enriched.csv"
CACHE = ROOT / "data" / "raw" / "price_history.csv"
OUT = ROOT / "data" / "processed" / "price_milestones.csv"

# Days since listing.
MILESTONES = [7, 30, 90, 180, 365, 730, 1095, 1825, 2555, 3650, 5475]

# The base every return divides by. Day zero alone is the least reliable price
# a junior ever prints — thin volume, wide spread, often just the placement
# price — so one bad tick would corrupt every return in the row. A mean of the
# first few trading days is far more robust and costs nothing.
BASE_DAYS = 5

# A milestone is filled only if a trading day falls within this many days of
# the target. Beyond that the gap is real (halt, suspension, no trading) and a
# nearby price would misrepresent it.
TOLERANCE = 10


def done_tickers():
    """Tickers already in the cache — including those that returned nothing,
    which are recorded as a single blank row so they aren't retried forever."""
    if not CACHE.exists():
        return set()
    return set(pd.read_csv(CACHE, usecols=["ticker"])["ticker"].unique())


def fetch(tickers, limit=None):
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("pip install yfinance")

    have = done_tickers()
    todo = [t for t in tickers if t not in have]
    if limit:
        todo = todo[:limit]
    print(f"{len(tickers)} tickers · {len(have)} already cached · {len(todo)} to fetch")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    ok = empty = fail = 0

    for i, t in enumerate(todo, 1):
        try:
            # actions=True also returns Dividends and Stock Splits in the same
            # request — free, and the only way to see consolidations, since
            # Yahoo's Close is already split-adjusted
            h = yf.Ticker(t).history(period="max", auto_adjust=False, actions=True)
            if len(h):
                out = pd.DataFrame({
                    "ticker": t,
                    "date": pd.to_datetime(h.index).tz_localize(None).date,
                    # Yahoo returns float noise (0.800000011920929); 6dp is
                    # far more precision than any listed price needs
                    "close": h["Close"].round(6).values,
                    "adj_close": h["Adj Close"].round(6).values,
                    "volume": h["Volume"].fillna(0).astype("int64").values,
                    "split": h["Stock Splits"].values if "Stock Splits" in h else 0.0,
                    "dividend": h["Dividends"].values if "Dividends" in h else 0.0,
                })
                ok += 1
            else:
                # one blank row marks the ticker as attempted and empty
                out = pd.DataFrame([{"ticker": t, "date": None, "close": None,
                                     "adj_close": None, "volume": None}])
                empty += 1
            out.to_csv(CACHE, mode="a", header=not CACHE.exists(), index=False)
        except Exception as e:
            fail += 1
            print(f"  FAIL {t}: {type(e).__name__} {str(e)[:60]}")
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}  ok={ok} empty={empty} fail={fail}")
        time.sleep(0.3)

    print(f"fetched: ok={ok} empty={empty} fail={fail}")


def load_cache():
    """The whole cache, split into one frame per ticker."""
    if not CACHE.exists():
        return {}
    h = pd.read_csv(CACHE, parse_dates=["date"])
    for c in ("split", "dividend"):
        if c not in h.columns:
            h[c] = 0.0
    h = h.dropna(subset=["date", "adj_close"]).sort_values(["ticker", "date"])
    # A share price cannot be zero or negative. Yahoo's Adj Close can be, because
    # it back-adjusts for distributions: when a company returns more capital per
    # share than the share was worth at the time — routine for an explorer that
    # pays out a settlement or spins off an asset — the adjusted series runs
    # through zero. Those quotes are dropped rather than repaired, so the
    # TOLERANCE checks below blank the affected milestones instead of silently
    # substituting a price from a later date.
    bad = (h["adj_close"] <= 0).sum()
    if bad:
        print(f"dropped {bad} non-positive adjusted quotes "
              f"({h.loc[h['adj_close'] <= 0, 'ticker'].nunique()} companies)")
        h = h[h["adj_close"] > 0]
    return {t: g.reset_index(drop=True) for t, g in h.groupby("ticker")}


def milestones_for(hist, listed, attempted):
    """Base price, milestone prices and coverage flags for one company."""
    if hist is None:
        return {"status": "no data" if attempted else "not fetched"}
    h = hist
    rec = {
        "first_price_date": h["date"].iloc[0].date().isoformat(),
        "last_price_date": h["date"].iloc[-1].date().isoformat(),
        "trading_days": len(h),
        "px_latest": round(float(h["adj_close"].iloc[-1]), 4),
    }
    if pd.isna(listed):
        rec["status"] = "no listing date"
        return rec

    start = pd.Timestamp(listed)
    rec["covers_listing"] = bool(h["date"].iloc[0] <= start + pd.Timedelta(days=TOLERANCE))

    # base = mean of the first BASE_DAYS trading days on/after listing
    at_start = h[h["date"] >= start].head(BASE_DAYS)
    if len(at_start) and (at_start["date"].iloc[0] - start).days <= TOLERANCE:
        rec["px_base"] = round(float(at_start["adj_close"].mean()), 4)
        rec["vol_base"] = int(at_start["volume"].mean()) if at_start["volume"].notna().any() else None

    # Corporate actions since listing. Yahoo's Close is already split-adjusted,
    # so a rollback is invisible in the prices — only the splits series shows it.
    after = h[h["date"] >= start]
    splits = after.loc[after["split"].fillna(0) > 0, "split"]
    if len(splits):
        factor = float(splits.prod())
        rec["split_factor"] = round(factor, 4)
        # <1 means shares were consolidated: 0.1 is a 10:1 rollback
        rec["consolidated"] = bool(factor < 1)
        rec["n_splits"] = int(len(splits))
    else:
        rec["split_factor"] = 1.0
        rec["consolidated"] = False
        rec["n_splits"] = 0
    rec["div_total"] = round(float(after["dividend"].fillna(0).sum()), 4)

    filled = 0
    for d in MILESTONES:
        later = h[h["date"] >= start + pd.Timedelta(days=d)]
        if later.empty:
            continue
        row = later.iloc[0]
        if (row["date"] - (start + pd.Timedelta(days=d))).days > TOLERANCE:
            continue
        rec[f"px_d{d}"] = round(float(row["adj_close"]), 4)
        filled += 1

    rec["milestones_filled"] = filled
    rec["status"] = "ok" if "px_base" in rec else "no price near listing"
    return rec


def build(df):
    hists = load_cache()
    attempted = done_tickers()
    rows = []
    for r in df.itertuples(index=False):
        rows.append({
            "co_id": r.co_id, "ticker_full": r.ticker_full, "name": r.name,
            "board": r.board, "commodities": getattr(r, "commodities", None),
            "listing_date": r.listing_date_iso, "mcap_30jun2026": r.mcap,
            **milestones_for(hists.get(r.ticker_full), r.listing_date_iso,
                             r.ticker_full in attempted),
        })
    cols = (["co_id", "ticker_full", "name", "board", "commodities", "listing_date",
             "status", "covers_listing", "first_price_date", "last_price_date",
             "trading_days", "milestones_filled", "consolidated", "split_factor",
             "n_splits", "div_total", "vol_base",
             "mcap_30jun2026", "px_base"]
            + [f"px_d{d}" for d in MILESTONES] + ["px_latest"])
    out = pd.DataFrame(rows)
    return out[[c for c in cols if c in out.columns]]


def add_returns(data):
    """ret_dN = px_dN / px_base - 1, for every milestone and for latest."""
    if "px_base" not in data.columns:
        return data
    base = data["px_base"]
    for col in [f"px_d{d}" for d in MILESTONES if f"px_d{d}" in data.columns] + ["px_latest"]:
        data["ret_" + col[3:]] = (data[col] / base - 1).round(4)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    df = pd.read_csv(SRC)
    if not a.rebuild:
        fetch(df["ticker_full"].tolist(), a.limit)

    data = add_returns(build(df))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUT, index=False)

    print("\n" + data["status"].value_counts().to_string())
    print("\nmilestone fill:")
    for d in MILESTONES:
        c = f"px_d{d}"
        if c in data:
            print(f"  d{d:<5} {int(data[c].notna().sum()):>4}")
    print(f"\n{len(data)} rows -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
