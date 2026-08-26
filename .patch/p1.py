# -*- coding: utf-8 -*-
import io, sys

p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()


def sub(a, b):
    global s
    assert a in s, "NOT FOUND: " + a[:70]
    s = s.replace(a, b, 1)


# ─────────────────────────────────────────────────────────── data builders ───
# _series takes a column name; the stage cuts need arbitrary masks, so the body
# moves into a mask-taking helper and _series becomes a thin wrapper. Same
# output shape, so the generic renderer keeps working on all of them.
sub(
    '''def _series(df, flag_col, label):
    row = {"label": label}
    mask = df[flag_col].fillna(False)
    for board in BOARDS:
        row[board] = _stats(df[mask & (df["board"] == board)])
    row["ALL"] = _stats(df[mask])       # for non-additive measures on both boards
    return row''',
    '''def _series_mask(df, mask, label):
    row = {"label": label}
    for board in BOARDS:
        row[board] = _stats(df[mask & (df["board"] == board)])
    row["ALL"] = _stats(df[mask])       # for non-additive measures on both boards
    return row


def _series(df, flag_col, label):
    return _series_mask(df, df[flag_col].fillna(False), label)''',
)

# ───────────────────────────────────────────────── stage cuts, next to size ───
sub(
    '''def build_size(df):''',
    '''# Everything that is not selling metal. Royalty/streamer is excluded because
# it earns without operating, so it belongs in neither camp.
NON_PRODUCING = ("Explorer", "Shell", "Unknown")

# Below this a producing share is one or two companies and reads as noise.
PRODSHARE_MIN = 15


def build_stage_series(df):
    """Stage in the same shape as commodity and region.

    That is the whole point of the shape: the Measure toggle then answers
    "is explorer trading thinner, or only smaller?" without any new plumbing.
    """
    if "stage" not in df.columns:
        return None
    return [_series_mask(df, df["stage"] == st, st)
            for st in STAGE_ORDER if (df["stage"] == st).any()]


def build_npsize(df):
    """Size distribution of the companies that are not producing.

    Explorer runs from a shell holding one claim to Seabridge at C$3.9B.
    Nothing in the free data separates those, but market cap does it well
    enough to be worth showing on its own rather than implying a stage.
    """
    if "stage" not in df.columns:
        return None
    sub = df[df["stage"].isin(NON_PRODUCING)]
    band = pd.cut(sub["mcap"], bins=SIZE_BINS, labels=SIZE_LABELS)
    return [_series_mask(sub, band == lab, lab) for lab in SIZE_LABELS]


def build_prodshare(df):
    """Producing companies as a share of each commodity's companies.

    Counts, not the share itself, because the board filter has to be applied
    before the division — a share of a share is not a share.
    """
    if "stage" not in df.columns:
        return None
    producing = df["stage"] == "Producer"
    out = []
    for c in SPECIFIC_COMMODITIES:
        col = _slug(c)
        if col not in df.columns:
            continue
        m = df[col].fillna(False)
        row = {"label": c}
        for b in BOARDS:
            mb = m & (df["board"] == b)
            row[b] = {"prod": int((mb & producing).sum()), "tot": int(mb.sum())}
        if sum(row[b]["tot"] for b in BOARDS):
            out.append(row)
    return out


def build_size(df):''',
)

sub(
    '''        "stage": build_stage(df),''',
    '''        "stage": build_stage(df),
        "stage_series": build_stage_series(df),
        "npsize": build_npsize(df),
        "prodshare": build_prodshare(df),''',
)

# ────────────────────────────────────────────────────────────────────── CSS ───
sub(
    '''  --series-TSXV: #eb6834;''',
    '''  --series-TSXV: #eb6834;
  /* A share is not a board, so it must not borrow a board's colour. Slot 3 of
     the validated categorical palette; passes CVD separation against both. */
  --series-stage: #1baf7a;''',
)

# ─────────────────────────────────────────────────────────────────────── JS ───
# distributions must keep their band order; ranked charts sort by value
sub(
    '''  const ADDITIVE = { n: true, mcap: true, median: false, turnover: false };''',
    '''  const ADDITIVE = { n: true, mcap: true, median: false, turnover: false };

  // Sorting a distribution by value destroys it — the bands are the x axis.
  const KEEP_ORDER = { npsize: true };''',
)

sub(
    '''        return { label: r.label, parts, total };
      })
      .sort((a, b) => b.total - a.total);''',
    '''        return { label: r.label, parts, total };
      });
    if (!KEEP_ORDER[key]) rows.sort((a, b) => b.total - a.total);''',
)

sub(
    '''    const rows = D[key]
      .map(r => {''',
    '''    const rows = D[key]
      .map(r => {''',
)

# producer share renderer
sub(
    '''  function drawAll() {''',
    '''  // ---- producing share by commodity ----
  // One series, so no CVD pair to worry about, but every bar carries its own
  // number and the table view is there — the relief the contrast check wants.
  function drawProdShare() {
    const host = document.getElementById('chart-prodshare');
    if (!host || !D.prodshare) return;
    const sel = [...boards];
    const MIN = 15;

    const rows = D.prodshare
      .map(r => {
        const prod = sel.reduce((s, b) => s + r[b].prod, 0);
        const tot = sel.reduce((s, b) => s + r[b].tot, 0);
        return { label: r.label, prod, tot, share: tot ? prod / tot : 0 };
      })
      // filtered AFTER the board filter: TSXV-only can thin a commodity out
      .filter(r => r.tot >= MIN)
      .sort((a, b) => b.share - a.share);

    const max = Math.max(...rows.map(r => r.share), 0.01);

    host.innerHTML = rows
      .map(r => {
        const w = Math.max((r.share / max) * 100, r.share > 0 ? 0.4 : 0);
        return `<div class="row"><div class="cat">${r.label}</div>
                <div class="track"><div class="bar"><div class="seg-fill"
                  style="width:${w}%;background:var(--series-stage)"
                  data-label="${r.label}" data-prod="${r.prod}"
                  data-tot="${r.tot}"></div></div></div>
                <div class="val">${Math.round(r.share * 100)}%</div></div>`;
      })
      .join('');

    host.querySelectorAll('.seg-fill').forEach(el => {
      el.addEventListener('mousemove', e =>
        showTip(e, `<b>${el.dataset.label}</b><br>` +
          `${el.dataset.prod} producing of ${el.dataset.tot}`));
      el.addEventListener('mouseleave', hideTip);
    });

    document.getElementById('table-prodshare').innerHTML =
      '<table><thead><tr><th></th><th class="num">Producing</th>' +
      '<th class="num">Companies</th><th class="num">Share</th></tr></thead><tbody>' +
      rows.map(r =>
        `<tr><td>${r.label}</td><td class="num">${r.prod}</td>` +
        `<td class="num">${r.tot}</td>` +
        `<td class="num">${Math.round(r.share * 100)}%</td></tr>`).join('') +
      '</tbody></table>';
  }

  function drawAll() {''',
)

sub(
    """    draw('commodity');
    draw('region');""",
    """    draw('commodity');
    draw('region');
    if (D.stage_series) draw('stage_series');
    if (D.npsize) draw('npsize');
    drawProdShare();""",
)

io.open(p, "w", encoding="utf-8").write(s)
print("patched charts.py (data + css + js)")
