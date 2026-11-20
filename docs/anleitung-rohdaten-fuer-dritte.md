# Anleitung für Dritte: zusätzliche Rohdaten sicher und prüfbar einführen

**Zweck:** Externe Teams, Datenlieferanten oder Reviewer sollen zusätzliche Daten für neue Tests bereitstellen können, ohne die wiederverwendbare synthetische Baseline zu verändern oder unbemerkt unzulässige Daten ins Repository einzubringen.

> **Grundregel:** Rohdaten bleiben unverändert und geschützt. Die synthetische Baseline ist ein eigener, reproduzierbarer Benchmark. Neue Rohdaten bekommen eine eigene Dataset-ID und Version; sie überschreiben niemals `data/synthetic/aktuariat-risikobewertung-v1/clean/`.

## 1. Verantwortlichkeiten und Sicherheit vor dem Import

Bevor ein Datensatz übergeben oder lokal verarbeitet wird, muss die verantwortliche Stelle bestätigen:

1. **Zweck und Umfang:** Welche Tests/Entscheidungen sollen unterstützt werden? Welche Population, Sparte, Länder, Stichtage und Ausschlüsse gelten?
2. **Nutzungsrecht:** Quelle, Vertrag/Lizenz, interne Analyseberechtigung, Weitergabe und zulässige Aufbewahrung sind geklärt.
3. **Datenschutz und Schutzbedarf:** Personenbezug, besondere Kategorien, Pseudonymisierung, Zugriffsberechtigung, Löschdatum und zulässige Ausgabestufe sind dokumentiert. Für Freigabe/Unklarheiten Datenschutz, Recht und Compliance einbeziehen.
4. **Sicherer Transport:** Freigegebener verschlüsselter Transfer und restriktiver Arbeitsbereich; keine Rohdaten über Chat, E-Mail, öffentliches Issue oder öffentliches Git.
5. **Echtdaten getrennt halten:** Echtdaten nicht in Beispielen, Präsentations-Screenshots, Logs, Stacktraces oder `reference/` speichern. Keine direkten IDs, Namen, Adressen, Freitexte oder zu feine Geo-/Zeitkombinationen an Testierende geben.

Das Repository ignoriert `data/incoming/` standardmäßig über `.gitignore`. Das ist eine Vorsichtsmaßnahme, **keine** Datenschutzfreigabe. Vor jedem Commit den Git-Status und den Inhalt der zu commitenden Dateien prüfen. Nur explizit freigegebene, synthetische oder wirksam anonymisierte Fixtures dürfen versioniert werden.

## 2. Ablage- und Versionskonvention

Pro Lieferant/Team und fachlichem Snapshot einen neuen, unverwechselbaren Ordner verwenden:

```text
data/incoming/<team-oder-lieferant>/<dataset-id>-<version>/
  raw/                       # unveränderte Quelle; lokal geschützt, Git-ignoriert
  normalized/                # kanonische Testtabellen; geschützt, falls noch personenbeziehbar
  metadata/
    manifest.json            # Dataset Card, Stand, Nutzungsrecht, Kontrollsummen
    field_mapping.csv        # Source-to-target-Mapping
    data_dictionary.csv      # Begriffe, Typen, Einheiten, Werte und Nullsemantik
    test_scope.md            # Zweck, Grenzen, Ansprechpartnerrolle
  results/<run-id>/          # Validierungsberichte, keine Rohdatenkopien
```

- `<version>` ändert sich mindestens bei neuem Extraktionsstichtag, geänderter Population, Quelle, Felddefinition, Mapping oder wesentlicher Bereinigung.
- Rohdateien niemals umschreiben. Korrekturen/Normalisierungen erfolgen in einem versionierten Transformationsschritt, der Eingabe-Hashes und Codeversion protokolliert.
- Keine Änderungen an den vorhandenen synthetischen `clean/`-Daten, um einen neuen Partnerdatensatz „passend“ zu machen.
- Datumsformat im Normalmodell: `YYYY-MM-DD`; Dezimalpunkt, keine Tausendertrennzeichen; UTF-8; eindeutige Kopfzeile; keine stillen Typwechsel.

## 3. Fachliches Mapping in ein gemeinsames Datenmodell

Die Namen unten sind ein **kanonischer Beispielvertrag** für Nichtleben-/Schaden-Erfahrungstests. Der fachliche Sinn ist wichtiger als eine erzwungene Umbenennung. Wenn ein Quellsystem etwas anderes meint, Definition abgleichen oder ein eigenes Schema und einen passenden Validator dokumentieren.

### 3.1 `policy_exposure.csv` — Policen-/Expositionsbasis

**Körnung:** eine Zeile je Police, Deckung, Produkt und Beobachtungsperiode. Mehrere Jahre derselben Police erhalten unterschiedliche `exposure_id`.

| Feld | Mindestbedeutung / Regel |
|---|---|
| `exposure_id` | Stabiler eindeutiger Schlüssel der Expositionszeile; keine Kunden-ID. |
| `policy_id` | Pseudonymer, über Tabellen konsistenter Policenschlüssel; nur verwenden, wenn für Join/Panel erforderlich. |
| `policy_year` | Beobachtungs-/Unfall-/Vertragsjahr eindeutig definieren; nicht bloß eine unkommentierte Zahl. |
| `inception_date`, `expiry_date` | Anfang und Ende des tatsächlich beobachteten Deckungszeitraums; Reihenfolge und Jahresabgrenzung prüfen. |
| `exposure_years` | Exposition in dokumentierter Jahreseinheit; Day-count-Methode und Teiljahre festhalten; größer null. |
| `product`, `region`, `risk_band` | Versionierte Codes mit Codebuch; Region angemessen aggregieren und kleine Zellen prüfen. |
| `gross_premium_eur` | Verdiente/gebuchte Prämie eindeutig benennen und abgrenzen; Währung und nominal/real dokumentieren. Nicht als Synonym für geschriebenes Prämienvolumen verwenden. |
| `currency` | Währung je Betrag; bei der gelieferten Baseline EUR. Umrechnung nicht ohne FX-Quelle, Stichtag und Formel. |
| `insured_value_eur` | Nur falls sachlich vorhanden; Definition und Bewertungsstichtag angeben. Für nicht relevante Produkte leer/„nicht anwendbar“ nach dokumentierter Nullsemantik. |
| optionale Merkmale | Nur zulässige und für den Zweck geeignete Variablen; Datenherkunft, Zeitraum, Kategorien und Verwendungsberechtigung nennen. |

### 3.2 `claim_header.csv` — Schadenstamm

**Körnung:** eine Zeile je Schadenfall, nicht je Zahlung oder Reservebuchung.

| Feld | Mindestbedeutung / Regel |
|---|---|
| `claim_id` | Eindeutiger pseudonymer Schadenfall-Schlüssel. |
| `exposure_id` | Bezug auf die versicherte Expositionszeile; nicht nur auf einen beliebigen Kunden. Orphans separat ausweisen. |
| `loss_date` | Schadeneintritt/Unfall, nicht Melde- oder Buchungsdatum. |
| `report_date` | Eingang/Meldung; muss fachlich nach oder am Schadenereignis liegen, sofern keine Ausnahme erklärt ist. |
| `claim_type`, `cat_event_id`, `claim_status_at_cutoff` | Versionierte Ursache/Ereignis-/Statuscodes; bei nicht katastrophenbezogenen Schäden `cat_event_id` leer lassen. |
| `currency` | Währung der Schadenwerte bzw. gemeinsame Reportingwährung; jeder Betrag muss dazu passen. |
| Ergebnisfelder | Ultimate, spätere Meldung oder sonstige nach dem Bewertungsstichtag bekannte Information nicht als Modellfeature in frühere Zeitpunkte zurückspielen. Outcome/Truth getrennt halten. |

### 3.3 `claim_development.csv` — Reserve-/Abwicklungsstände (optional)

**Körnung:** eine Zeile je Schadenfall und Bewertungsstichtag bzw. Entwicklungsalter. Diese Tabelle nur einführen, wenn Reservierung/Entwicklung geprüft werden soll.

- `claim_id`, `valuation_date`, `development_months` bilden den zeitlichen Kontext; eindeutigen zusammengesetzten Schlüssel festlegen.
- `gross_paid_cumulative_eur` ist kumulierte Zahlung bis zum Stand, nicht einzelne Transaktion.
- `gross_case_reserve_eur` ist Fallreserve zu genau diesem Stichtag.
- `gross_incurred_eur` sollte der fachlich gewählten Definition `paid + case reserve` entsprechen; Abweichungen erklären.
- Brutto, Rückversicherung und Netto getrennt führen; Rückflüsse/Regresse und Rückversicherungsforderungen nicht doppelt abziehen.
- Historische Bewegungen nicht durch den aktuellsten Stand ersetzen. Für rohe Transaktionen bei Bedarf eine gesonderte, unveränderte Bewegungsdatei behalten und die Aggregation/Entwicklung reproduzierbar ableiten.

### 3.4 Optionale Tabellen

- `reinsurance_treaties.csv`: Treaty-ID, Deckungsperiode, Produkt, Attachment, Limit, Anteil, Währung und Vertragslogik. Sonderregeln wie Aggregate Limits/Wiederauffüllung beschreiben.
- `market_curve.csv`: Stichtag, Laufzeit, Rate/Spread, Währung, Quelle und Kurvenversion. Synthetische, historische, beobachtete und regulatorische Kurven strikt unterscheiden.
- `catastrophe_events.csv`: eindeutige Ereignis-ID, Gefahrenart, Datum, räumliche Aggregation, Quelle und Unsicherheit; Event-Daten sind nicht automatisch versicherte Schäden.
- `scenario_catalog.csv`: Szenario-ID, Treiber, Schock, Einheit, Horizont, Abhängigkeit, Status und Begründung. Beispielwerte aus dem Testset sind nicht als regulatorische Schocks zu verwenden.

Für Lebens-/Kranken-, Markt-, Kredit- oder operationelle Risiken ist dieses Nichtleben-Schema nicht automatisch passend. Ein eigenes fachliches Datenmodell mit gleichwertiger Datenkarte, Lineage, Kontrollen und Tests aufsetzen, statt unpassende Schadenfelder zu erzwingen.

## 4. Mapping, Transformation und Datenqualität

### Schritt 1 — Quellinventar erstellen

- Je Quelldatei Tabellenname, Körnung, Zeilenanzahl, Extraktionszeit, Stichtag, Zeitraum, Quellsystem, Eigentümerrolle und SHA-256 erfassen.
- Primär-/Fremdschlüssel, Datumsfelder, Währung, Einheiten, Nullcodes, Korrekturen, Duplikate, verspätete Meldungen und historische Schemaänderungen benennen.
- Kontrollsummen aus dem Quellsystem sichern (z. B. Policenanzahl, Exposition, Prämien, Zahlungen, Fallreserven) und ihre Abgrenzung dokumentieren.

### Schritt 2 — Mapping freigeben

Für jedes Zielfeld Mapping in [`templates/field_mapping.template.csv`](../templates/field_mapping.template.csv) erfassen; die fachlichen Definitionen zusätzlich im [`Datenwörterbuch-Template`](../templates/data_dictionary.template.csv) festhalten:

- Quelltable/-feld und Zielfield
- Quell-/Zieltyp, Einheit, Währung und Datumssemantik
- Transformation, FX-/Umrechnungsquelle und Rundung
- Null-/Sondercode-Behandlung
- Validierungsregel und fachliche Ansprechrollen
- Rückverfolgbarkeit zur Quelle und bekannte Einschränkung

Felder nicht durch Namensähnlichkeit gleichsetzen. Beispiel: „Meldejahr“ ist nicht zwingend „Unfalljahr“, „gebuchte Prämie“ nicht zwingend „verdiente Prämie“ und „Incurred“ nicht zwingend „Ultimate“.

### Schritt 3 — Normalisieren, nicht bereinigen, ohne Spur

- Rohdaten unverändert aufbewahren und Ergebnisse über eine dokumentierte Transformation erzeugen.
- Personenbeziehbare Schlüssel nur nach freigegebenem Verfahren pseudonymisieren; einfacher ungesalzener Hash von Kundennummern reicht wegen möglicher Rückrechnung oft nicht.
- Einheiten nicht überschreiben: Beträge in Cent in Euro konvertieren, dann Quell-/Zielformel, Rundung und Validierung festhalten. Felder mit Suffix `_eur` erst nach echter, dokumentierter EUR-Umrechnung befüllen; bei anderer Reportingwährung Schema und Validator anpassen, niemals nur Feldnamen oder Währungscode umetikettieren.
- Fehlend, nicht anwendbar, null, unbekannt und nicht erhoben voneinander unterscheiden. Keine fehlenden Werte pauschal mit 0 auffüllen.
- Unplausible, doppelte und nicht verknüpfte Zeilen zunächst markieren/quarantänisieren. Jede Bereinigung mit Zahl, Ursache, Regel, Entscheidung und Ergebniswirkung protokollieren.
- Zeitliche Features ausschließlich aus Informationen bilden, die zum jeweiligen Modell-/Bewertungsstichtag verfügbar gewesen wären.

### Schritt 4 — Abstimmen und negative Fixtures bereitstellen

Vor Modellierung müssen Quellsystem-Kontrollsummen und Normalmodell erklärt überleitbar sein. Für jede neue Datenregel wenigstens diese drei Fälle erzeugen:

1. **gültiger Normalfall** (muss bestehen),
2. **Grenzfall** (z. B. Teiljahr, Nullreserve, Rundungsgrenze oder verspätete Meldung; erwartete Behandlung vorgeben),
3. **Fehlerfall** (z. B. doppelte ID, falsche Einheit, ungültiges Datum oder verwaister Schlüssel; muss erkannt oder ausdrücklich quarantänisiert werden).

Fixtures nur synthetisch/anonymisiert und klein halten. Für jede Regel erwartet/nicht erwartet, Fehlercode, Schweregrad und zuständige Rolle nennen.

## 5. Manifest und Begleitdokumente

Kopie von [`templates/partner_manifest.template.json`](../templates/partner_manifest.template.json) als `manifest.json` verwenden. Mindestens ausfüllen:

- eindeutige Dataset-ID und Version
- Dataset-Eigentümerrolle, Quellsystem, Zweck und Population
- Extraktionsdatum, Bewertungsstichtag, Beobachtungszeitraum und Zeitsemantik
- Reporting-Währung, Preisbasis und Geographie
- Nutzungsrecht, Datenschutzstatus, Schutzklasse, Zugriff und Löschdatum
- je Datei Körnung, Zeilenzahl, SHA-256, Schlüssel und Quellkontrollsummen
- Transformationen, bekannte Grenzen und erforderliche Freigaben

Im Manifest keine Kundennamen, personenbezogenen Ansprechpartnerdaten oder vertraulichen Inhalte aufnehmen. Eine Rollenbezeichnung genügt.

## 6. Validator ausführen und mit Tests ergänzen

Nach dem Mapping die kanonischen Dateien und das Manifest in einen Arbeitsordner legen; dann aus dem Repository-Verzeichnis ausführen:

```bash
python scripts/validate_dataset.py data/incoming/<team>/<version>/normalized
```

Der Validator prüft die Kernstruktur für Policen-/Expositions- und Schadendaten, Schlüssel, positive Exposition, Datumsgrundregeln, Währungsabgleich mit `reporting_currency`, optionale Entwicklungsstände sowie Manifest-Zeilenzahlen/Prüfsummen. Bei reinen Frequenz-/Schwere-Tests kann `claim_development.csv` entfallen. Für andere Risikotypen sind zusätzliche fachliche Validatoren nötig.

Der Validator ist ein Startpunkt, kein vollständiger Data-Governance- oder Aktuariatsreview. Er prüft beispielsweise nicht automatisch, ob Modellmerkmale rechtlich zulässig sind, ob die Population repräsentativ ist, ob der Vertrag korrekt abgebildet wurde oder ob die gewählte Methode fachlich angemessen ist.

Neue Testfälle im [`Testfall-Template`](../templates/test_case.template.md) dokumentieren. Eindeutige IDs verwenden, zum Beispiel `EXT-<TEAM>-DQ-001` oder `EXT-<TEAM>-MODEL-001`. Jeden neuen Test mit Eingabeversion, Formel, Einheit, vorab freigegebenem Akzeptanzkriterium, Soll-/Ist-Ergebnis, Fehlerwirkung und Evidenz versehen. Schwellen nie nach Sichtung des Resultats so ändern, dass ein gewünschtes Ergebnis entsteht.

## 7. Freigabe für zusätzliche Tests

Vor Aufnahme in eine gemeinsame Testkampagne müssen mindestens folgende Punkte bestätigt sein:

- [ ] Zweck, Scope, Dataset-ID und Version sind freigegeben.
- [ ] Datenquelle, Nutzungsrecht, Datenschutzstatus, Zugriff und Löschung sind geklärt.
- [ ] Quell- und Zielfelder sowie Nullsemantik, Zeitbezug, Einheiten und Währung sind dokumentiert.
- [ ] Kontrollsummen sind abgestimmt oder Abweichungen quantifiziert.
- [ ] Rohdaten bleiben geschützt und nicht versehentlich versioniert.
- [ ] Keine Truth-/Zukunftsfelder leaken in Modellfeatures.
- [ ] Saubere, Grenz- und Fehler-Fixtures existieren und haben erwartete Testresultate.
- [ ] Data-/Model-Owner und unabhängige Reviewer haben Ergebnis und Grenzen bestätigt.
- [ ] Ergebnisse sind durch Run-ID, Codeversion und Datenhash reproduzierbar.

Für den Gesamt-Testplan, Datenquellen, Standards, Szenarien und Präsentationsregeln siehe [`docs/testplan-risikobewertung-aktuar.md`](testplan-risikobewertung-aktuar.md). Für den ausführbaren synthetischen Benchmark siehe [`data/synthetic/aktuariat-risikobewertung-v1/README.md`](../data/synthetic/aktuariat-risikobewertung-v1/README.md).
