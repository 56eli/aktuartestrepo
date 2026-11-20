# Aktuarieller Testplan zur Risikobewertung

Praxisorientierter Rahmen für komplexe Versicherungs-/Aktuardaten, Modellvalidierung, Stress- und Szenarioanalysen sowie eine prüfbare Ergebnisdarstellung. Dazu gibt es jetzt einen reproduzierbaren synthetischen Benchmark und eine Anleitung zur sicheren Aufnahme weiterer Rohdaten.

- [Testplan, Datenquellen und Präsentationsanforderungen](docs/testplan-risikobewertung-aktuar.md)
- [Wiederverwendbares synthetisches Testset](data/synthetic/aktuariat-risikobewertung-v1/README.md)
- [Anleitung für Dritte: Rohdaten und zusätzliche Tests einführen](docs/anleitung-rohdaten-fuer-dritte.md)
- [Manifest-Template](templates/partner_manifest.template.json)
- [Field-Mapping-Template](templates/field_mapping.template.csv)
- [Datenwörterbuch-Template](templates/data_dictionary.template.csv)
- [Testfall-Template](templates/test_case.template.md)

Testset generieren/prüfen (Python 3.10+, nur Standardbibliothek):

```bash
python scripts/generate_testset.py
python scripts/validate_dataset.py data/synthetic/aktuariat-risikobewertung-v1/clean
python scripts/validate_dataset.py data/synthetic/aktuariat-risikobewertung-v1/defect_fixtures --expect-defects
python -m unittest discover -s tests
```

**Hinweis:** Der fachliche Rahmen nutzt Deutschland/EU als Ausgangspunkt. Der Testdatensatz ist vollständig synthetisch und kein Tarif-, Solvenz- oder Marktbenchmark. Echtdaten sind nicht enthalten und gehören nicht ins Git-Repository.

## Benchmark verifizieren

```bash
python scripts/run_benchmark.py --report docs/benchmark-probelauf.html
```

Der Lauf generiert v1 in einem temporären Verzeichnis, vergleicht alle drei Profile
bytegenau, prüft die Defekte nach Code/Datei/Schlüssel und rechnet die Referenzsummen
nach. Der [grafische Probelauf](docs/benchmark-probelauf.html) zeigt die beobachtete
Schadenfrequenz je Policenjahr; er ist keine Modellvalidierung. CI prüft auch die
Reproduzierbarkeit des HTML-Berichts. Siehe [Umsetzungsplan](docs/umsetzungsplan-industriestandard.md).

## Visuelle Testfixtures

Die [Diagrammgalerie für Versicherungsrisiken](docs/visualisierung/index.html)
enthält berechnete Beispiele und getrennt gekennzeichnete Lehrgrafiken.
Offline öffnen oder im Browser als PDF drucken. Neu erzeugen:

```bash
python scripts/render_gallery.py
```

[Visueller Abnahmeauftrag und Abdeckung](docs/visualisierung/abnahme.md).
