# -*- coding: utf-8 -*-
import io, sys

p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()


def sub(a, b):
    global s
    assert a in s, "NOT FOUND: " + a[:70]
    s = s.replace(a, b, 1)


# ── paths ───────────────────────────────────────────────────────────────────
sub(
    '''PRICES = ROOT / "data" / "processed" / "price_milestones.csv"''',
    '''PRICES = ROOT / "data" / "processed" / "price_milestones.csv"
ASX_DATA = ROOT / "data" / "processed" / "asx_clean.csv"''',
)

# ── builders ────────────────────────────────────────────────────────────────
sub(
    '''def _esc(text):''',
    '''# The ASX export has no board split and no second series of any kind, so its
# charts are single-series. A third hue rather than a borrowed board colour:
# TSX blue on an ASX chart would read as a comparison that is not being made.
ASX_SIZE_LABELS = ["< $5M", "$5\\u201325M", "$25\\u2013100M",
                   "$100\\u2013500M", "$500M\\u20132B", "> $2B"]

# Before this, surviving listings are a thin tail back to 1885.
ASX_FIRST_YEAR = 2000


def build_asx():
    """Everything the ASX file can support, which is not much.

    Population is GICS Materials — the finest classification in the export.
    It carries roughly A$92B of packaging, steel and chemicals, and it leaves
    coal and uranium miners out in Energy. Both are stated wherever the number
    is used rather than quietly corrected.
    """
    if not ASX_DATA.exists():
        return None
    df = pd.read_csv(ASX_DATA)
    m = df[df["is_materials"] == True]          # noqa: E712 — CSV round-trip
    priced = m[m["mcap"].notna()]
    total = float(priced["mcap"].sum())

    size = [{"label": lab, "n": int((m["size_band"] == lab).sum())}
            for lab in ASX_SIZE_LABELS]

    yrs = m["listing_year"].dropna().astype(int)
    years = [{"label": str(y), "n": int((yrs == y).sum())}
             for y in range(ASX_FIRST_YEAR, int(yrs.max()) + 1)]

    top10 = priced.nlargest(10, "mcap")
    return {
        "n": int(len(m)),
        "total": total,
        "median": float(priced["mcap"].median()),
        "no_mcap": int(m["mcap"].isna().sum()),
        "size": size,
        "years": years,
        "before": int((yrs < ASX_FIRST_YEAR).sum()),
        "top10_share": 100 * float(top10["mcap"].sum()) / total,
        "largest": top10.iloc[0]["name"],
        "largest_share": 100 * float(top10.iloc[0]["mcap"]) / total,
    }


def _esc(text):''',
)

# ── single-series static bars ───────────────────────────────────────────────
sub(
    '''def static_chart(kind):''',
    '''def static_bars_one(rows, note="", legend="Companies"):
    """One series, no board split — the ASX charts.

    Same markup as the stacked version so the hover script and the CSS both
    keep working; only the number of segments differs.
    """
    biggest = max((r["n"] for r in rows), default=1) or 1
    out = ['<div class="viz-root viz-static"><div class="legend">'
           f'<span><i style="background:var(--series-ASX)"></i>{_esc(legend)}</span>'
           '</div><div class="rows">']
    for r in rows:
        w = 100 * r["n"] / biggest
        seg = (f'<div class="seg-fill" style="width:{w:.2f}%;'
               f'background:var(--series-ASX)" title="{r["n"]:,}"></div>'
               if r["n"] else "")
        out.append(
            f'<div class="row"><div class="cat">{_esc(r["label"])}</div>'
            f'<div class="track"><div class="bar">{seg}</div></div>'
            f'<div class="val">{r["n"]:,}</div></div>'
        )
    out.append("</div>")
    if note:
        out.append(f'<p class="note" style="margin-top:12px">{note}</p>')
    out.append("</div>")
    return "".join(out)


def static_chart(kind):''',
)

sub(
    '''    if kind == "stage":''',
    '''    if kind.startswith("asx_"):
        a = build_asx()
        if not a:
            raise KeyError("asx_clean.csv missing — run build_asx_dataset.py")
        if kind == "asx_size":
            return static_bars_one(
                a["size"],
                note=f"Market cap in Australian dollars. {a['no_mcap']} companies "
                     f"show no market cap in the export — suspended lines, read as "
                     f"blank rather than zero, so they appear in no band.")
        if kind == "asx_listings":
            return static_bars_one(
                a["years"],
                note=f"Companies that listed in each year <strong>and are still "
                     f"listed today</strong>, so early years are undercounted by "
                     f"everything that has since failed or been acquired. "
                     f"{a['before']} surviving companies listed before "
                     f"{ASX_FIRST_YEAR} and are not shown.",
                legend="Listings")
        raise KeyError(f"unknown chart: {kind}")

    if kind == "stage":''',
)

# ── CSS ─────────────────────────────────────────────────────────────────────
sub(
    '''  --series-stage: #1baf7a;''',
    '''  --series-stage: #1baf7a;
  /* A third market, not a third board — slot 6 of the same validated palette. */
  --series-ASX: #4a3aa7;''',
)

io.open(p, "w", encoding="utf-8").write(s)
print("patched charts.py for ASX")
