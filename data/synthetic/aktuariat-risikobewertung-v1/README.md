# Synthetisches aktuarielles Risikobewertungs-Testset v1

**Zweck:** Wiederverwendbarer Übungs- und Pipeline-Benchmark für Versicherungs-/Aktuardaten.

**Datenart:** Vollständig synthetisch; keine echten Personen, Versicherer, Verträge, Schäden oder Marktbeobachtungen.

**Standardlauf:** Seed `20261120`, 2.000 stabile Policenprofile je Unfalljahr, Unfalljahre 2019–2024, Bewertungs-Cut-off 2025-12-31.

> Dieses Testset ist ein kompakter **Nichtleben-Benchmark (Motor und Property)** für Daten-, Modell-, Szenario- und Visualisierungstests. Es ist **keine** Tarifgrundlage, Marktstatistik, Prognose, aufsichtsrechtliche Kalibrierung oder Aussage über ein reales Unternehmen. Die Szenariowerte und Markt-/Katastrophendaten sind ausdrücklich synthetisch. Mit rund 738 Schadenfällen ist es nicht für glaubwürdige Tail-, VaR-/TVaR- oder Kapital-Kalibrierung ausgelegt; dafür sind wesentlich mehr, zweckgerechte Daten und fachliche Validierung erforderlich.

## Aufbau

- [`clean/`](clean/) — saubere Eingabetabellen mit Manifest, Prüfsummen und Zeilenzahlen.
- [`reference/`](reference/) — Ground Truth und erwartete Kontrollsummen für Backtests. **Niemals als Modellinput oder Feature verwenden.**
- [`defect_fixtures/`](defect_fixtures/) — Kopie der Eingabetabellen mit sechs absichtlich eingebauten Fehlerklassen. Nur für Datenqualitäts-/Negativtests.

Beim Standardlauf entstehen aktuell ungefähr **12.000 Policen-Jahreszeilen**, **700–800 Schadenfälle** und **3.000–4.000 Entwicklungszeilen**. Die tatsächlichen Zahlen stehen im Manifest; Änderungen an Seed, Generatorversion oder Policenzahl können sie verändern.

### Tabellen in `clean/`

| Datei | Körnung / Verwendung |
|---|---|
| `policy_exposure.csv` | Eine Zeile je Policen-/Unfalljahr; Exposition, Produkt, Region, Risikoband, Prämie und weitere Risikomerkmale. |
| `claim_header.csv` | Eine Zeile je gemeldetem synthetischem Schaden; Policenbezug, Ereignis-/Meldedatum, Typ und Status. |
| `claim_development.csv` | Eine Zeile je Schaden und Entwicklungsalter; kumulierte Zahlung, Fallreserve, Incurred sowie synthetische Brutto-/Rückversicherungs-/Netto-Sichten. |
| `reinsurance_treaties.csv` | Vereinfachte per-claim Excess-of-Loss-Verträge mit Gültigkeit, Attachment, Limit und Anteil. |
| `market_curve.csv` | Monatliche synthetische Zins-/Spreadkurven nach Laufzeit; ausdrücklich keine EIOPA- oder Marktdaten. |
| `catastrophe_events.csv` | Drei künstliche Ereignisse für Kumul-, Join- und Geotests. |
| `scenario_catalog.csv` | Basis-, Einzel-, Kombi- und Reverse-Stress-Vorlagen. Schocks sind nicht regulatorisch kalibriert. |
| `manifest.json` | Version, Seed, Cut-off, Zeilenzahlen und SHA-256 je CSV. |

`reference/claim_ultimate_truth.csv` enthält den synthetischen Ultimate je Schaden; `reference/policy_year_truth.csv` enthält erwartete Frequenz und erzeugte Schadenanzahl je Exposition. Diese Werte sind ausschließlich für eine externe Auswertung/Backtest gedacht.

## Generieren und prüfen

Voraussetzung: Python 3.10+; keine Drittanbieterpakete erforderlich.

```bash
python scripts/generate_testset.py
python scripts/validate_dataset.py data/synthetic/aktuariat-risikobewertung-v1/clean
python scripts/validate_dataset.py data/synthetic/aktuariat-risikobewertung-v1/defect_fixtures --expect-defects
```

Eigener Seed oder Umfang, ohne die Standardausgabe zu überschreiben:

> Der Generator prüft vorab alle drei Profilordner, lehnt fremde Einträge ab und erstellt neue Profile in einem temporären `.testset-*`-Ordner im Ziel. Bei einem Fehler während des Austauschs werden alte Profile zurückverschoben. Nicht parallel auf dasselbe Ziel schreiben. Nach einem harten Prozessabbruch nicht sofort erneut generieren: Der temporäre Ordner kann unter `backups/` noch alte Profile enthalten; vor Wiederherstellung ggf. beide Stände separat sichern.

```bash
python scripts/generate_testset.py \
  --seed 20261121 \
  --policies 3000 \
  --output-dir /tmp/aktuariat-testset-v1
```

Der Validator muss beim sauberen Bestand `PASS` und beim Fehlerprofil mit `--expect-defects` die erwarteten Fehlerklassen melden. Ohne `--expect-defects` ist `defect_fixtures/` erwartungsgemäß **nicht bestanden**.

## Wiederverwendung und Grenzen

- Der Generator ist die maßgebliche Spezifikation; CSV-Dateien sind vorgefertigte, direkt nutzbare Fixtures.
- Eingaben sind nach `policy_exposure.csv`, `claim_header.csv` und optional `claim_development.csv` getrennt. `market_curve`, Rückversicherung, Ereignisse und Szenarien sind optionale Zusatzdomänen.
- Der Generator bildet eine einfache Frequenz-/Schwere-Struktur mit zeitlichem Trend, heterogenen Segmenten, Tail, Entwicklungsständen, Rückversicherung und synthetischen Ereignisclustern ab. Er bildet keine reale Marktverteilung, aufsichtsrechtliche Formel oder vollständige Deckungs-/Bedingungslogik ab.
- Der Umfang deckt keine Lebens-/Krankenversicherung, Mortalität, Langlebigkeit oder vollständige Solvency-II-Kapitalberechnung ab; dafür ist ein separates fachliches Testset nötig.
- Die Ground-Truth-Dateien nicht in Trainingsdaten oder Features einführen; sie würden Target Leakage erzeugen.
- Für Testfälle mit echtem Drittanbieter-/Unternehmensmaterial die Anleitung [`docs/anleitung-rohdaten-fuer-dritte.md`](../../../docs/anleitung-rohdaten-fuer-dritte.md) verwenden. Echtdaten gehören nicht in diesen Ordner.
- Das Repository enthält derzeit keine allgemeine Lizenzdatei. Vor einer Weitergabe außerhalb des Repositorys die Lizenz-/Nutzungsbedingungen für Generator und synthetische Dateien festlegen.
