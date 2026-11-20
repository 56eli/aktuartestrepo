#!/usr/bin/env python3
"""Render the standalone insurance visualisation gallery (standard library only)."""
from collections import Counter, defaultdict
from decimal import Decimal as D
from html import escape
from pathlib import Path
import argparse

from run_benchmark import BASE
from validate_dataset import read_rows, validate

OUT = BASE.parents[2] / 'docs/visualisierung/index.html'
COLORS = ('#076956', '#285d9b', '#a94b19')


def svg(label, body):
    return f'<svg viewBox="0 0 680 280" role="img" aria-label="{escape(label)}">{body}</svg>'


def text(x, y, value, anchor='end'):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}">{escape(str(value))}</text>'


def bars(label, pairs):
    max_value = max(v for _, v in pairs) or 1
    step = 220 / len(pairs)
    body = ''
    for i, (key, value) in enumerate(pairs):
        y = 25 + i * step
        width = 420 * float(value / max_value)
        body += text(155, y + 15, key) + f'<rect x="168" y="{y:.2f}" width="{width:.2f}" height="19" fill="{COLORS[0]}"/>'
        body += text(177 + width, y + 15, f'{value:.2f}', 'start')
    return svg(label, body)


def line(label, xs, series, band=None):
    values = [float(v) for _, ys in series for v in ys] + ([v for bounds in band for v in bounds] if band else [])
    low, high = min(values), max(values)
    span = high - low or 1
    x = lambda i: 72 + 565 * i / (len(xs) - 1)
    y = lambda v: 223 - 184 * (float(v) - low) / span
    coords = lambda seq: ' '.join(f'{x(i):.2f},{y(v):.2f}' for i, v in seq)
    body = ''
    for step in range(5):
        v = low + step * span / 4
        body += f'<path d="M72 {y(v):.2f}H637" stroke="#cbd8de"/>' + text(66, y(v) + 4, f'{v:.2f}')
    if band:
        polygon = coords(list(enumerate(band[0])) + list(reversed(list(enumerate(band[1])))))
        body += f'<polygon points="{polygon}" fill="#b9ded7"/>'
    for i, (name, seq) in enumerate(series):
        dash = ('none', '8 4', '2 4')[i]
        body += f'<polyline points="{coords(enumerate(seq))}" stroke="{COLORS[i]}" stroke-width="3" stroke-dasharray="{dash}" fill="none"/>'
        body += text(74 + i * 190, 267, f'{("━", "┄", "··")[i]} {name}', 'start')
    body += ''.join(text(x(i), 244, key, 'middle') for i, key in enumerate(xs))
    return svg(label, body)


def matrix(headers, rows, heat=False):
    def cell(v):
        if v is None:
            return '<td class="missing">—</td>'
        shade = ''
        if heat and isinstance(v, (int, D)):
            shade = ' style="background:' + ('#f8e4da' if v < 0 else '#d5eee8' if v > 0 else '#f3f5f7') + '"'
        return f'<td{shade}>{escape(str(v))}</td>'
    return ('<div class="scroll"><table><thead><tr>' + ''.join(f'<th scope="col">{escape(h)}</th>' for h in headers)
            + '</tr></thead><tbody>' + ''.join(f'<tr><th scope="row">{escape(str(r[0]))}</th>'
            + ''.join(cell(v) for v in r[1:]) + '</tr>' for r in rows) + '</tbody></table></div>')


def tornado(rows):
    limit = max(abs(v) for _, a, b in rows for v in (a, b))
    origin = 402
    body = f'<path d="M{origin} 25V225" stroke="#475867"/>'
    for i, (name, down, up) in enumerate(rows):
        y = 43 + i * 59
        body += text(216, y + 19, name)
        for v, color, dy in ((down, COLORS[1], 0), (up, COLORS[2], 19)):
            endpoint = origin + 140 * v / limit
            body += f'<rect x="{min(origin, endpoint):.2f}" y="{y+dy}" width="{abs(endpoint-origin):.2f}" height="16" fill="{color}"/>'
            body += text(endpoint + (5 if v >= 0 else -5), y + dy + 13, f'{v:+d}', 'start' if v >= 0 else 'end')
    body += text(origin, 244, '0 · Basis', 'middle') + text(240, 268, 'Oben: Down · unten: Up · Mio. EUR', 'start')
    return svg('Tornado: Abweichung vom Basisfall in Millionen Euro', body)


def waterfall(brutto, zediert, netto):
    scale = float(brutto) / 165
    net = float(netto) / scale
    body = '<path d="M55 220H635" stroke="#475867"/>'
    body += f'<rect x="85" y="55" width="100" height="165" fill="{COLORS[0]}"/>'
    body += f'<rect x="475" y="{220-net:.2f}" width="100" height="{net:.2f}" fill="{COLORS[1]}"/>'
    body += f'<path d="M185 55H280M380 {220-net:.2f}H475" stroke="#475867" stroke-dasharray="4 3"/>'
    body += f'<rect x="280" y="55" width="100" height="{165-net:.2f}" fill="{COLORS[2]}"/>'
    for x, y, title, value in [(135, 55, 'Brutto', brutto), (330, 55, 'Zession', -zediert), (525, 220-net, 'Netto', netto)]:
        body += text(x, 247, title, 'middle') + text(x, y-12, f'{value:,.2f}', 'middle')
    return svg('Ultimate-Wasserfall in EUR: Brutto minus Zession ergibt Netto', body)


def render():
    clean = BASE / 'clean'
    issues, tables = validate(clean)
    if issues:
        raise ValueError(f'Clean-Profil ungültig: {issues[:3]}')
    defects, _ = validate(BASE / 'defect_fixtures')
    policies, claims, dev = (tables[f'{name}.csv'] for name in ('policy_exposure', 'claim_header', 'claim_development'))
    sources = 'Daten: synthetischer Standardbestand v1 · Seed 20261120 · Stichtag 31.12.2025'
    cards = []

    def card(title, area, note, content, demo=False):
        i = len(cards) + 1
        tag = 'ILLUSTRATION · KEIN BEFUND' if demo else 'AUS SYNTHETISCHEN DATEN BERECHNET'
        cards.append((title, f'<section id="g{i}"><p class="eyebrow">{i:02} / {area} · {tag}</p><h2>{title}</h2><p>{note}</p>{content}<p class="source">{("Quelle: frei definierte Lehrwerte" if demo else sources)}</p></section>'))

    card('Die sechs Negativfälle bleiben sichtbar', 'DATENQUALITÄT', 'Clean: keine Befunde. Negativprofil: erkannte Regeln mit Datei und Schlüssel. Die Tabelle ist kein Nachweis ungeprüfter Regeln.',
         matrix(['Regel', 'Datei', 'Schlüssel'], [(i['code'], i['file'], i['row_key']) for i in sorted(defects, key=lambda i: i['code'])]))
    exp, count = defaultdict(D), Counter()
    for r in policies:
        exp[r['product']] += D(r['exposure_years'])
    for r in claims:
        count[r['product']] += 1
    card('Frequenz und Datenbasis nach Produkt', 'PRICING', 'Gemeldete Schäden je 100 Expositionsjahre (2019–2024). Deskriptiv, ohne Mixbereinigung oder Konfidenzintervall.',
         bars('Schadenfrequenz je 100 Expositionsjahre', [(k, 100 * count[k] / exp[k]) for k in sorted(exp)])
         + matrix(['Produkt', 'Schäden', 'Expositionsjahre'], [(k, count[k], f'{exp[k]:.2f}') for k in sorted(exp)]))
    calendar_grid = defaultdict(dict)
    by_claim_year = {}
    for r in dev:
        k = (r['claim_id'], int(r['valuation_date'][:4]))
        if k not in by_claim_year or r['valuation_date'] > by_claim_year[k]['valuation_date']:
            by_claim_year[k] = r
    for (_, year), r in by_claim_year.items():
        origin = int(r['accident_year'])
        calendar_grid[origin].setdefault(year, []).append(D(r['gross_paid_cumulative_eur']))
    triangle = []
    for origin in sorted(calendar_grid):
        row = [origin]
        for age in range(7):
            amounts = calendar_grid[origin].get(origin + age)
            row.append(f'{sum(amounts)/1000:.1f} ({len(amounts)})' if amounts else None)
        triangle.append(row)
    card('Abwicklungsstände sind ungleich dicht', 'RESERVIERUNG', 'Kalenderjahr minus Unfalljahr; je Schaden nur der letzte vorhandene Snapshot des jeweiligen Kalenderjahrs, ohne Fortschreibung. Zellen: Brutto-Paid in Tsd. EUR (Schäden). Kein vollständiges Stichtagsdreieck; nicht für Chain-Ladder verwenden.',
         matrix(['Unfalljahr', *[f'+{i} J.' for i in range(7)]], triangle))
    ultimate = read_rows(BASE / 'reference/claim_ultimate_truth.csv')[1]
    totals = [sum(D(r[f'{basis}_ultimate_eur']) for r in ultimate) for basis in ('gross', 'ceded', 'net')]
    card('Die Zession überleitet Brutto zu Netto', 'RÜCKVERSICHERUNG', 'Ultimate in EUR, alle 738 Referenzschäden. Zession ist ein Abzug. Referenzdaten ausschließlich zur Auswertung; kein Modellinput.', waterfall(*totals))
    losses = sorted(D(r['gross_ultimate_eur']) for r in ultimate)
    exceed = [(threshold, 100 * sum(v > threshold for v in losses) / len(losses)) for threshold in (500, 1000, 2000, 3000, 5000, 10000)]
    card('Hohe Einzelschäden sind selten', 'SCHWERE / TAIL', 'Empirische Überschreitungsanteile in Prozent an festen Brutto-Ultimate-Schwellen (EUR). n = 738, keine Tail- oder Kapital-Kalibrierung.',
         bars('Prozent der Schäden oberhalb der Schwelle', [(f'> {t} EUR', p) for t, p in exceed]))
    regions = defaultdict(D)
    for r in policies:
        regions[r['region']] += D(r['exposure_years'])
    card('Exposition nach synthetischer Region', 'KUMUL', 'Anteil an allen Expositionsjahren (%), keine Gefahren- oder Schadenkarte. Die Regionen besitzen keine geografischen Grenzen.',
         bars('Expositionsanteil nach Region (%)', [(k, 100 * regions[k] / sum(regions.values())) for k in sorted(regions)]))
    curve = defaultdict(dict)
    for r in tables['market_curve.csv']:
        curve[r['valuation_date']][int(r['maturity_years'])] = D(r['risk_free_rate_pct'])
    last = max(curve)
    tenors = sorted(curve[last])
    card('Die synthetische Kurve nach Laufzeit', 'ALM', f'Risikofreier Zins in Prozent, Kurvenstichtag {last}. Laufzeitkategorien gleichabständig; keine Markt-/EIOPA-Kurve.',
         line('Synthetische Zinsstruktur in Prozent', [f'{t} J.' for t in tenors], [('Zins', [curve[last][t] for t in tenors])]))
    card('Szenarien können gegenläufig wirken', 'STRESS / KAPITAL', 'Beispiel: Änderung gegen Basis in Prozentpunkten. Orange = negativ, Grün = positiv, — = nicht gerechnet. Keine berechneten Kapitalwirkungen.',
         matrix(['Szenario', 'Solvenzquote Δ pp', 'Liquiditätsquote Δ pp'], [('Basis', 0, 0), ('Schadeninflation', -12, -4), ('Zinsanstieg', 5, -2), ('Kombi', -9, None)], heat=True), True)
    card('Welche Annahme bewegt das Ergebnis?', 'SENSITIVITÄT', 'Frei gewählte Einzelfaktor-Effekte auf eine Ergebniskennzahl (Mio. EUR), sortiert nach Spannweite. Keine Interaktionen.',
         tornado([('Schadeninflation ±5 pp', 9, -11), ('Frequenz ±10 %', 7, -8), ('Zins ±100 bp', -3, 4)]), True)
    card('Projektionsunsicherheit wächst mit dem Horizont', 'PLANUNG / ORSA', 'Lehrwerte in Prozent für eine Solvenztrajektorie. Das Band illustriert P10–P90; es wurde nicht statistisch geschätzt.',
         line('Illustrative Median-Solvenzquote und P10–P90-Band', ['Basis', '+1 J.', '+2 J.', '+3 J.'], [('Median', [155, 151, 148, 144])], ([155, 138, 125, 112], [155, 165, 174, 180])), True)
    card('Risiken zur Eskalation priorisieren', 'GOVERNANCE', 'Qualitative Eintritts- und Wirkungsklassen, keine Kapitalmessung. Leere Zelle bedeutet hier: kein Beispiel zugeordnet.',
         matrix(['Eintritt / Wirkung', 'Begrenzt', 'Mittel', 'Hoch'], [('Häufig', None, 'Datenlieferung', None), ('Möglich', None, 'Storno', 'Schadeninflation'), ('Selten', None, None, 'Kumulereignis')]), True)
    card('Sterblichkeit steigt über die Altersgruppen', 'LEBEN / BIOMETRIE', 'Frei gewählte jährliche Sterbewahrscheinlichkeiten je 1.000 exponierte Personen. Keine Sterbetafel und keine Rechnungsgrundlage.',
         line('Illustrative Sterbewahrscheinlichkeit je 1.000', ['40', '50', '60', '70', '80'], [('Basis', [1, 2, 5, 13, 38]), ('Stress', [1.2, 2.4, 6, 15.6, 45.6])]), True)
    card('Leistungsausgaben und Bestand getrennt betrachten', 'KRANKEN / LEISTUNG', 'Frei gewählte Leistungsausgaben je Versichertenjahr (EUR) und exponierte Versichertenjahre. Keine Tarif- oder Beitragsaussage.',
         bars('Leistungsausgaben in EUR je Versichertenjahr', [('18–39', 720), ('40–59', 1320), ('60+', 2440)])
         + matrix(['Alter', 'Versichertenjahre'], [('18–39', 1700), ('40–59', 1350), ('60+', 810)]), True)
    nav = ''.join(f'<li><a href="#g{i}">{t}</a></li>' for i, (t, _) in enumerate(cards, 1))
    return f'''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Versicherungsrisiken · Diagrammgalerie</title><style>
*{{box-sizing:border-box}}body{{background:#edf2f4;color:#172d3b;font:16px/1.5 system-ui;margin:0}}main{{max-width:960px;margin:auto;padding:24px}}header{{background:#132e3b;color:white;padding:36px;border-radius:16px}}h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.05;margin:.3em 0}}h2{{margin:.25em 0}}section,nav{{background:white;border:1px solid #cedbe1;border-radius:14px;padding:24px;margin:18px 0}}.eyebrow,.source{{font-size:.82rem;font-weight:700;letter-spacing:.04em}}.eyebrow{{color:#076956}}header .eyebrow{{color:#a5e4d7}}a{{color:#22578d}}nav ol{{columns:2}}svg{{width:100%;max-height:330px}}svg text{{font:14px system-ui;fill:#172d3b}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{text-align:left;border-bottom:1px solid #cedbe1;padding:.45em}}thead{{background:#eef5f7}}.missing{{background:#f1f2f5;color:#505c65}}.source{{color:#475867}}@media(max-width:620px){{nav ol{{columns:1}}}}@media print{{body{{background:white}}section{{break-inside:avoid}}nav{{display:none}}header{{color:#172d3b;background:white}}}}
</style><main><header><p class="eyebrow">AKTUARIAT · VISUELLE TESTFIXTURES</p><h1>Versicherungsrisiken präsentieren</h1><p>Dreizehn Musteransichten von Datenqualität bis Risikogovernance. Synthetische Befunde und frei definierte Lehrbeispiele sind getrennt gekennzeichnet.</p></header>
<nav aria-label="Diagrammübersicht"><ol>{nav}</ol></nav>{''.join(c for _, c in cards)}
<footer><p>Erzeugen: <code>python scripts/render_gallery.py</code> · Keine Unternehmens- oder Aufsichtsaussage.</p></footer></main></html>\n'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    args.output.write_bytes(render().encode('utf-8'))
