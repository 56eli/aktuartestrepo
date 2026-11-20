# Visueller Abnahmeauftrag für Versicherungsanalysen

Die [Galerie](index.html) ist eine Sammlung reproduzierbarer Darstellungsfixtures,
kein Soll-Layout und keine fachliche Freigabe. Der [Testplan](../testplan-risikobewertung-aktuar.md#93-diagrammportfolio-für-komplexe-ergebnisse)
beschreibt den Rahmen. Eine Abgabe darf sinnvolle Alternativen zur Musterform wählen,
muss die jeweilige Entscheidungsfrage aber mindestens genauso gut beantworten.

| Mindestansicht für einen vollständigen Testauftrag | Abnahmeaufgabe | Vorliegende Fixture / benötigte Erweiterung |
|---|---|---|
| Management-Einseiter und Maßnahmen | Ergebnis, Einschränkung, Entscheidung und Verantwortlichkeit trennen; keinen ungeprüften Teil als bestanden melden. | Prüfmatrix in Galerie; individuelle Entscheidung und Freigabeverantwortung aus dem Testauftrag ergänzen. |
| Datenqualität und Abstimmung | Saubere und negative Ergebnisse unterscheiden; Fehler zu Regel, Datei und Schlüssel zurückverfolgen. | Berechnete Prüfmatrix. |
| Pricing / Portfolio / Tail | Nenner und Fallzahl nach Segment zeigen; Überschreitung, Rechtszensierung oder Unsicherheit nicht als Kalibrierung ausgeben. | Produktfrequenz und empirische Überschreitungsanteile. Histogramm, Kalibrierungsplot mit Holdout und Poisson- bzw. geeignete alternative Intervalle benötigen einen eigenen Modellauftrag. |
| Reservierung | Unfalljahr, Entwicklungsbasis, beobachtete und fehlende Zellen zeigen; keine fehlende Zelle als Null. | Berechnete Snapshot-Tabelle. Für Methodenvergleich ein kohärentes Stichtagsdreieck und Referenzmethoden bereitstellen. |
| Rückversicherung / Kumul | Überleitung additiv abstimmen; räumliche Exposition und Ereignisschäden nicht verwechseln. | Ultimate-Wasserfall und Regionsbalken. Für Choroplethen vergleichbare Grenzen und passende Gebietsnenner liefern. |
| ALM / Liquidität | Laufzeit, Bewertungsdatum, Zinsbasis und Einheiten; Zahlungsstrom und Barwert auseinanderhalten. | Synthetische Zinskurve. Duration-Gap oder Liquiditätsleiter benötigen Asset-/Liability-Cashflows. |
| Stress / Kapital / ORSA | Basisszenario, Schocks, Einheit und Ergebnis trennen; bei Interaktionen Mehrfaktorszenarien zeigen; Prognoseband definieren. | Lehrbeispiele: Matrix, Tornado und Fan-Chart. Vollständige Ergebnisrechnung erfordert Portfolio und Kapital-/Liquiditätsmodell. |
| Leben und Kranken | Exposition / Bezugsgröße, Altersstruktur und Produktbasis offenlegen; Lehrwerte nicht als Tarifparameter nutzen. | Illustrative Biometriekurve und Leistungsausgaben je Versichertenjahr. |
| Governance | Ordinale Risiko-Matrix nicht als quantitatives Kapitalmaß interpretieren; Maßnahmen mit Eigentümer und Termin ergänzen. | Qualitative Matrix als Lehrbeispiel. |

## Abnahmeregeln

- **Pflicht:** Titel mit Aussage, Einheit, Population, Zeitraum/Stichtag, Datenherkunft, Rechenmethode und Status („berechnet“, „Illustration“, „nicht geprüft“) sind unmittelbar nachvollziehbar. Eine Illustration zählt nicht als ausgeführte Risikorechnung.
- **Pflicht:** Kernwerte müssen aus einer unabhängigen Rechnung reproduzierbar sein. Die Prüfung soll mindestens eine Rate samt Nenner, eine Überleitung und den Umgang mit fehlenden Werten umfassen. Ein Abweichungsgrund muss dokumentiert werden.
- **Pflicht:** Null und fehlend unterscheiden; bei Balken Nullbasis; Vorzeichen und Rundung sichtbar. Farbe nie als einziges Signal. Rohwerte in Tabelle oder Text verfügbar machen.
- **Präsentationsprüfung:** Übersichtsseite für Entscheidungen, Detailgrafiken für Fachreview, maschinenlesbare Tabellen für die Nachprüfung. Offline und im PDF-Druck auf abgeschnittene Achsen, Legenden und Tabellen prüfen.
- **Reproduzierbarkeit:** `python scripts/render_gallery.py --output /tmp/galerie.html` und Ausgabe mit `docs/visualisierung/index.html` vergleichen. Wird eine zusätzliche Grafik verlangt, Datenbedarf und Abnahmerechnung vor dem Implementieren definieren.
