"""
Fetch price history for every ASX mining company and extract prices at
milestones keyed to each company's own listing date.

    python src/fetch_asx_prices.py              # fetch, then build the extract
    python src/fetch_asx_prices.py --rebuild    # rebuild from cache, no fetching
    python src/fetch_asx_prices.py --limit 25   # trial run on the first 25
    python src/fetch_asx_prices.py --all        # all 775 fetched, not just miners

In:    data/processed/asx_enriched.csv
Cache: data/raw/asx_price_history.csv    one file, appended as it goes, resumable
Out:   data/processed/asx_price_milestones.csv

The ASX twin of fetch_prices.py. Deliberately a separate script with a separate
cache: the TSX cache is 170 MB of Canadian bars keyed on TMX co_id, and mixing
two markets into one file buys nothing and risks the TSX extract.

Requires: pip install yfinance     Needs internet.

COLUMNS
  px_base   mean adjusted close over the first BASE_DAYS trading days from
            listing. Day zero alone is the least reliable price a junior ever
            prints, and every return divides by this, so a short mean is used.
  px_dN     adjusted close on the first trading day at least N days after
            listing, accepted only within TOLERANCE days of the target; blank
            if none.
  ret_dN    px_dN / px_base - 1.
  split_factor  product of all share splits since listing. Below 1 means a
            consolidation - 0.1 is a 10:1 rollback. Taken from Yahoo's splits
            series, because its Close is already split-adjusted and so hides
            them. Coverage of small-cap corporate actions is incomplete, so
            1.0 does not prove none occurred.
  consolidated  split_factor < 1.
  div_total  dividends per share paid since listing.
  days_price_before_listing  days the price series starts before the stated
            listing date. Positive is the backdoor-listing signature.
  price_predates_listing  that gap exceeds PREDATE_LIMIT.

  Australian dollars, never converted. A ret_ column is a ratio and so is
  currency-free and comparable with the TSX one; a px_ column is not.

WHERE THIS DIFFERS FROM THE TSX RUN
  Every ASX miner has a listing date, so the 222-company hole that made a fifth
  of the TSX population unanchorable does not exist here. Expect materially
  better coverage.

  But the ASX date is the date the *entity* listed, and backdoor listings -
  a mining company reversing into a dormant shell - keep the shell's original
  date. Same failure as TMX's RTO and Qualifying Transaction listings: the
  price series starts years before the mining business did.

  covers_listing does NOT catch this. It reads True for exactly these cases,
  because a series starting early certainly covers the listing. The guard that
  works is days_price_before_listing: Antilles Gold states a 1993 listing and
  Yahoo's quotes start in 1988. Anything over PREDATE_LIMIT is flagged and
  excluded from the returns summary.

  Adj Close going non-positive is NOT repaired. AIC Mines is negative for the
  twenty-one years 1993-2014, because A$5.49 of dividends are back-adjusted
  through a 12:1 and then a 20:1 consolidation. Its Close series is positive
  throughout and could be substituted, but that silently turns a total return
  into a price return for one company and not the rest, so the row is dropped
  and reported instead.

CAVEATS
  Survivorship: only companies listed at 26 August 2026 are present. Longer
  milestones are progressively more selected, so long-horizon returns overstate
  the typical outcome.

  Prices are Yahoo Finance via yfinance - free, and unreliable on thin juniors.
  On an exchange where the median miner is A$32M, that is most of the file.
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "asx_enriched.csv"
CACHE = ROOT / "data" / "raw" / "asx_price_history.csv"
OUT = ROOT / "data" / "processed" / "asx_price_milestones.csv"

# Days since listing. Identical to the TSX set so the two extracts line up.
MILESTONES = [7, 30, 90, 180, 365, 730, 1095, 1825, 2555, 3650, 5475]

# The base every return divides by. Day zero alone is the least reliable price
# a junior ever prints - thin volume, wide spread, often just the placement
# price - so one bad tick would corrupt every return in the row.
BASE_DAYS = 5

# A milestone is filled only if a trading day falls within this many days of
# the target. Beyond that the gap is real (halt, suspension, no trading) and a
# nearby price would misrepresent it.
TOLERANCE = 10

# A price series may legitimately start a few days before the official listing
# date - grey-market and when-issued quotes. Beyond a quarter it is not a
# rounding difference, it is a different company: a backdoor listing that
# inherited a shell's ticker and price history.
PREDATE_LIMIT = 90


def source(all_fetched=False):
    """The population: miners by default, everything fetched with --all."""
    df = pd.read_csv(SRC, low_memory=False)
    if not all_fetched:
        df = df[df["is_miner"].fillna(False).astype(bool)]
    return df.reset_index(drop=True)


def done_tickers():
    """Tickers already in the cache - including those that returned nothing,
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
            # request - free, and the only way to see consolidations, since
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
    # A share price cannot be zero or negative. Yahoo's Adj Close can be,
    # because it back-adjusts for distributions: when a company returns more
    # capital per share than the share was worth at the time - routine for an
    # explorer that pays out a settlement or spins off an asset - the adjusted
    # series runs through zero. This cost the TSX run 9,809 quotes across five
    # companies and produced a -100.8% return before it was caught. Those
    # quotes are dropped rather than repaired, so the TOLERANCE checks below
    # blank the affected milestones instead of silently substituting a price
    # from a later date.
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

    # How far the price series starts BEFORE the stated listing date. Positive
    # means Yahoo has quotes predating the listing, which on the ASX almost
    # always means a backdoor listing: a mining company reversed into a dormant
    # shell and inherited its ticker and its price history. Antilles Gold says
    # it listed on 1993-11-25; the series starts 1988-01-29.
    #
    # covers_listing does not catch this - it reads True, because a series that
    # starts early certainly covers the listing. This is the guard that works.
    rec["days_price_before_listing"] = int((start - h["date"].iloc[0]).days)
    rec["price_predates_listing"] = bool(
        rec["days_price_before_listing"] > PREDATE_LIMIT)

    # base = mean of the first BASE_DAYS trading days on/after listing
    at_start = h[h["date"] >= start].head(BASE_DAYS)
    if len(at_start) and (at_start["date"].iloc[0] - start).days <= TOLERANCE:
        rec["px_base"] = round(float(at_start["adj_close"].mean()), 4)
        rec["vol_base"] = int(at_start["volume"].mean()) if at_start["volume"].notna().any() else None

    # Corporate actions since listing. Yahoo's Close is already split-adjusted,
    # so a rollback is invisible in the prices - only the splits series shows it.
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
            "ticker": r.ticker, "ticker_full": r.ticker_full, "name": r.name,
            "stage": getattr(r, "stage", None),
            "commodities": getattr(r, "commodities", None),
            "listing_date": r.listing_date, "mcap_26aug2026": r.mcap,
            **milestones_for(hists.get(r.ticker_full), r.listing_date,
                             r.ticker_full in attempted),
        })
    cols = (["ticker", "ticker_full", "name", "stage", "commodities", "listing_date",
             "status", "covers_listing", "price_predates_listing",
             "days_price_before_listing", "first_price_date", "last_price_date",
             "trading_days", "milestones_filled", "consolidated", "split_factor",
             "n_splits", "div_total", "vol_base",
             "mcap_26aug2026", "px_base"]
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
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild the extract from cache, no fetching")
    ap.add_argument("--limit", type=int, help="fetch only the first N outstanding")
    ap.add_argument("--all", action="store_true",
                    help="all 775 fetched companies, not just the 726 miners")
    a = ap.parse_args()

    df = source(a.all)
    print(f"population: {len(df)} companies")
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

    ok = data[data["status"].eq("ok")]
    if len(ok):
        # .eq(True) not .fillna(False).astype(bool): the column is object dtype
        # with NaN for unpriced rows, and pandas warns on that downcast
        shell = ok["price_predates_listing"].eq(True)
        print(f"\npriced: {len(ok)}   of which price predates listing by "
              f">{PREDATE_LIMIT}d: {int(shell.sum())}  (likely backdoor listings, "
              f"excluded from the returns below)")
        clean = ok[~shell]
        print("\nmedian return, excluding suspected backdoor listings:")
        for c in ("ret_d365", "ret_d1825", "ret_latest"):
            if c in clean:
                s, a = clean[c].dropna(), ok[c].dropna()
                if len(s):
                    print(f"  {c:<11} n={len(s):>4}  median={s.median():+.0%}"
                          f"  negative={100 * (s < 0).mean():.0f}%"
                          f"   [all priced: n={len(a)} median={a.median():+.0%}]")
    print(f"\n{len(data)} rows -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
