"""
Charts for the ASX side of the report.

Separate from charts.py because the two markets do not share a dimension. Every
TSX chart splits by BOARD — TSX against TSXV — and the ASX has one board. The
natural second dimension here is STAGE, which the TSX side could not use because
its stage column is a residual (producer versus everything else) rather than a
lifecycle.

    import asx_charts
    asx_charts.section_html()        the interactive Charts tab
    asx_charts.static_chart(name)    one inert chart for embedding in a note

WHAT IS NOT COMPARABLE, AND WHY IT IS NAMED DIFFERENTLY
turnover_est is not the TSX turnover. There, TMX reports dollars actually traded
over six months and turnover is that over market cap. Here the exchange export
carries no trading data at all, so it is estimated from average daily volume x
price x 126 trading days over market cap. Same quantity, different construction,
different reliability — so the two never share an axis and the label always says
"est".

Currency is never converted. An A$ band is not the C$ band with the same label.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "asx_enriched.csv"

# Lifecycle order, not frequency order — the bars read as a sequence.
STAGES = ["Producer", "Developer", "Explorer", "Other"]
STAGE_OF = {"Producer": "Producer", "Developer": "Developer",
            "Explorer": "Explorer", "Royalty/Streamer": "Other",
            "Unknown": "Other", "Shell": "Other"}

# Validated as a 4-slot categorical set: worst all-pairs CVD ΔE 9.1, above the
# floor. Green for Producer matches the "share producing" green on the TSX tab,
# so the colour means the same thing in both markets.
STAGE_COLOUR = {"Producer": "#1baf7a", "Developer": "#eda100",
                "Explorer": "#2a78d6", "Other": "#4a3aa7"}

# Mirrors the TSX chart exactly so the two can be read side by side.
SHARED_COMMODITIES = [
    ("gold", "Gold"), ("copper", "Copper"), ("lithium", "Lithium"),
    ("silver", "Silver"), ("nickel", "Nickel"), ("rare_earths", "Rare Earths"),
    ("zinc", "Zinc"), ("lead", "Lead"), ("iron", "Iron"),
    ("uranium", "Uranium"), ("platinum_pgm", "Platinum/PGM"),
    ("molybdenum", "Molybdenum"), ("tungsten", "Tungsten"), ("coal", "Coal"),
    ("diamond", "Diamond"), ("potash", "Potash"),
]
# Commodities the TMX flag set has no column for. Shown separately so nobody
# reads them as part of a like-for-like comparison.
ASX_ONLY = [
    ("cobalt", "Cobalt"), ("niobium_tantalum", "Niobium/Tantalum"),
    ("graphite", "Graphite"), ("vanadium", "Vanadium"),
    ("manganese", "Manganese"), ("antimony", "Antimony"),
    ("bauxite_alumina", "Bauxite/Alumina"), ("mineral_sands", "Mineral Sands"),
    ("tin", "Tin"), ("scandium", "Scandium"), ("silica", "Silica"),
    ("phosphate", "Phosphate"),
]

REGIONS = [
    ("prop_aus_nz_png", "Aus / NZ / PNG"), ("prop_africa", "Africa"),
    ("prop_canada", "Canada"), ("prop_usa", "USA"),
    ("prop_latin_america", "Latin America"), ("prop_uk_europe", "UK / Europe"),
    ("prop_asia", "Asia"), ("prop_other", "Other / unnamed"),
]

SIZE_LABELS = ["< $5M", "$5–25M", "$25–100M", "$100–500M", "$500M–2B", "> $2B"]
FIRST_YEAR = 2000
PRODSHARE_MIN = 15

PRICES = ROOT / "data" / "processed" / "asx_price_milestones.csv"
TSX_PRICES = ROOT / "data" / "processed" / "price_milestones.csv"

MILESTONE_LABELS = {7: "7d", 30: "1m", 90: "3m", 180: "6m", 365: "1y", 730: "2y",
                    1095: "3y", 1825: "5y", 2555: "7y", 3650: "10y", 5475: "15y"}

# Below this a median is noise. Developer has 11 priced companies, so its line
# stops partway across rather than wandering off on a sample of seven.
MIN_SAMPLE = 10


def _load():
    df = pd.read_csv(DATA)
    df = df[df["is_miner"] == True].copy()          # noqa: E712 — CSV round-trip
    df["stage_group"] = df["stage"].map(STAGE_OF).fillna("Other")
    return df


def _stats(sub):
    """Everything a measure might need. Same shape as the TSX builder."""
    mcap = float(sub["mcap"].sum())
    return {
        "n": int(len(sub)),
        "mcap": mcap,
        "median": float(sub["mcap"].median()) if len(sub) and sub["mcap"].notna().any() else 0.0,
        "turnover": (float(sub["turnover_est"].median())
                     if sub["turnover_est"].notna().any() else 0.0),
    }


def _series(df, mask, label):
    row = {"label": label}
    for st in STAGES:
        row[st] = _stats(df[mask & df["stage_group"].eq(st)])
    row["ALL"] = _stats(df[mask])
    return row


def _curve(sub, days):
    """Median, quartiles and share underwater at each milestone for one group."""
    med, neg, p25, p75, n = [], [], [], [], []
    for d in days:
        v = sub[f"ret_d{d}"].dropna()
        n.append(int(len(v)))
        if len(v) < MIN_SAMPLE:
            med.append(None); neg.append(None); p25.append(None); p75.append(None)
        else:
            med.append(round(float(v.median()) * 100, 1))
            neg.append(round(float((v < 0).mean()) * 100, 1))
            p25.append(round(float(v.quantile(0.25)) * 100, 1))
            p75.append(round(float(v.quantile(0.75)) * 100, 1))
    return {"median": med, "neg": neg, "p25": p25, "p75": p75, "n": n}


def build_returns():
    """Post-listing return curve by stage, with the TSX curve as a reference.

    Returns None if fetch_asx_prices.py has not been run, so the report still
    builds on a machine without the price file.

    Two things this cannot do, both stated on the chart:

    Stage is measured TODAY, not at listing. A company that listed as an
    explorer and became a producer counts as a producer across its whole
    history, so the producer line is partly a definition of success rather than
    a finding about it.

    Suspected backdoor listings are excluded — where Yahoo's price series
    predates the stated listing date the anchor is a shell's, not the mining
    company's.
    """
    if not PRICES.exists():
        return None
    p = pd.read_csv(PRICES, low_memory=False)
    shell = p["price_predates_listing"].eq(True) if "price_predates_listing" in p else False
    ok = p[p["status"].eq("ok") & ~shell].copy()
    if ok.empty:
        return None
    ok["stage_group"] = ok["stage"].map(STAGE_OF).fillna("Other")

    days = [d for d in MILESTONE_LABELS if f"ret_d{d}" in ok.columns]
    out = {"labels": [MILESTONE_LABELS[d] for d in days],
           "stages": {st: _curve(ok[ok["stage_group"].eq(st)], days) for st in STAGES},
           "all": _curve(ok, days)}

    # The TSX curve as a dashed reference. This is the one cross-market
    # comparison in the report that is honestly like for like: same script,
    # same milestones, same base, and a return is a ratio so the currencies
    # never meet. It is here because the two curves turn out to be the same
    # curve, which is the finding.
    if TSX_PRICES.exists():
        t = pd.read_csv(TSX_PRICES, low_memory=False)
        t = t[t["status"].eq("ok")]
        tdays = [d for d in days if f"ret_d{d}" in t.columns]
        if len(t) and tdays == days:
            out["tsx"] = _curve(t, days)

    out["priced"] = int(len(ok))
    out["total"] = int(len(p))
    out["no_history"] = int(p["status"].eq("no price near listing").sum())
    out["shells"] = int(shell.sum()) if hasattr(shell, "sum") else 0
    out["consolidated"] = int((ok["consolidated"] == True).sum())  # noqa: E712
    return out


def build_data():
    df = _load()

    commodity = [_series(df, df["comm_" + k].fillna(False), lab)
                 for k, lab in SHARED_COMMODITIES if "comm_" + k in df.columns]
    commodity = [r for r in commodity if sum(r[s]["n"] for s in STAGES) > 0]

    extra = [_series(df, df["comm_" + k].fillna(False), lab)
             for k, lab in ASX_ONLY if "comm_" + k in df.columns]
    extra = [r for r in extra if sum(r[s]["n"] for s in STAGES) > 0]

    region = [_series(df, df[k].fillna(False), lab)
              for k, lab in REGIONS if k in df.columns]

    size = [_series(df, df["size_band"].eq(lab), lab) for lab in SIZE_LABELS]

    stage = [_series(df, df["stage_group"].eq(st), st) for st in STAGES
             if (df["stage_group"] == st).any()]

    # Producing share by commodity. The chart was removed from the Charts tab;
    # the figures still back the table of the same name on the Numbers tab, so
    # the builder stays. Counts, not shares, so a stage filter could be applied
    # before the division — a share of a share is not a share.
    prodshare = []
    for k, lab in SHARED_COMMODITIES + ASX_ONLY:
        col = "comm_" + k
        if col not in df.columns:
            continue
        m = df[col].fillna(False)
        if int(m.sum()) == 0:
            continue
        prodshare.append({"label": lab, "tot": int(m.sum()),
                          "prod": int((m & df["stage"].eq("Producer")).sum())})

    yrs = df["listing_year"].dropna().astype(int)
    years = list(range(FIRST_YEAR, int(yrs.max()) + 1))
    lines = {
        "years": [str(y) for y in years],
        "series": [{"label": st,
                    "vals": [int(((df["listing_year"] == y)
                                  & df["stage_group"].eq(st)).sum())
                             for y in years]}
                   for st in STAGES],
        "total": [int((df["listing_year"] == y).sum()) for y in years],
        "before": int((yrs < FIRST_YEAR).sum()),
    }

    totals = {st: _stats(df[df["stage_group"].eq(st)]) for st in STAGES}
    return {"commodity": commodity, "extra": extra, "region": region,
            "size": size, "stage": stage, "prodshare": prodshare,
            "lines": lines, "totals": totals, "returns": build_returns(),
            "n": int(len(df)), "mcap": float(df["mcap"].sum()),
            "no_commodity": int(df["no_disclosed_commodity"].sum()),
            "offshore": int(df["operates_offshore"].sum())}


# ─────────────────────────────────────────────────────────────── static bars ──

def _esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _legend(stages=STAGES):
    return ("<div class='legend'>" + "".join(
        f"<span><i style='background:{STAGE_COLOUR[s]}'></i>{s}</span>"
        for s in stages) + "</div>")


def static_bars(rows, note="", stages=STAGES, keep_order=False):
    """Inert stacked bars for embedding in a written tab."""
    def tot(r):
        return sum(r[s]["n"] for s in stages)
    if not keep_order:
        rows = sorted(rows, key=lambda r: -tot(r))
    biggest = max((tot(r) for r in rows), default=1) or 1

    out = ["<div class='viz-root viz-static'>", _legend(stages), "<div class='rows'>"]
    for r in rows:
        segs = "".join(
            f"<div class='seg-fill' style='width:{100 * r[s]['n'] / biggest:.2f}%;"
            f"background:{STAGE_COLOUR[s]}' title='{s}: {r[s]['n']:,}'></div>"
            for s in stages if r[s]["n"] > 0)
        out.append(f"<div class='row'><div class='cat'>{_esc(r['label'])}</div>"
                   f"<div class='track'><div class='bar'>{segs}</div></div>"
                   f"<div class='val'>{tot(r):,}</div></div>")
    out.append("</div>")
    if note:
        out.append(f"<p class='note' style='margin-top:12px'>{note}</p>")
    out.append("</div>")
    return "".join(out)


def static_chart(kind):
    d = build_data()

    if kind == "asx_stage":
        return static_bars(
            d["stage"], keep_order=True,
            note="Producer means reported revenue. Developer means construction "
                 "in progress on the balance sheet — the test the TSX side could "
                 "not run. Other is three royalty companies and 17 with no "
                 "statements at all.")
    if kind == "asx_commodity":
        return static_bars(
            d["commodity"],
            note="Extracted from Yahoo business summaries, so this is what a "
                 "company says it explores for. Companies name more than one, so "
                 "the bars sum to more than 726. These sixteen mirror the TSX "
                 "chart exactly.")
    if kind == "asx_commodity_extra":
        return static_bars(
            d["extra"],
            note="Commodities the TMX flag set has no column for, so these have "
                 "no TSX counterpart to compare against.")
    if kind == "asx_assets":
        return static_bars(
            d["region"],
            note="Regions named in the business summary. A summary usually names "
                 "the flagship project and stops, so these counts <strong>"
                 "understate by construction</strong> — unlike the TSX side, "
                 "which has a property register.")
    if kind == "asx_size":
        return static_bars(
            d["size"], keep_order=True,
            note="Market cap in Australian dollars, never converted. The bands "
                 "use the same numeric thresholds as the TSX chart so the shapes "
                 "compare, but an A$ band is not the C$ band with the same label.")
    raise KeyError(f"unknown chart: {kind}")


# ──────────────────────────────────────────────────────────────── interactive ──

CSS = """
.asx .seg button[data-stage="Producer"] .dot{color:#1baf7a}
.asx .seg button[data-stage="Developer"] .dot{color:#eda100}
.asx .seg button[data-stage="Explorer"] .dot{color:#2a78d6}
.asx .seg button[data-stage="Other"] .dot{color:#4a3aa7}
"""

JS = """
(function () {
  const D = window.__ASXVIZ__;
  const COL = %COL%;
  const STAGES = %STAGES%;
  const on = new Set(STAGES);
  let measure = 'n';
  const ADDITIVE = { n: true, mcap: true, median: false, turnover: false };

  const fmtN = v => v.toLocaleString('en-US');
  const fmtM = v => v >= 1e9 ? 'A$' + (v / 1e9).toFixed(1) + 'B'
    : v >= 1e6 ? 'A$' + Math.round(v / 1e6).toLocaleString('en-US') + 'M'
    : 'A$' + Math.round(v / 1e3).toLocaleString('en-US') + 'k';
  const fmt = v => measure === 'n' ? fmtN(v)
    : measure === 'turnover' ? Math.round(v * 100) + '%' : fmtM(v);

  const tip = document.createElement('div');
  tip.className = 'tip'; document.body.appendChild(tip);
  function showTip(e, html) {
    tip.innerHTML = html; tip.style.opacity = 1;
    const r = tip.getBoundingClientRect();
    let x = e.clientX + 14;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    tip.style.left = x + 'px';
    tip.style.top = Math.min(e.clientY + 14, innerHeight - r.height - 8) + 'px';
  }
  const hideTip = () => (tip.style.opacity = 0);

  const KEEP = { size: true, stage: true };

  function draw(key) {
    const host = document.getElementById('asx-' + key);
    if (!host || !D[key]) return;
    const additive = ADDITIVE[measure];
    const sel = STAGES.filter(s => on.has(s));

    // On the stage chart the row axis IS the stage dimension, so a deselected
    // stage has to lose its row. Leaving it in prints a bar reading zero, which
    // says "no producers" rather than "producers hidden".
    const src = key === 'stage' ? D[key].filter(r => on.has(r.label)) : D[key];

    const rows = src.map(r => {
      const parts = sel.map(s => ({ st: s, v: r[s][measure], n: r[s].n }));
      const total = additive ? parts.reduce((a, p) => a + p.v, 0)
        : (sel.length === STAGES.length ? r.ALL[measure]
          : Math.max(...parts.map(p => p.v)));
      return { label: r.label, parts, total };
    });
    if (!KEEP[key]) rows.sort((a, b) => b.total - a.total);

    const max = additive ? Math.max(...rows.map(r => r.total))
      : Math.max(...rows.flatMap(r => r.parts.map(p => p.v)));

    host.innerHTML = rows.map(r => {
      const segs = r.parts.filter(p => additive ? p.v > 0 : p.n > 0).map(p => {
        const w = Math.max((p.v / (max || 1)) * 100, p.v > 0 ? 0.4 : 0);
        return `<div class="seg-fill" style="width:${w}%;background:${COL[p.st]}"
                 data-l="${r.label}" data-s="${p.st}" data-v="${p.v}" data-n="${p.n}"></div>`;
      }).join('');
      return `<div class="row"><div class="cat">${r.label}</div>
              <div class="track"><div class="bar${additive ? '' : ' grouped'}">${segs}</div></div>
              <div class="val">${fmt(r.total)}</div></div>`;
    }).join('');

    host.querySelectorAll('.seg-fill').forEach(el => {
      el.addEventListener('mousemove', e => showTip(e,
        `<b>${el.dataset.l}</b><br><span class="k">${el.dataset.s}</span> ` +
        `${fmt(+el.dataset.v)}<br><span class="k">${(+el.dataset.n).toLocaleString('en-US')} companies</span>`));
      el.addEventListener('mouseleave', hideTip);
    });

    const tb = document.getElementById('asxtbl-' + key);
    if (tb) tb.innerHTML = '<table><thead><tr><th></th>' +
      sel.map(s => `<th class="num">${s}</th>`).join('') +
      '<th class="num">Total</th></tr></thead><tbody>' +
      rows.map(r => `<tr><td>${r.label}</td>` +
        r.parts.map(p => `<td class="num">${fmt(p.v)}</td>`).join('') +
        `<td class="num">${fmt(r.total)}</td></tr>`).join('') + '</tbody></table>';
  }

  function drawLines() {
    const host = document.getElementById('asx-lines');
    if (!host || !D.lines) return;
    const L = D.lines, W = 900, H = 300, P = { t: 14, r: 96, b: 30, l: 46 };
    const sel = STAGES.filter(s => on.has(s));
    const series = L.series.filter(s => sel.includes(s.label));
    const maxY = Math.max(1, ...series.flatMap(s => s.vals));
    const x = i => P.l + i * (W - P.l - P.r) / Math.max(1, L.years.length - 1);
    const y = v => H - P.b - (v / maxY) * (H - P.t - P.b);

    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img">`;
    for (let g = 0; g <= 4; g++) {
      const v = maxY * g / 4;
      svg += `<line class="grid" x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}"/>` +
        `<text class="axis-txt" x="${P.l - 8}" y="${y(v) + 4}" text-anchor="end">${Math.round(v)}</text>`;
    }
    L.years.forEach((yr, i) => {
      if (i % 4 === 0 || i === L.years.length - 1)
        svg += `<text class="axis-txt" x="${x(i)}" y="${H - 10}" text-anchor="middle">${yr}</text>`;
    });
    series.forEach(s => {
      const d = s.vals.map((v, i) => (i ? 'L' : 'M') + x(i) + ' ' + y(v)).join(' ');
      svg += `<path class="ser" d="${d}" stroke="${COL[s.label]}"/>`;
      const last = s.vals.length - 1;
      svg += `<text class="endlab" x="${x(last) + 8}" y="${y(s.vals[last]) + 4}" fill="${COL[s.label]}">${s.label}</text>`;
    });
    host.innerHTML = svg + '</svg>';
  }

  // ---- returns since listing ----
  // Median, never mean: a handful of 30x survivors would drag a mean upward
  // and hide what happens to the company in the middle.
  let retMode = 'median';

  function drawReturns() {
    const R = D.returns;
    if (!R) return;
    const host = document.getElementById('asx-returns');
    if (!host) return;
    const spread = retMode === 'spread';
    const series = STAGES.filter(s => on.has(s)).map(s => ({
      label: s, colour: COL[s], vals: R.stages[s][spread ? 'median' : retMode],
      lo: R.stages[s].p25, hi: R.stages[s].p75, n: R.stages[s].n,
    }));
    const ref = R.tsx ? { label: 'TSX/TSXV', colour: '#9a9a9a',
                          vals: R.tsx[spread ? 'median' : retMode], n: R.tsx.n } : null;

    const W = 860, H = 330, ml = 46, mr = 78, mt = 14, mb = 44;
    const iw = W - ml - mr, ih = H - mt - mb;
    const flat = series.flatMap(s => spread ? [...s.vals, ...s.lo, ...s.hi] : s.vals)
      .concat(ref ? ref.vals : []).filter(v => v !== null);
    if (!flat.length) { host.innerHTML = ''; return; }

    // the domain always includes zero — which side of it we are on is the point
    const step = 20;
    const lo = Math.floor(Math.min(0, ...flat) / step) * step;
    const rawHi = Math.ceil(Math.max(0, ...flat) / step) * step;
    // The surviving producers' 75th percentile reaches +280% at fifteen years.
    // Letting that set the top squashes every median line into the bottom fifth
    // of the panel and the chart stops saying anything. The domain is capped
    // and the band is clipped, with the overflow named on the chart rather than
    // quietly cropped.
    const CAP = 100;
    const hi = rawHi > CAP ? CAP : rawHi;
    const over = hi < rawHi
      ? series.filter(s => spread && Math.max(...s.hi.filter(v => v !== null)) > hi)
              .map(s => ({ label: s.label, colour: s.colour,
                           v: Math.max(...s.hi.filter(v => v !== null)) }))
      : [];
    const x = i => ml + (i / (R.labels.length - 1)) * iw;
    const y = v => mt + ih - ((v - lo) / (hi - lo)) * ih;

    let g = '';
    for (let v = lo; v <= hi; v += step) {
      g += `<line class="grid" x1="${ml}" x2="${ml + iw}" y1="${y(v)}" y2="${y(v)}"` +
        `${v === 0 ? ' stroke="#9a9a9a"' : ''}/>` +
        `<text class="axis-txt" x="${ml - 8}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`;
    }
    R.labels.forEach((lab, i) => {
      g += `<text class="axis-txt" x="${x(i)}" y="${H - 24}" text-anchor="middle">${lab}</text>`;
      // sample size under each tick: it falls from ~610 to ~270 across the
      // grid, and every later point is a smaller, more selected group
      const n = series.reduce((t, s) => t + (s.n[i] || 0), 0);
      g += `<text class="axis-txt" x="${x(i)}" y="${H - 9}" text-anchor="middle"
              style="font-size:10px;opacity:.7">${n}</text>`;
    });

    // interquartile band as a 12% wash, under the medians — the spread is the
    // finding here, so it has to read as area rather than as more lines
    const bands = !spread ? '' : series.map(s => {
      const idx = s.lo.map((v, i) => i).filter(i => s.lo[i] !== null && s.hi[i] !== null);
      if (idx.length < 2) return '';
      const top = idx.map((i, k) => (k ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(s.hi[i]).toFixed(1)).join(' ');
      const bot = idx.slice().reverse().map(i => 'L' + x(i).toFixed(1) + ' ' + y(s.lo[i]).toFixed(1)).join(' ');
      return `<path d="${top} ${bot} Z" fill="${s.colour}" opacity=".12"/>`;
    }).join('');

    // Lines first, end labels second: several series finish within a few pixels
    // of each other at fifteen years — Explorer at -95% and the TSX reference
    // at -93% collided and printed on top of one another — so the labels are
    // laid out afterwards with a minimum spacing.
    const ends = [];
    const line = (s, dash) => {
      const pts = s.vals.map((v, i) => [i, v]).filter(([, v]) => v !== null);
      if (!pts.length) return '';
      const d = pts.map(([i, v], k) => `${k ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
      const [li, lv] = pts[pts.length - 1];
      ends.push({ x: x(li), y: y(lv), label: s.label, colour: s.colour });
      return `<path class="ser" d="${d}" stroke="${s.colour}"${dash ? ' stroke-dasharray="5 4"' : ''}/>` +
        `<circle class="dot" cx="${x(li)}" cy="${y(lv)}" r="4" fill="${s.colour}"/>`;
    };
    const paths = (ref ? line(ref, true) : '') + series.map(s => line(s, false)).join('');

    const GAP = 13;
    ends.sort((a, b) => a.y - b.y);
    ends.forEach((e, i) => {
      e.ty = i ? Math.max(e.y, ends[i - 1].ty + GAP) : e.y;
    });
    // if the stack has run off the bottom, push the whole run back up
    const spill = ends.length ? ends[ends.length - 1].ty - (mt + ih) : 0;
    if (spill > 0) ends.forEach(e => { e.ty -= spill; });
    const endlabs = ends.map(e =>
      // a leader line where the label had to move off its own point
      (Math.abs(e.ty - e.y) > 2
        ? `<line x1="${(e.x + 4).toFixed(1)}" y1="${e.y.toFixed(1)}"
             x2="${(e.x + 8).toFixed(1)}" y2="${e.ty.toFixed(1)}"
             stroke="${e.colour}" stroke-width="1" opacity=".5"/>` : '') +
      `<text class="endlab" x="${(e.x + 9).toFixed(1)}" y="${(e.ty + 4).toFixed(1)}"
         fill="${e.colour}">${e.label}</text>`).join('');

    const flag = over.map((o, i) =>
      `<text class="axis-txt" x="${ml + 6}" y="${mt + 12 + i * 13}" fill="${o.colour}"
         style="font-size:10px">▲ ${o.label} 75th percentile reaches +${Math.round(o.v)}%</text>`).join('');

    const hit = R.labels.map((_, i) =>
      `<rect class="hit" x="${x(i) - iw / (R.labels.length - 1) / 2}" y="${mt}"
         width="${iw / (R.labels.length - 1)}" height="${ih}" data-i="${i}"/>`).join('');

    host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
        <defs><clipPath id="asx-ret-clip">
          <rect x="${ml}" y="${mt}" width="${iw}" height="${ih}"/>
        </clipPath></defs>
        ${g}<g clip-path="url(#asx-ret-clip)">${bands}${paths}</g>
        <g id="asx-ret-cross"></g>${endlabs}${flag}${hit}</svg>`;

    host.querySelectorAll('.hit').forEach(r => {
      r.addEventListener('mousemove', e => {
        const i = +r.dataset.i;
        document.getElementById('asx-ret-cross').innerHTML =
          `<line class="cross" x1="${x(i)}" x2="${x(i)}" y1="${mt}" y2="${mt + ih}"/>`;
        const rows = series.filter(s => s.vals[i] !== null).map(s => spread
          ? `<span class="k">${s.label}</span> median ${s.vals[i]}%` +
            `<br><span class="k">middle half ${s.lo[i]}% to ${s.hi[i]}% · n=${s.n[i]}</span>`
          : `<span class="k">${s.label}</span> ${s.vals[i]}%` +
            ` <span class="k">(n=${s.n[i]})</span>`).join('<br>');
        const rr = ref && ref.vals[i] !== null
          ? `<br><span class="k">TSX/TSXV</span> ${ref.vals[i]}% <span class="k">(n=${ref.n[i]})</span>` : '';
        showTip(e, `<b>${R.labels[i]} after listing</b><br>` +
          (rows || '<span class="k">too few companies</span>') + rr);
      });
      r.addEventListener('mouseleave', () => {
        document.getElementById('asx-ret-cross').innerHTML = '';
        hideTip();
      });
    });

    const tb = document.getElementById('asxtbl-returns');
    if (tb) tb.innerHTML = '<table><thead><tr><th>After listing</th>' +
      series.map(s => `<th class="num">${s.label}</th><th class="num">n</th>`).join('') +
      (ref ? '<th class="num">TSX/TSXV</th>' : '') + '</tr></thead><tbody>' +
      R.labels.map((lab, i) => `<tr><td>${lab}</td>` +
        series.map(s => `<td class="num">${s.vals[i] === null ? '' : s.vals[i] + '%'}</td>` +
          `<td class="num">${s.n[i]}</td>`).join('') +
        (ref ? `<td class="num">${ref.vals[i] === null ? '' : ref.vals[i] + '%'}</td>` : '') +
        '</tr>').join('') + '</tbody></table>';
  }

  function all() {
    document.querySelectorAll('.asx .legend span[data-stage]').forEach(sp => {
      sp.style.display = on.has(sp.dataset.stage) ? '' : 'none';
    });
    document.querySelectorAll('.asx .measure-note').forEach(n => {
      n.textContent = measure === 'turnover'
        ? 'Estimated turnover: average daily volume x price x 126 trading days, over market cap. NOT the TSX turnover, which TMX reports directly as dollars traded. Stages sit side by side; a median of the parts is not the median for the whole.'
        : measure === 'median'
        ? 'The middle company in each group, not the total. Stages sit side by side; a median of the parts is not the median for the whole.'
        : '';
    });
    ['commodity', 'extra', 'region', 'size', 'stage'].forEach(draw);
    drawLines(); drawReturns();
  }

  document.querySelectorAll('.asx [data-ret]').forEach(btn => {
    btn.addEventListener('click', () => {
      retMode = btn.dataset.ret;
      document.querySelectorAll('.asx [data-ret]').forEach(b =>
        b.setAttribute('aria-pressed', b.dataset.ret === retMode));
      drawReturns();
    });
  });

  document.querySelectorAll('.asx [data-stage]').forEach(btn => {
    if (btn.tagName !== 'BUTTON') return;
    btn.addEventListener('click', () => {
      const s = btn.dataset.stage;
      if (on.has(s)) { if (on.size === 1) return; on.delete(s); } else on.add(s);
      btn.setAttribute('aria-pressed', on.has(s));
      all();
    });
  });
  document.querySelectorAll('.asx [data-measure]').forEach(btn => {
    btn.addEventListener('click', () => {
      measure = btn.dataset.measure;
      document.querySelectorAll('.asx [data-measure]').forEach(b =>
        b.setAttribute('aria-pressed', b.dataset.measure === measure));
      all();
    });
  });
  all();
})();
"""

MEASURE = """  <div class="ctrl-group" style="margin:0 0 6px">
    <span class="ctrl-label">Measure</span>
    <div class="seg">
      <button data-measure="n" aria-pressed="true">Companies</button>
      <button data-measure="mcap" aria-pressed="false">Market cap</button>
      <button data-measure="median" aria-pressed="false">Typical size</button>
      <button data-measure="turnover" aria-pressed="false">% traded (est)</button>
    </div>
  </div>
  <p class="note measure-note" style="margin:0 0 12px"></p>
"""


RETURNS_BLOCK = """
<div class='chart'><h3>What happens after listing</h3>
<p class='note'>Median share-price return at each point in a company's own life,
measured against the mean of its first five trading days. {priced} of {total}
miners are priced: {no_history} have no Yahoo history reaching back to their
listing — almost all of them listed before 2000 — and {shells} are excluded as
suspected backdoor listings, where the price series starts years before the
stated listing date and so belongs to a shell rather than to the mining company.
<strong>Stage is measured today, not at listing.</strong> A company that listed
as an explorer and became a producer counts as a producer across its whole
history, so the producer line describes companies that succeeded rather than a
strategy that works. <strong>These are survivors only</strong> — companies that
failed outright are not in the exchange export at all, so the real picture is
worse than this, and each point is a smaller, more selected group than the one
before it. The count under each label is how quickly that thins out.
<strong>The grey dashed line is the TSX/TSXV curve</strong>, built by the same
script from the same milestones; a return is a ratio, so this is the one
cross-market comparison in the report where the currencies never meet.</p>
<div class="ctrl-group" style="margin:0 0 14px">
  <span class="ctrl-label">Show</span>
  <div class="seg">
    <button data-ret="median" aria-pressed="true">Median return</button>
    <button data-ret="spread" aria-pressed="false">Spread</button>
    <button data-ret="neg" aria-pressed="false">% underwater</button>
  </div>
</div>
{legend}
<div class='linewrap' id='asx-returns'></div>
<details class='tbl'><summary>Show as table</summary>
<div id='asxtbl-returns'></div></details></div>
"""


def _lg():
    return ("<div class='legend'>" + "".join(
        f"<span data-stage='{s}'><i style='background:{STAGE_COLOUR[s]}'></i>{s}</span>"
        for s in STAGES) + "</div>")


def _chart(key, title, note, measure=True, keep=False):
    return (f"<div class='chart'><h3>{title}</h3><p class='note'>{note}</p>"
            + (MEASURE if measure else "") + _lg()
            + f"<div class='rows' id='asx-{key}'></div>"
            f"<details class='tbl'><summary>Show as table</summary>"
            f"<div id='asxtbl-{key}'></div></details></div>")


def section_html():
    d = build_data()
    js = (JS.replace("%COL%", json.dumps(STAGE_COLOUR))
            .replace("%STAGES%", json.dumps(STAGES))
            .replace("%MIN%", str(PRODSHARE_MIN)))
    return f"""
<div class="viz-root viz-live asx">
<style>{CSS}</style>

<div class="ctrls">
  <div class="ctrl-group">
    <span class="ctrl-label">Stage</span>
    <div class="seg">
      {"".join(f'<button data-stage="{s}" aria-pressed="true"><i class="dot"></i>{s}</button>' for s in STAGES)}
    </div>
  </div>
</div>

{_chart("stage", "By stage",
        f"{d['n']} mining companies, A${d['mcap']/1e9:,.0f}B. Producer means "
        f"reported revenue; Developer means construction in progress on the "
        f"balance sheet. Switch to <strong>% traded (est)</strong> for whether "
        f"explorer trading is genuinely thinner or only looks that way.",
        keep=True)}

{_chart("commodity", "Commodity",
        f"Extracted from business summaries — what a company says it explores "
        f"for, which is not the same as what it holds. Companies name more than "
        f"one, so bars sum to more than {d['n']}. "
        f"{d['no_commodity']} name none. These sixteen mirror the TSX chart.")}

{_chart("extra", "Commodities with no TSX counterpart",
        "The TMX flag set has no column for these, so they cannot be compared "
        "like for like — shown separately rather than mixed into the chart above.")}

{_chart("region", "Where the assets are",
        f"Regions named in the summary. Usually the flagship project and no "
        f"more, so these <strong>understate by construction</strong> — the TSX "
        f"side has a property register and this does not. "
        f"{d['offshore']} companies name ground outside Australasia.")}

{_chart("size", "Size distribution",
        "Australian dollars, never converted. Same numeric thresholds as the "
        "TSX chart so the shapes compare — but an A$ band is not the C$ band "
        "with the same label.", keep=True)}


<div class='chart'><h3>Companies by listing year</h3>
<p class='note'>Companies that listed in each year <strong>and are still listed
today</strong>, so early years are undercounted by everything that has since
failed or been acquired. {d['lines']['before']} surviving companies listed before
{FIRST_YEAR} and are not shown.</p>
{_lg()}
<div class='linewrap' id='asx-lines'></div></div>

{RETURNS_BLOCK.format(legend=_lg(), **d["returns"]) if d["returns"] else ""}

<script>window.__ASXVIZ__ = {json.dumps(d)};</script>
<script>{js}</script>
</div>
"""
