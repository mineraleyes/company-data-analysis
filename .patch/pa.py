# -*- coding: utf-8 -*-
import io, sys

p = sys.argv[1]
s = io.open(p, encoding="utf-8").read()


def sub(a, b):
    global s
    assert a in s, "NOT FOUND: " + a[:70]
    s = s.replace(a, b, 1)


sub("""import charts""", """import asx_charts
import charts""")

sub('''    "asx": [
        ("Dataset", "asx-dataset.md"),
        ("Numbers", "asx-numbers.md"),
    ],''',
    '''    "asx": [
        ("Dataset", "asx-dataset.md"),
        ("Numbers", "asx-numbers.md"),
        ("Charts", None),
    ],''')

# the generated tab now depends on which market it belongs to
sub('''        if filename is None:
            body = charts.section_html()
            slug = "charts"''',
    '''        if filename is None:
            body = charts.section_html() if mk == "tsx" else asx_charts.section_html()
            slug = "charts" if mk == "tsx" else "asx-charts"''')

# static charts: route asx_* to the ASX module
sub('''            return charts.static_chart(name)''',
    '''            if name.startswith("asx_"):
                return asx_charts.static_chart(name)
            return charts.static_chart(name)''')

io.open(p, "w", encoding="utf-8").write(s)
print("patched build_report.py")
