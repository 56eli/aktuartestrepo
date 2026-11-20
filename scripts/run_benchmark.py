#!/usr/bin/env python3
"""Regenerate and verify v1, then write a deterministic standalone HTML report."""
import argparse
import json
import tempfile
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from generate_testset import generate, DEFAULT_SEED, DEFAULT_POLICY_COUNT
from validate_dataset import read_rows, validate

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/synthetic/aktuariat-risikobewertung-v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def benchmark():
    with tempfile.TemporaryDirectory() as folder:
        run = Path(folder)
        generate(run, DEFAULT_POLICY_COUNT, DEFAULT_SEED)
        for profile in ('clean', 'reference', 'defect_fixtures'):
            names = {p.name for p in (run / profile).iterdir()}
            require(names == {p.name for p in (BASE / profile).iterdir()}, f'{profile}: Dateiliste weicht ab')
            for name in sorted(names):
                require((run / profile / name).read_bytes() == (BASE / profile / name).read_bytes(),
                        f'{profile}/{name}: Bytes weichen ab')
        issues, tables = validate(run / 'clean')
        require(not issues, f'Clean-Profil: {issues[:5]}')
        defects, _ = validate(run / 'defect_fixtures')
        catalog = read_rows(run / 'defect_fixtures/defect_catalog.csv')[1]
        require(Counter((i['code'], i['file'], i['row_key']) for i in defects) ==
                Counter((i['validator_code'], i['file_name'], i['row_key']) for i in catalog),
                'Unerwartete Defektbefunde')
        reference = run / 'reference'
        controls = json.loads((reference / 'expected_control_totals.json').read_text(), parse_float=Decimal)
        exposures = tables['policy_exposure.csv']
        claims = tables['claim_header.csv']
        truth = read_rows(reference / 'claim_ultimate_truth.csv')[1]
        policy_truth = read_rows(reference / 'policy_year_truth.csv')[1]
        require({r['claim_id'] for r in truth} == {r['claim_id'] for r in claims} and len(truth) == len(claims),
                'Schadenreferenz nicht 1:1')
        require({r['exposure_id'] for r in policy_truth} == {r['exposure_id'] for r in exposures}
                and len(policy_truth) == len(exposures), 'Policenreferenz nicht 1:1')
        counts = Counter(r['exposure_id'] for r in claims)
        require(all(int(r['generated_claim_count']) == counts[r['exposure_id']] for r in policy_truth),
                'Schadenanzahl je Exposition weicht ab')
        actual = {name: len(rows) for name, rows in tables.items()}
        actual.update({'claim_ultimate_truth.csv': len(truth), 'policy_year_truth.csv': len(policy_truth)})
        require(actual == controls['row_counts'], 'Kontrollzeilenzahlen weichen ab')
        for key, rows, field in (
            ('total_exposure_years', exposures, 'exposure_years'),
            ('total_gross_premium_eur', exposures, 'gross_premium_eur'),
            *((f'{basis}_ultimate_loss_eur', truth, f'{basis}_ultimate_eur') for basis in ('gross', 'ceded', 'net')),
        ):
            require(sum(Decimal(r[field]) for r in rows) == controls[key], f'Kontrollsumme weicht ab: {key}')
        require(len(claims) == controls['reported_claim_count'], 'Schadenanzahl weicht ab')
        exposure_by_year = defaultdict(Decimal)
        for row in exposures:
            exposure_by_year[row['policy_year']] += Decimal(row['exposure_years'])
        claims_by_year = Counter(row['policy_year'] for row in claims)
        return controls, [(year, claims_by_year[year], exposure_by_year[year]) for year in sorted(exposure_by_year)]


def report(controls, years):
    frequencies = [(year, n, e, 100 * n / e) for year, n, e in years]
    chart = '\n'.join(f'<tr><th scope="row">{year}</th><td>{n}</td><td>{e:.2f}</td>'
                      f'<td><meter min="0" max="{max(10, *(x[3] for x in frequencies)):.2f}" value="{f:.4f}"></meter> {f:.2f}</td></tr>'
                      for year, n, e, f in frequencies)
    return f'''<!doctype html>
<html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Probelauf · Aktuariat-Benchmark v1</title>
<style>
body{{background:#f3f6fa;color:#172b44;font:16px/1.55 system-ui;margin:0}}main{{max-width:830px;margin:2rem auto;padding:1rem}}
section{{background:white;border:1px solid #dce4ee;border-radius:12px;padding:1.2rem;margin:1rem 0}}h1{{font-size:2.2rem;line-height:1.1}}
strong{{color:#076449}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:.5rem;border-bottom:1px solid #dce4ee}}meter{{width:65%;accent-color:#076449}}code{{overflow-wrap:anywhere}}
</style>
<main><header><p>SYNTHETISCHER NICHTLEBEN-BENCHMARK · V1</p><h1>Reproduzierbarer Probelauf</h1>
<p>Seed {controls['seed']} · Bewertungsstichtag {controls['evaluation_cutoff']}</p></header>
<section><h2><strong>PASS</strong> · Reproduzierbarkeit</h2>
<ul><li>Alle drei Datenprofile bytegleich zum versionierten Stand</li><li>Clean-Profil ohne Befund; sechs Defekte am erwarteten Datensatzschlüssel</li>
<li>Zeilenzahlen, Exposition, Prämie und Ultimate-Summen rechnerisch abgestimmt</li></ul></section>
<section><h2>Beobachtete Schadenfrequenz je Policenjahr</h2><p>Gemeldete Schäden pro 100 Expositionsjahre; unmodellierte Bestandskennzahl.</p>
<table><thead><tr><th>Jahr</th><th>Schäden</th><th>Expositionsjahre</th><th>Frequenz</th></tr></thead><tbody>{chart}</tbody></table></section>
<section><h2>Kontrollsummen</h2><p>{controls['reported_claim_count']} Schäden · {controls['total_exposure_years']:.2f} Expositionsjahre</p>
<p>Ultimate (EUR): {controls['gross_ultimate_loss_eur']:.2f} brutto · {controls['ceded_ultimate_loss_eur']:.2f} zediert · {controls['net_ultimate_loss_eur']:.2f} netto.</p>
<p>Ground Truth dient nur der Abstimmung. Kein Marktvergleich, keine Modellvalidierung und keine regulatorische Freigabe.</p></section>
<p>Neu erzeugen: <code>python scripts/run_benchmark.py --report docs/benchmark-probelauf.html</code></p></main></html>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='Optionales HTML-Ausgabeziel')
    args = parser.parse_args()
    result = benchmark()
    if args.report:
        args.report.write_bytes(report(*result).encode('utf-8'))
    print('PASS: Bytevergleich, Datenqualität und Kontrollsummen')


if __name__ == '__main__':
    main()
