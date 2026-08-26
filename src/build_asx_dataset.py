"""
Clean the ASX listed-companies export into one row per company.

    python src/build_asx_dataset.py

In:   data/raw/ASX_Listed_Companies_*.csv
Out:  data/processed/asx_clean.csv

WHAT THIS FILE IS NOT
The TMX exports arrive pre-filtered to mining and carry commodity, property
location and value traded. This one carries five columns: code, name, GICS
industry group, listing date and market cap. There is no mining flag, no
commodity, no project location and no trading data, so most of the TSX analysis
has nothing to stand on here. What survives is population, size and listing
date.

WHY THE POPULATION IS "MATERIALS", NOT "MINING"
GICS industry group is the finest classification in the export, and its
Materials group is where miners sit — together with chemicals, packaging and
building products. The sub-industry level that would separate Metals & Mining
is not in the file. Rather than guess, every row is kept and flagged, so the
choice of population is made downstream and in the open:

  is_materials   GICS says Materials. Over-counts: Amcor (packaging) is here.
  mining_name    the company name says mining. Under-counts: Alcoa does not.

Neither is right on its own. Both are recorded so a reader can see the gap
between them, which is the honest measure of how uncertain this population is.

CURRENCY
Market cap is Australian dollars. The size bands use the same numeric
thresholds as the TSX side so the distributions have the same shape, but a
band is A$ here and C$ there — they are not converted, and must not be read
as equal.
"""

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "asx_clean.csv"

# Same thresholds as the TSX side, so the two distributions are the same shape.
SIZE_BINS = [0, 5e6, 25e6, 100e6, 500e6, 2e9, float("inf")]
SIZE_LABELS = ["< $5M", "$5–25M", "$25–100M",
               "$100–500M", "$500M–2B", "> $2B"]

# Words that only appear in a miner's name. Deliberately not a filter — it is
# recorded next to the GICS flag so the disagreement between them is visible.
MINING_WORDS = [
    "MINING", "MINERAL", "MINERALS", "MINES", "RESOURCES", "EXPLORATION",
    "METALS", "GOLD", "SILVER", "COPPER", "LITHIUM", "NICKEL", "IRON ORE",
    "URANIUM", "ZINC", "COBALT", "GRAPHITE", "RARE EARTH", "RARE EARTHS",
    "TUNGSTEN", "ANTIMONY", "MANGANESE", "POTASH", "VANADIUM", "TITANIUM",
    "PLATINUM", "PALLADIUM", "BAUXITE", "ALUMINA", "COAL", "DIAMOND",
    "DIAMONDS", "TIN", "LEAD", "MOLYBDENUM", "PHOSPHATE", "QUARRY",
]
# Letter boundaries rather than \b: "29METALS" must match (the digit is not a
# letter) while "BEACON LIGHTING" must not match TIN and "WAM LEADERS" must not
# match LEAD. A plain substring test gets both of those wrong.
MINING_RE = re.compile(
    "|".join(f"(?<![A-Z]){re.escape(w)}(?![A-Z])" for w in MINING_WORDS))


def source_file():
    hits = sorted(RAW.glob("ASX_Listed_Companies_*.csv"))
    if not hits:
        raise SystemExit(f"no ASX export found in {RAW}")
    return hits[-1]


def main():
    src = source_file()
    df = pd.read_csv(src, dtype=str)
    df.columns = ["ticker", "name", "gics", "listing_date", "mcap"]
    raw_rows = len(df)

    df["name"] = df["name"].str.strip()
    df["gics"] = df["gics"].str.strip()

    # Yahoo's symbol for an ASX line, so a later price run needs no rework.
    df["ticker_full"] = df["ticker"].str.strip() + ".AX"
    df["market"] = "ASX"

    # "--" is a suspended or unpriced line, not a zero. Left blank, and counted
    # below, because a zero would drag every median and total it touches.
    df["mcap"] = pd.to_numeric(df["mcap"], errors="coerce")

    # DD/MM/YYYY — confirmed by day values above 12 in the first field.
    df["listing_date"] = pd.to_datetime(
        df["listing_date"], format="%d/%m/%Y", errors="coerce")
    df["listing_year"] = df["listing_date"].dt.year

    df["is_materials"] = df["gics"].eq("Materials")
    df["mining_name"] = df["name"].str.upper().str.contains(MINING_RE)

    df["size_band"] = pd.cut(df["mcap"], bins=SIZE_BINS, labels=SIZE_LABELS)

    df = df[[
        "ticker", "ticker_full", "name", "market", "gics",
        "listing_date", "listing_year", "mcap", "size_band",
        "is_materials", "mining_name",
    ]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    mat = df[df["is_materials"]]
    both = df["is_materials"] & df["mining_name"]
    print(f"source: {src.name}")
    print(f"{raw_rows} rows -> {OUT.relative_to(ROOT)}\n")
    print(f"Materials (GICS)            {len(mat):>5}")
    print(f"  ... and mining name       {int(both.sum()):>5}")
    print(f"  ... but no mining name    {int((df['is_materials'] & ~df['mining_name']).sum()):>5}")
    print(f"Mining name, NOT Materials  {int((~df['is_materials'] & df['mining_name']).sum()):>5}")
    print(f"\nno market cap ('--' or blank)  {int(df['mcap'].isna().sum()):>5}"
          f"   of which Materials {int(mat['mcap'].isna().sum()):>4}")
    print(f"no listing date                {int(df['listing_date'].isna().sum()):>5}")
    print(f"\nMaterials market cap  A${mat['mcap'].sum() / 1e9:,.1f}B"
          f"   median A${mat['mcap'].median() / 1e6:,.1f}M")
    print("\nsize bands (Materials):")
    print(mat["size_band"].value_counts().reindex(SIZE_LABELS).to_string())


if __name__ == "__main__":
    main()
