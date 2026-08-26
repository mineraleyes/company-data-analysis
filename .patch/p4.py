# -*- coding: utf-8 -*-
import io, sys

p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()


def sub(a, b):
    global s
    assert a in s, "NOT FOUND: " + a[:70]
    s = s.replace(a, b, 1)


# ── tab groups per market ───────────────────────────────────────────────────
sub(
    '''TITLE = "TSX / TSXV Mining"

# (tab label, filename). Order defines tab order.
# A filename of None means the tab is generated, not read from markdown.
TABS = [
    ("Stage 1 · Dataset", "stage1-dataset.md"),
    ("Stage 1 · Numbers", "stage1-numbers.md"),
    ("Stage 1 · Charts", None),
    ("Stage 2", "stage2.md"),
]''',
    '''TITLE = "Listed Mining"

# Two markets, each with its own tabs. They are not merged into one set of
# charts: the TMX export carries commodity, geography and trading data that the
# ASX export simply does not have, so a shared view would be mostly blank
# columns pretending to be a comparison.
MARKETS = [
    ("tsx", "TSX / TSXV"),
    ("asx", "ASX"),
]

# (tab label, filename). Order defines tab order.
# A filename of None means the tab is generated, not read from markdown.
TABS = {
    "tsx": [
        ("Stage 1 · Dataset", "stage1-dataset.md"),
        ("Stage 1 · Numbers", "stage1-numbers.md"),
        ("Stage 1 · Charts", None),
        ("Stage 2", "stage2.md"),
    ],
    "asx": [
        ("Dataset", "asx-dataset.md"),
        ("Numbers", "asx-numbers.md"),
    ],
}''',
)

# ── header markup ───────────────────────────────────────────────────────────
sub(
    '''  <div class="head-inner">
    <h1 class="site">{title}</h1>
    <nav role="tablist">{tabs}</nav>
  </div>''',
    '''  <div class="head-inner">
    <div class="head-top">
      <h1 class="site">{title}</h1>
      <div class="seg market">{markets}</div>
    </div>
    <nav role="tablist">{tabs}</nav>
  </div>''',
)

# ── header CSS ──────────────────────────────────────────────────────────────
sub(
    '''  background: var(--panel);''',
    '''  background: var(--panel);
}

.head-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}
.seg.market { display: flex; gap: 4px; }
.seg.market button {
  appearance: none;
  font: inherit;
  font-size: 13px;
  padding: 5px 14px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink-soft);
  border-radius: 5px;
  cursor: pointer;
}
.seg.market button:hover { border-color: #c9c9c9; color: var(--ink); }
.seg.market button[aria-pressed="true"] {
  color: var(--ink);
  border-color: #b0b0b0;
  font-weight: 550;''',
)

# ── JS: market switching ────────────────────────────────────────────────────
sub(
    '''const panels = [...document.querySelectorAll('main section')];''',
    '''// Market first, then tab. Switching market swaps which tab bar is live and
// lands on that market's first tab — carrying the tab index across would point
// at a tab the other market does not have.
let market = document.querySelector('.seg.market button').dataset.market;

function showMarket(m) {
  market = m;
  document.querySelectorAll('.seg.market button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.market === m));
  document.querySelectorAll('[data-market]').forEach(el => {
    if (el.tagName === 'BUTTON' && el.closest('.seg.market')) return;
    el.hidden = el.dataset.market !== m;
  });
  const first = [...document.querySelectorAll(`nav [data-market="${m}"]`)][0];
  if (first) first.click();
}

document.querySelectorAll('.seg.market button').forEach(btn =>
  btn.addEventListener('click', () => showMarket(btn.dataset.market)));

const panels = [...document.querySelectorAll('main section')];''',
)

# tab switching must stay inside the active market
sub(
    '''  panels.forEach((p, n) => p.hidden = n !== i);''',
    '''  panels.forEach((p, n) => p.hidden = n !== i || p.dataset.market !== market);''',
)

sub(
    '''const start = panels.findIndex(p => '#' + p.id === location.hash);
show(start > -1 ? start : 0, false);''',
    '''const start = panels.findIndex(p => '#' + p.id === location.hash);
if (start > -1) {
  showMarket(panels[start].dataset.market);
  show(start, false);
} else {
  showMarket(market);
}''',
)

# ── render ──────────────────────────────────────────────────────────────────
sub(
    '''    tabs_html, panels_html = [], []
    for i, (label, filename) in enumerate(TABS):
        if filename is None:''',
    '''    tabs_html, panels_html, markets_html = [], [], []
    flat = [(mk, label, filename)
            for mk, _ in MARKETS for label, filename in TABS[mk]]

    for mk, mlabel in MARKETS:
        markets_html.append(
            f'<button data-market="{mk}" '
            f'aria-pressed="{"true" if mk == MARKETS[0][0] else "false"}">'
            f'{mlabel}</button>')

    for i, (mk, label, filename) in enumerate(flat):
        if filename is None:''',
)

sub(
    '''        selected = "true" if i == 0 else "false"
        tabs_html.append(
            f'<button role="tab" aria-selected="{selected}" '
            f'aria-controls="{slug}">{label}</button>'
        )
        panels_html.append(
            f'<section id="{slug}" role="tabpanel"'
            f'{"" if i == 0 else " hidden"}>{body}</section>'
        )

    sources = " · ".join(f for _, f in TABS if f)''',
    '''        selected = "true" if i == 0 else "false"
        tabs_html.append(
            f'<button role="tab" aria-selected="{selected}" '
            f'data-market="{mk}" '
            f'{"" if mk == MARKETS[0][0] else "hidden "}'
            f'aria-controls="{slug}">{label}</button>'
        )
        panels_html.append(
            f'<section id="{slug}" role="tabpanel" data-market="{mk}"'
            f'{"" if i == 0 else " hidden"}>{body}</section>'
        )

    sources = " · ".join(f for _, _, f in flat if f)''',
)

sub(
    '''    footer = (
        f"Rendered from {sources} — edit the markdown and re-run "
        f"<code>src/build_report.py</code>. "
        f"Size and trading data as at 30 June 2026; "
        f"commodity and property as at 31 July 2026."
    )''',
    '''    footer = (
        f"Rendered from {sources} — edit the markdown and re-run "
        f"<code>src/build_report.py</code>. "
        f"TSX/TSXV size and trading as at 30 June 2026, commodity and property "
        f"as at 31 July 2026; ASX as at 26 August 2026. "
        f"Canadian and Australian dollars are never converted."
    )''',
)

sub(
    '''        tabs="".join(tabs_html),''',
    '''        markets="".join(markets_html),
        tabs="".join(tabs_html),''',
)

io.open(p, "w", encoding="utf-8").write(s)
print("patched build_report.py for markets")
