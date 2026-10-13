> Historical report / plan. The current production decision is spaCy + Regex only; see [PRODUCTION-DETECTOR.md](PRODUCTION-DETECTOR.md). Alternative detector code and evidence are preserved on `archive/cpu-pii-evaluation-2026-10-13`. Older install and backend-selection instructions below are not current release instructions.

# UI-Review: Local Privacy Guard und Requesty Privacy Guard

11. Oktober 2026 · Zielgruppe: datenschutzinteressierte Privatanwender

## Ergebnis

Beide Plugins bieten eine sinnvolle Kombination: Local Privacy Guard reduziert erkannte persönliche Angaben vor unterstützten Modellaufrufen und konfiguriert lokale Embeddings. Requesty Privacy Guard beschränkt die externe Verarbeitung anhand ausgewählter Anforderungen und Katalogangaben. Die derzeitige Oberfläche setzt jedoch zu viel technisches Vorwissen voraus. Die höchste Priorität haben verständliche Schutzgrenzen, erkennbare Zustände und ein geführter Einrichtungsablauf.

Die vier bereitgestellten Screenshots sowie die README-Dateien und UI-Quellen beider Repositories bilden die Grundlage. Die Screenshots 1–2 zeigen Requesty, 3–4 Local Privacy Guard. Aussagen über Kontrast und Überlauf beziehen sich auf diese Ansichten; das Review ist kein Nachweis der tatsächlichen Datenschutzwirkung und kein vollständiger Accessibility-Audit.

## Nutzergruppen und Bedürfnisse

| Aufgabe | Technisch unversierte Nutzer | Technisch versierte Nutzer |
| --- | --- | --- |
| Schutz einrichten | Verständliche Voreinstellungen und ein geführter Ablauf | Einzelne Bedingungen gezielt konfigurieren |
| Wirkung verstehen | Was bleibt lokal, was wird extern verarbeitet? | Prüfumfang, Datenquelle und Grenzen nachvollziehen |
| Probleme lösen | Ursache und nächster Schritt direkt am betroffenen Feld | Kataloggründe, Diagnosen und Konfigurationsdetails |
| Alltag | Wenige Entscheidungen, sichtbarer Status | Schneller Zugriff auf erweiterte Einstellungen |

Empfohlen wird eine gemeinsame Oberfläche mit Basisansicht und aufklappbaren erweiterten Einstellungen. Technische Erfahrung ist kein Schutzniveau: Auch unversierte Nutzer können strenge Anforderungen haben. Basisansicht und Expertenansicht müssen dieselben Schutzregeln verwenden.

## Befunde und Prioritäten

### P0: Gewünschte Einstellung und wirksamen Schutz unterscheiden

Häkchen zeigen die Konfiguration, aber nicht, ob Sprachmodelle geladen, Änderungen gespeichert oder neue Einstellungen bereits wirksam sind. Die Oberfläche muss Entwurf, gespeichert, geprüft und aktiv unterscheiden. Ein Entwurf darf keine grüne Gesamtaussage wie „Alles geschützt“ auslösen. Bei Änderungen müssen frühere Prüfungen sichtbar ungültig werden.

Für Local Privacy Guard sollen Konfigurationszusammenfassung und lokale Beispielprüfung getrennt bleiben. Eine erfolgreiche Beispielprüfung belegt nur das Ergebnis für dieses Beispiel und die geladenen Komponenten. Sie beweist keine vollständige Erkennung und keinen Schutz aller Datenwege.

### P0: Lokale Verarbeitung verständlich abgrenzen

Lokale Embeddings bedeuten, dass die Berechnung für die Gedächtnissuche lokal erfolgt. Sie schließen nicht aus, dass ein Hilfsmodell abgerufene Gedächtnisinhalte extern verarbeitet. Lokale Chats, Logs und Caches bleiben ebenfalls von den externen Speicherregeln getrennt. Die UI muss diese Unterschiede in kurzen, sichtbaren Sätzen erklären.

„Anonymisieren“ sollte durch „Erkannte persönliche Angaben ersetzen“ ergänzt oder ersetzt werden. Die Erkennung kann Angaben übersehen; verbleibender Text kann weiterhin Rückschlüsse erlauben. Nicht unterstützte Modell-, Tool- und Drittanbieterpfade dürfen nicht durch allgemeine Schutzversprechen mit eingeschlossen werden.

### P0: Requesty-ZDR als blockierende Bedingung darstellen

Die derzeit nicht verifizierbare ZDR-Eigenschaft der Requesty-Organisation steht neben normalen Schutzoptionen. Das vermittelt eine vergleichbare Verfügbarkeit. Die Option gehört in den erweiterten Bereich, mit der direkten Aussage: „Anfragen blockieren, solange Requesty-ZDR nicht verifiziert werden kann. Aktuell blockiert diese Einstellung alle Anfragen.“ Bereits aktivierte Anforderungen müssen weiterhin sichtbar sein, auch wenn der Bereich geschlossen ist. Modellanbieter-ZDR, Requesty-ZDR und lokale Speicherung sind getrennte Sachverhalte.

### P1: Requesty als geführten Ablauf gestalten

Der Ablauf umfasst Schlüssel speichern, Anforderungen speichern, Katalog laden, zwei Modelle wählen, testen, Preset erstellen und anschließend auswählen. Diese Abhängigkeiten sind bisher vor allem in Fließtext versteckt. Empfohlen sind nummerierte Abschnitte mit klaren Voraussetzungen und persistenten Rückmeldungen:

1. Zugang verbinden: Schlüssel speichern und Status anzeigen.
2. Datenschutz festlegen: Region, Speicherung und Training erklären und speichern.
3. Modelle wählen: passende Modelle anbieten und Haupt-/Hilfsmodell erklären.
4. Verbindung testen: künstliche Daten und mögliche Kosten unmittelbar nennen.
5. Konfiguration erstellen: Erstellung bestätigen und Auswahl im Testchat erklären.

Technisch getestet ist nicht unabhängig auf Datenschutz geprüft. Erstellt ist nicht aktiv. Schutzanforderungen dürfen niemals automatisch gelockert werden, um Ergebnisse zu erzeugen.

### P1: Lesbarkeit und Bedienbarkeit verbessern

Die Sprachauswahl in Screenshot 3 läuft rechts aus dem sichtbaren Bereich; Beschriftungen stehen dicht zusammen. Ein umbrechendes Raster mit gut anklickbaren Labels behebt das Problem. Bei schmalen Fenstern müssen Felder untereinander erscheinen. Lange Modellnamen brauchen Platz oder müssen vollständig einsehbar sein.

Überschriften und Feldnamen erscheinen kontrastarm. Weniger verschachtelte Rahmen, klare Überschriften, deutliche Fokusmarkierungen und größere Klickflächen verbessern Orientierung. Normaler Text soll mindestens 4,5:1 Kontrast erreichen; große Schrift und wesentliche Bedienelemente mindestens 3:1. Status darf nicht allein über Farbe vermittelt werden. Tastaturbedienung und 200 Prozent Zoom gehören zur Abnahme.

### P1: Leere Zustände, Fehler und deaktivierte Aktionen erklären

Vor dem Katalogladen: „Noch keine Modelle geladen“. Nach erfolgreichem Laden ohne passende Modelle: „Keine Modelle erfüllen die Anforderungen“. Bei einer Suche ohne Treffer ist stattdessen die Suche als Ursache zu nennen. Ablehnungsgründe müssen erreichbar bleiben.

Deaktivierte Aktionen benötigen sichtbare Voraussetzungen, beispielsweise „Wähle beide Modelle“ oder „Anforderungen geändert: Katalog erneut laden“. Erfolgs- und Fehlermeldungen sollten im Dialog bestehen bleiben und zusätzlich für assistive Technologien angekündigt werden.

## Konkrete Änderungen für Local Privacy Guard

- Basisansicht: Schutzschalter, Verhalten bei Erkennung, Sprachen und lokale Gedächtnissuche.
- Erweiterter Bereich: Regex, spaCy, Protokollierung, Zuordnung, Embedding-Modell und Startprüfungen.
- „Nur protokollieren“ deutlich als unverändertes Senden kennzeichnen.
- Bei ausgeschaltetem Schutz abhängige Optionen sperren, bestehende Werte erhalten.
- Englische Basissprache sichtbar als immer enthalten darstellen.
- Lokalen Test mit festem künstlichem Beispiel anbieten; keine echten Eingaben, externe Modellanfragen oder Downloads auslösen.
- Fehlende Sprachmodelle und Beispielergebnis sichtbar anzeigen. Ein erfolgreich erkanntes E-Mail-Beispiel darf fehlende Namenserkennung nicht verdecken.
- Änderungen an Sprachen oder Embedding-Modell mit Neustarthinweis versehen. Nicht behaupten, dass jeder fehlende Sprachdownload automatisch beim Neustart erfolgt; das muss zur tatsächlichen Implementierung passen.

## Konkrete Änderungen für Requesty Privacy Guard

- Nummerierte Abschnitte und eine zusammenhängende Einrichtungsübersicht.
- Kurze, verständliche Bezeichnungen; technische Memory- und Vision-Details aufklappbar.
- API-Schlüsselstatus als gespeichert oder unbekannt anzeigen; gespeichert ist nicht erfolgreich verbunden.
- Katalogprüfung und synthetischen Modelltest voneinander unterscheiden.
- Zeitstempel und Herkunft der Kataloginformationen anzeigen, aber den UI-Zeitstempel nicht als Laufzeitgültigkeit oder Auditnachweis darstellen.
- Ausgeschlossene Modelle mit Gründen und unterstützten Fähigkeiten anzeigen.
- Nach Schlüssel-, Richtlinien- oder Modellauswahländerung Testfreigabe zurücknehmen; verspätete Antworten nach Schließen oder Änderung ignorieren.
- Nach Erstellung „Noch nicht aktiviert“ und den nächsten Schritt anzeigen.
- Wiederherstellung in den erweiterten Bereich mit verständlicher Folgenbeschreibung.

## Umsetzungsplan und Abnahme

**Erstes Paket:** beide Einstellungsoberflächen überarbeiten, Schutzgrenzen korrigieren, lokale Beispielprüfung ergänzen, Requesty-Zustände und Abhängigkeiten sichtbar machen. Vorhandene Backend-Schutzregeln, Speicherverwaltung und Preset-Aktivierung bleiben maßgeblich.

**Weitere Produktarbeit:** eine gemeinsame chatbezogene Übersicht braucht Framework-Integration mit dem tatsächlich aktiven Preset, Projekt und Profil. Sprachwechsel der gesamten UI, verlässliche aktuelle Preise sowie unabhängig verifizierte Anbieterangaben benötigen eigene Datenquellen beziehungsweise Produktentscheidungen. Sie dürfen nicht durch erfundene Werte oder abgeleitete Schutzbehauptungen ersetzt werden.

Abnahme des ersten Pakets:

1. Beide Nutzergruppen können die wichtigsten Funktionen ohne Kenntnis von PII, NER, Embeddings oder Utility erklären.
2. Sprachauswahl und wichtige Aktionen bleiben bei schmalen Ansichten und Zoom erreichbar.
3. Ein blockierender Requesty-ZDR-Schalter hat bereits vor Auswahl eine klare Folgenbeschreibung.
4. Nicht geladen, leer, Suche ohne Treffer, Fehler und geänderte Anforderungen sind unterscheidbar.
5. Änderungen und verspätete Antworten können keine veraltete Testfreigabe erzeugen.
6. Die lokale Vorschau nutzt echte Filterlogik, ausschließlich künstliche Daten und keine externen Modellaufrufe.
7. Vorhandene Regressionstests bestehen; neue Zustandsübergänge werden mit Fehler- und Änderungsfällen getestet.
8. Ein isolierter Browserlauf prüft Labels, Tastaturbedienung, Layout und den vollständigen Einrichtungsablauf. Ein Mocklauf wird ausdrücklich von realen Backend- und Live-Modelltests unterschieden.

## Quellen

- https://github.com/mgr-de/a0-local-privacy-guard
- https://github.com/mgr-de/a0-local-privacy-guard/blob/main/webui/config.html
- https://github.com/mgr-de/a0-requesty-privacy-guard
- https://github.com/mgr-de/a0-requesty-privacy-guard/blob/main/webui/config.html
- https://github.com/mgr-de/a0-requesty-privacy-guard/blob/main/webui/requesty-store.js
- Vier bereitgestellte Screenshots der Einstellungsdialoge.

Das Dokument trennt beobachtete Probleme, Empfehlungen und Abnahmekriterien. Live-Modelltests können technische Kompatibilität prüfen, liefern aber keinen unabhängigen Nachweis über tatsächliche Verarbeitung, Speicherung oder Training beim Anbieter.


## Ergänzung: Agentenprofil als verbindliche Grenze

Nach der Klärung vom 11. Oktober 2026 wurde die Umsetzung auf ausdrücklich konfigurierte Agentenprofile begrenzt. Globale Einstellungen reichen nicht zur Aktivierung. Requesty verwendet profilbezogene Schlüssel und Modell-Setups; Local Privacy Guard schreibt keine gemeinsamen Embedding-Vorlagen mehr um. Geschützte Profile erhalten getrennte Memory-Ordner. Die Oberfläche führt zur Profilauswahl und zeigt Erstellen und Aktivieren getrennt. Bestehende gemeinsame Erinnerungen werden nicht automatisch kopiert. Details und Grenzen stehen in [PROFILE-SCOPE-REVIEW.md](PROFILE-SCOPE-REVIEW.md).
