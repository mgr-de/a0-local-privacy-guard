# Erweiterte PII-Tests – Ergebnisse 11.10.2026

Repository-Ausgabe: Dieser Bericht dokumentiert die gemessenen Ergebnisse. Die genannten JSON-Protokolle und Screenshots liegen im separaten lokalen Testpaket und werden hier nicht mit eingecheckt. Der experimentelle Wiederholungscode liegt unter `tools/privacy_benchmark`; er ist kein Bestandteil des Plugin-Laufzeitpfads.

## Was der Schutz leisten soll

Originalnamen und Kontaktdaten sollen in der lokalen Browser-Anzeige lesbar bleiben. Vor dem Versand an externe Modelle werden erkannte Angaben durch eindeutige Platzhalter ersetzt; passende Platzhalter in Antworten werden ausschließlich lokal für die Anzeige zurückübersetzt. Sichtbare Originalnamen sind daher kein Fehler. Kritisch sind unmaskierte Werte in ausgehenden Modellanfragen.

Automatische Maskierung reduziert das Offenlegungsrisiko, garantiert aber keine vollständige Anonymisierung. Regex, Namenserkennung und modellbasierte Verfahren können Angaben übersehen oder harmlose Wörter falsch erkennen. Kurzformen, Spitznamen, sprachliche Varianten und indirekt identifizierende Informationen bleiben besondere Risiken. Fehlende Erkennungsmodelle und Aufrufpfade ohne Filter sind dagegen behebbare Implementierungsfehler.

Vorgeschlagener Hinweis für die Oberfläche: **„Erkannte personenbezogene Angaben werden vor dem Versand an externe KI-Dienste lokal maskiert. Die Erkennung kann Angaben übersehen. Originalwerte bleiben für dich sichtbar; eine vollständige Anonymisierung ist nicht garantiert.“** Für einen lokalen Modus muss zusätzlich geprüft werden, dass auch Hintergrundmodelle, Embeddings und Werkzeuge keine entsprechenden Daten extern übertragen.

### Requesty als zusätzliche Schutzschicht

Requesty dokumentiert schnelle und modellbasierte PII-Scanner. Laut Anbieter ist die ML-Variante auf höhere Genauigkeit ausgelegt; ein belastbarer Vergleich mit unserem Filter erfordert dieselben Testfälle. Guardrails sind auch außerhalb von Enterprise verfügbar. „Report“ verändert den Inhalt nicht; „Mask“ ersetzt erkannte Werte vor dem Modellanbieter und übersetzt passende Antwortwerte zurück. [Requesty Guardrails](https://docs.requesty.ai/features/guardrails)

Beim gehosteten Gateway verlassen die Originaldaten den Rechner bereits auf dem Weg zu Requesty. Serverseitige Maskierung schützt daher die nächste Weitergabe, ersetzt aber keine lokale Maskierung. Zero Data Retention betrifft Speicherung und Caching, nicht die Übertragung oder notwendige Verarbeitung. [Requesty Datenschutz](https://www.requesty.ai/privacy)

Für unser Ziel bleibt lokale Maskierung vor jedem externen Versand die erste Schutzschicht; serverseitige Erkennung kann ergänzen. Ob sie zusätzliche Angaben erkennt, welche Sprachen sie abdeckt und wie sie Personen über lange Gespräche konsistent zuordnet, ist noch nicht getestet. Die bisherigen acht Requesty-Aufrufe bewerten nicht den Requesty-PII-Service.

Die Testserie ist implementiert und abgeschlossen: 240 lokale Vergleichsaufrufe, 40 Browser-Nachrichten mit 40 zusätzlichen Utility-Aufrufen, jeweils 40 Aufrufe für Reasoning, LLM Guard und automatische Beziehungsauswertung, ein nativer Agentenablauf sowie acht erfolgreiche Requesty-Aufrufe. Speicher, Profilgrenzen, Kontextkürzung und Wiederaufnahme nach einem Server-Neustart wurden ergänzend geprüft. Die Produktionsintegration eines neuen Filters ist damit noch nicht freigegeben.

## Aufbau

Vier fiktive Personen mit jeweils Name, E-Mail, Telefonnummer und prüfsummengültiger synthetischer IBAN. Ereignisse: Heirat, Trennung, neue Geschäftspartnerschaft, Schuld von 125 Euro, Zahlung und Ende der Partnerschaft. Nach jeweils zehn Nachrichten werden Zusammenfassungen angefordert. Je 40 Nachrichten auf Deutsch, Englisch und gemischt, mit dem bisherigen Filter sowie dem experimentellen Presidio-Adapter. Gemma 3 4B über vorhandenes Ollama; echte Agent-Zero-Modellfunktionen und ausgehende Transportnachrichten werden geprüft. Nach Nachricht 20 wird der Filter neu erzeugt; Presidio lädt seine lokale Zuordnung erneut.

Das Ausgangsmaterial wird nur maskiert in die Modellhistorie aufgenommen. Antworten werden kanonisch gespeichert; die Rückübersetzung erfolgt ausschließlich in einer getrennten lokalen Anzeige. Externe Aufrufe sind im lokalen Test vor dem Transport gesperrt. Die Testprofile besitzen eigene Plugin-Schalter; Agent 0 und globale Einstellungen werden dabei nicht verändert.

## Messwerte

| Filter | Sprache | Nachrichten | Exakte Rückübersetzung des Eingabetexts | Ausgehende Aufrufe mit vollständigen bekannten Testwerten |
|---|---|---:|---:|---:|
| Presidio-Prototyp | Deutsch | 40 | 40/40 | 0 |
| Presidio-Prototyp | Englisch | 40 | 40/40 | 0 |
| Presidio-Prototyp | Gemischt | 40 | 40/40 | 0 |
| Bisheriger Filter | Deutsch | 40 | 0/40 | 0 |
| Bisheriger Filter | Englisch | 40 | 0/40 | 0 |
| Bisheriger Filter | Gemischt | 40 | 0/40 | 0 |

Null vollständige Testwerte beweist keine vollständige PII-Freiheit: Kurzformen, Flexionen und unbekannte personenbezogene Angaben benötigen zusätzliche Prüfungen. Exakte Rückübersetzung belegt ebenfalls nicht die Qualität der Beziehungsauswertung.

## Inhaltliche Fehler

Der bisherige Filter vermischt Personen. Beispiele sind „Anna Weber married to Anna Weber“ und eine erfundene Schuld von 500 statt 125 Euro. Überlappende Erkennungen und gemeinsame Typ-Platzhalter machen den Ansatz für reversible Personenbeziehungen ungeeignet.

Presidio ist besser, hat aber weiterhin Fehler: Deutsche Satzanfänge wie „Bestätige“ und Begriffe wie „Geschäftspartner“ werden im gemischten Gespräch als Personen behandelt. „David Berger's“ wird teilweise als eigene Identität geführt. Im englischen Gespräch meldet Gemma nach Zahlung weiterhin die frühere Schuld und Partnerschaft; auf Deutsch berücksichtigt es beide Änderungen. Das erfordert getrennte Tests für Erkennung, Identitätsverknüpfung und Modellverständnis.

Ein fremdes Presidio-Profil konnte die jeweiligen Zuordnungen nicht rückübersetzen. Dies prüft den Prototyp-Decoder; es belegt nicht sämtliche Grenzen der installierten Plugins.

## Vollständiger Agentenablauf

Der zusätzliche Test führt die native `Agent.monologue` samt Promptaufbereitung, Streaming, Werkzeugauswertung und Antwortwerkzeug aus. Ergebnis: „Ben Fischer“. Der erste Start scheiterte am fehlenden Container-Runtime-Flag im separaten Testprozess; nach Korrektur des Teststarts war der Ablauf erfolgreich. Memory ist dabei ausdrücklich deaktiviert. Der Test ist kein Browser-Test und prüft keinen laufenden Webserver-Neustart.

## Requesty

Das vorhandene aktive Agent-0-Profil wird unverändert benutzt; weder Einstellungen noch Schlüssel werden geschrieben. Acht echte Aufrufe, einschließlich READY-Probe und wechselnder Beziehungen, waren erfolgreich. Der frühere Override-Fehler trat auf diesem Modellpfad nicht auf. Die abschließende Antwort berücksichtigt die Zahlung und das Ende der Geschäftspartnerschaft. Der zusätzliche falsche Datensatz „David Berger's“ bleibt sichtbar.

Jeder Transportaufruf wird vorab geprüft: nur die gespeicherten Modelle und die konfigurierte Route sind zulässig; bekannte vollständige PII-Werte stoppen die Übertragung. Ausgabe maximal 512 Tokens, interne Transport-Retries deaktiviert. Die lokale SQLite-Kostenkontrolle reserviert vor jedem Aufruf mit UTF-8-Byte-Obergrenze plus Sicherheitszuschlag und dem Vierfachen der höchsten passenden Katalogpreise. Auch fehlgeschlagene Aufrufe behalten ihre volle Reservierung. Gesamtreservierung dieser Serie: **0,120912 €** bei einem Limit von 5 €. Dies ist eine konservative Testbudget-Buchung, keine Provider-Rechnung. Requesty dokumentiert seine Nutzungsgebühren in USD: https://docs.requesty.ai/ .

## Ergänzung: echter Browser, Speicher und Reasoning

Ein eigener Browser-Chat im Profil `privacy_bench_browser` wurde nach einem Container-Neustart geladen und mit **40 Benutzer-Nachrichten** durchgespielt. Dabei liefen 40 echte Chat- und 40 automatische Utility-Aufrufe über lokales Gemma 3 4B. Profilbezogene Diagnose-Hooks dokumentieren die Nachrichten nach den normalen PII-Filtern und sperren externe Modell-Wrapper. Diese Hooks messen die unterstützten Agenten-Aufrufpunkte, nicht sämtliche Transportaufrufe.

**Kritischer Befund:** In allen 80 erfassten Aufrufen stehen vollständige Testnamen. Die deutschen und englischen spaCy-Modelle fehlen im laufenden Agent-Zero-Python, obwohl sie in der separaten Benchmark-Umgebung vorhanden sind. Die Namenserkennung fällt still aus. Gleichzeitig beschädigt die Regex-Maskierung Texte durch Überlappungen. Die früheren Null-Leck-Messwerte aus der Benchmark-Umgebung gelten deshalb ausdrücklich nicht für diesen Browser-Lauf.

Der Browser meldete vor der manuellen nativen Kontextkürzung 115,1 % Kontextbelegung. Die Kürzung sicherte die ursprüngliche Historie in JSON und Text. Ihre Zusammenfassung enthält aber keine konkreten Personenbeziehungen und Schulden. Danach produziert das kleine Modell generische Felder wie `[Details]` und `[Amount]`, statt den erwarteten Zustand zu nennen. Dieser Test ist inhaltlich fehlgeschlagen. Die Antworten vor der Kürzung ignorierten außerdem teilweise die Trennung; die Verantwortung von Modellverständnis, beschädigter Maskierung und Erinnerungsinhalt muss bei einer Reparatur getrennt untersucht werden.

Ein zusätzlicher realer Transport-Test des nativen Kompaktierungshelfers bestätigt eine weitere Lücke: **Anna Weber, Ben Fischer, E-Mail, Telefon und IBAN werden unmaskiert übergeben**, weil der Helfer das Modell direkt aufruft und die bisherigen Chat-/Utility-Filter nicht durchläuft. Der Test ließ ausschließlich lokales Ollama zu; daraus folgt keine Aussage über eine tatsächlich erfolgte externe Übertragung.

Der reale FAISS-Speicher-Test verwendete zwei neue Profile und lokale Hugging-Face-Embeddings. Profil A speicherte eine fiktive Testinformation. Ein neuer Python-Prozess konnte sie per Ähnlichkeitssuche abrufen und den gespeicherten Chat samt Profil und lokaler Modellüberschreibung wiederherstellen. Profil B hatte einen anderen Speicherpfad und enthielt diese Information nicht. Die geprüften Agent-0-Requesty-Dateien blieben unverändert. Ein Utility-Aufruf mit der Erinnerung enthielt erneut unmaskierte Namen und beschädigte Maskierungen; Speicherisolierung und PII-Schutz sind getrennte Ergebnisse.

Ein fremdes Requesty-Testprofil konnte weder den Agent-0-Schlüssel lesen noch dessen Setup übernehmen. Zusammen mit den Speicher- und Zuordnungstests belegt dies die konkret geprüften Profilgrenzen; eine umfassende Sandbox gegen beliebige vom Agenten ausgeführte Dateizugriffe ist damit nicht bewiesen.

Direkt über Ollama erzeugte Qwen 3 8B 1.242 Zeichen separaten Denktext und eine Antwort. DeepSeek R1 8B erzeugte 3.876 Zeichen Denktext, aber innerhalb der Ausgabegrenze keine abschließende Antwort. Über `ollama_chat` lieferte auch der echte Agent-Zero-Modellpfad separaten Denktext (vier Aufrufe: 1.193/1.527/1.969/1.551 Zeichen). Eine Antwort blieb leer. Der zuvor verwendete `ollama`-Pfad hatte keinen separaten Denktext zurückgegeben. Das ist eine wichtige Testkonfigurationsfrage, keine abgeschlossene Reparatur des Frameworks.

Der persistente Presidio-Prototyp wurde ebenfalls in zwei getrennten Prozessen geprüft: exakte Rückübersetzung, stabile Tokens, kein Decoding im fremden Profil und exakte Anzeige nach gepuffertem Streaming. Der kanonische Stream blieb maskiert; die lokale Zuordnungsdatei hatte Modus 0600. Eine produktive Anzeigeintegration oder vollständige Absicherung der Zuordnungsdatei ist damit nicht implementiert.

## Abgeschlossene Langläufe und Neustart

| Test | Ergebnis | Einschränkung |
|---|---|---|
| Qwen 3 8B, Presidio, gemischte Sprache, 40 Nachrichten | 40/40 Eingabetexte exakt rückübersetzbar; alle Aufrufe mit separatem Denktext; keine vollständigen bekannten Testwerte im erfassten Transport | 22/40 abschließende Antworten leer. Die Grenze von 512 Ausgabetokens umfasst auch Denktext; dies ist kein allgemeines Urteil über Qwen. Abgeschnittene Platzhalter bleiben teilweise unübersetzbar. |
| LLM Guard, Englisch, Gemma 3 4B, 40 Nachrichten | 40/40 Eingabetexte exakt rückübersetzbar; keine leeren Antworten; keine vollständigen bekannten Testwerte im erfassten Transport | Nach dem Erkennungsprozess-Neustart bei Nachricht 20 fehlen alte Zuordnungen. Alte Platzhalter bleiben sichtbar; die abschließende Antwort übernimmt veraltete Schuld und Partnerschaft. |
| Erwarteter Beziehungsgraph, gemischte Sprache, 40 Nachrichten | Alle vier geforderten Zustandswerte stimmen in 40/40 Antworten | Alle Antworten enthalten unerlaubte zusätzliche JSON-Felder: strenge Formatprüfung 0/40; kombinierte Freigabe 0/40. |
| Langer Browser-Chat nach Server-Neustart | Derselbe Verlauf und dasselbe Testprofil sind vorhanden; eine weitere Nachricht wird erfolgreich lokal beantwortet | Inhalt bleibt falsch bzw. unspezifisch: `[Details]` und `[Amount]` statt des erwarteten Schuldenstands. |

Der Graph-Test bewertet Heirat, Geschäftspartnerschaft, Geschwisterbeziehung und offene Schuld nach jeder Änderung automatisch. Inhalt und Antwortformat werden getrennt ausgewiesen; die strenge Formatregel wurde nicht nachträglich abgeschwächt. Dies zeigt, dass kleine lokale Modelle für kontrollierte Testfälle reichen können, während der vollständige Agentenablauf mit Speicher und Kontextkürzung zusätzliche Fehlerquellen hat.

Der Neustart-Nachweis liegt in `browser-after-restart.txt`, `browser-chat-after-restart.json`, `browser-calls-after-restart.jsonl` und dem Screenshot. Die erfassten neuen Aufrufe verwenden weiterhin `ollama/gemma3:4b`. Die Modellanzeige im Browser zeigt dennoch „Default gpt-6.1-sol“ und ist für diesen Override irreführend.

## Folgerungen für die Umsetzung

1. Maskierung an einem gemeinsamen Ausgangspunkt für alle Modellaufrufe erzwingen, einschließlich Kontextkürzung, Speicherverarbeitung und Utility-Aufrufen. Fehlende Erkennungsmodelle sichtbar melden und bei erforderlichem Schutz den Aufruf stoppen.
2. Überlappende Treffer konfliktfrei auflösen; pro Identität eindeutige, pro Profil und Chat getrennte Platzhalter verwenden. Zuordnungen persistent speichern und nach Neustart wiederherstellen.
3. Maskierte Modellhistorie und lokal demaskierte Anzeige getrennt halten. Streaming erst mit vollständigen Platzhaltern rückübersetzen; gekürzte Tokens gesondert behandeln.
4. Kontextkürzung auf Erhalt des aktuellen Zustands prüfen. Für Reasoning-Modelle ausreichend Ausgabetokens vorsehen und leere Schlussantworten explizit behandeln.
5. Requesty-Speicherung, Profilwechsel und Wiederaufnahme als wiederholbare Regressionstests aufnehmen. Die acht erfolgreichen Requesty-Aufrufe bestätigen den geprüften Modellpfad; sie ersetzen keine vollständige Prüfung jeder UI-Speicherfolge.

Presidio ist auf Basis dieser Tests der bessere Kandidat für einen persistenten, mehrsprachigen Adapter. Die Integration bleibt eine eigene Implementierungsaufgabe; die vorliegenden Testbefunde sind keine Datenschutzfreigabe. LLM Guard benötigt ebenfalls eigene Persistenz und Profil-Namensräume und wurde hier im langen Lauf ausschließlich auf Englisch geprüft.

## Nachweise und Grenzen

Die Rohdaten und Programme sind beigefügt. Die ursprüngliche Langtest-Datei enthält den fehlgeschlagenen ersten Monolog-Start; `monologue-results.json` enthält den korrigierten erfolgreichen Lauf. In älteren Rohresultaten ist das Feld `foreign_profile_does_not_decode` außerhalb des Presidio-Vergleichs nicht aussagekräftig: Dort wurde ein fremder Presidio-Decoder statt des jeweiligen nativen Decoders geprüft. Der beigefügte Wiederholungscode kennzeichnet dies; diese Altwerte werden hier nicht als Isolationsnachweis verwendet.

Die Browser-Automatisierungsdatei erfasst nicht jeden frühen Versand separat. Die gesicherte native Historie vor der Kürzung und der abschließende Chat enthalten die vollständige 40-Nachrichten-Serie; die zusätzliche Neustartfrage ist separat dokumentiert. Alle Angaben betreffen fiktive Testdaten und konkret geprüfte Aufrufpfade. Ein profilbezogenes Plugin ist keine Betriebssystem-Sandbox gegen beliebige Dateizugriffe.
