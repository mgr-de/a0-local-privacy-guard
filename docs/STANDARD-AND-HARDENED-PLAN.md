> Historical report / plan. The current production decision is spaCy + Regex only; see [PRODUCTION-DETECTOR.md](PRODUCTION-DETECTOR.md). Alternative detector code and evidence are preserved on `archive/cpu-pii-evaluation-2026-10-13`. Older install and backend-selection instructions below are not current release instructions.

# Standardschutz und optionaler gehärteter Agent

## Umgesetzter Standardschutz

Die bestehenden Plugins bleiben für Browser, Fotos, Formulare und Dateibearbeitung nutzbar. Requesty prüft die tatsächliche Modellroute eines geschützten Profils; native lokale Modellrouten bleiben zulässig. Ein natives Preset darf die Policy nicht umgehen und wird bei Konflikten abgelehnt, ohne die Auswahl still zu verändern. Unteragenten desselben Chats übernehmen die Mindestanforderungen seines geschützten Stammprofils. Andere unabhängige Chats behalten ihre eigene Konfiguration.

Local Privacy Guard kopiert native Modellpayloads vor der Prüfung. Systemtexte, Werkzeugtexte und alle Textblöcke werden berücksichtigt. Der Modellwrapper erfasst auch direkte Kompaktierungsaufrufe; native Vision-Werkzeugaufrufe erhalten einen tasklokalen Besitzer. Fehlende erforderliche Namenserkennung stoppt externe Textaufrufe. Fremde, selbst geschriebene Modellclients sind außerhalb dieser Integration.

PII-Zuordnungen liegen pro Profil und Chat in lokalen SQLite-Dateien unter `usr/privacy-mappings`. Jeder erkannte Wert erhält eine eindeutige Tokenfamilie; Schreibweisen und eindeutige Kurzformen können eigene Varianten derselben Familie erhalten. Originalwerte werden nur für die lokale Anzeige und die lokale Werkzeugausführung zurückübersetzt. Antworten und Denktext werden vor der Speicherung geprüft. Streaming wird zunächst gepuffert; dadurch erscheint die geprüfte Ausgabe später statt Zeichen für Zeichen. Alte gemeinsame Typ-Platzhalter werden nicht importiert.

Der lokale Secret-Scanner prüft bekannte verwaltete Credentials, erkennbare Schlüsseltypen, private Schlüssel, Credential-URLs und kontextbezogene Passwort-/Token-Zuweisungen. Er kontaktiert keine Dienste zur Prüfung der Gültigkeit. Treffer blockieren Modellinhalte und werden ohne Originalwert gemeldet. Dies ist kein vollständiger Secret-Erkennungsnachweis. Requestys serverseitige Scanner werden weder automatisch aktiviert noch als geprüft dargestellt.

## Bilder, Browser und lokale Dateien

Zugelassene Vision-Modelle dürfen Originalbilder verarbeiten. Textmaskierung entfernt keine Gesichter, Dokumentdaten, Bildtext oder Metadaten aus diesen Bildern. Bei extern verarbeiteten Bildern zeigt der Chat einen Hinweis mit der tatsächlichen erfassten Modellroute. Die Freigabe eines Modellanbieters umfasst nicht die Datenweitergabe an Webseiten.

Lokale OCR mit bereits installiertem Tesseract ist optional. Sie liefert Text, verändert das Bild nicht und begründet keine Einstufung als anonymisiert. Es entstehen keine neuen allgemeinen Browserrestriktionen oder Pflichtfreigaben für jedes Bild. Formulare, Uploads und Dateibearbeitung bleiben native Funktionen; diese Plugins kontrollieren nicht jede Werkzeugübertragung.

Erkennung reduziert Offenlegungsrisiken, garantiert aber keine vollständige Anonymisierung. Eine zugelassene Region sowie Regeln zu Speicherung und Training ändern nichts daran, dass der gewählte Dienst die übertragenen Daten verarbeitet. Die UI unterscheidet Modellroute, Textfilter, lokale Embeddings und nicht abgedeckte Bild-/Werkzeugpfade.

## Einführung und Prüfung

Bestehende Profile, Zugangsdaten und Presets bleiben erhalten. Ein alter von Requesty 0.3.x ausgesetzter Override wird erst bei Deaktivierung wiederhergestellt; neu gewählte Overrides werden geprüft. Mappings werden ab der neuen Version aufgebaut. Dateien enthalten personenbezogene Originalwerte und müssen zusammen mit den lokalen Chats geschützt und gesichert werden. Die Dateirechte sind keine verschlüsselte Ablage.

Die Abnahme umfasst native Transportpayloads, Presets, Vision, Unteragenten, alte Wrapper, mehrsprachige 40-/100-Nachrichten-Sitzungen, Beziehungen und Schulden, Reasoning, Streaming, Kontextkürzung, echte Speicherabfragen, Neustart und einen synthetischen Foto-Formular-Ablauf. Erkennungsfehler, Rückübersetzungsfehler und falsche Modellantworten werden getrennt dokumentiert. Externe Tests behalten das bestehende kumulative Budgetlimit von 5 Euro.

## Ausblick: Privacy Hardened Agent

Ein späterer optionaler Modus erhält eine eigene Agent-Zero-Instanz, einen Schutzmanager, einen separaten lokalen Schutzdienst und kontrollierte Netzwerkzugänge. Mindestpolicy und externe Credentials liegen außerhalb des Agenten. Plugin-Deaktivierung und direkte Provider-Aufrufe können dann keinen unkontrollierten externen Zugang öffnen. Diese Infrastruktur ist nicht Bestandteil des Standardschutzes.

Freigaben werden auf Aufgaben begrenzt: konkrete Daten, Empfänger, Zweck und Gültigkeit. Passende Schritte brauchen keine wiederholte Rückfrage; zusätzliche Daten oder andere Empfänger erfordern eine neue Entscheidung. Bei Formularen liegt der Zeitpunkt vor dem Eintragen, da Webseiten Eingaben bereits beim Tippen erfassen können. Fotoauswertung durch ein Modell und Weitergabe an eine Webseite sind getrennte Entscheidungen.

Strengere Bildregeln, lokale Verarbeitung und der Freigabeumfang werden dort konfigurierbar. Ausnahmen bleiben sichtbar und auf die Aufgabe begrenzt. Eine pauschale Freigabe für alle künftigen Daten wird nicht als sicherer Zustand dargestellt. Schutz vor Host-Administratoren und absichtlichen verdeckten Kommunikationskanälen gehört nicht zu einer umfassenden Sicherheitsgarantie dieser Plugins.

## Entwicklungs-Testserver

Der vorhandene lokale Modelldienst dient nur als Entwicklungs-Testumgebung. Die Plugins erhalten dafür keine eigene Integration oder Metadatenabfrage. Die Nutzung funktioniert mit zugelassenen Requesty-Modellen allein. Lokale Textfilter und sentence-transformers-Embeddings benötigen keinen lokalen Chat-LLM. OCR benötigt optional bereits installiertes Tesseract und wird nicht vorausgesetzt.

## Native Adapter und Einführung

Installationshooks richten kleine native Adapter unter `usr/extensions/python` ein. Sie erhalten die Mindestpolicy geschützter Elternchats auch bei deaktivierten Unteragenten-Profilhooks; unabhängige Chats anderer Profile bleiben unverändert. Sie betreiben keinen Dienst und schreiben keine gemeinsamen Presets. Eigentumsnachweise unter `usr/privacy-guard-adapters` überstehen Plugin-ZIP-Ersetzungen; fremde oder veränderte Dateien werden erhalten. Nach Installation/Aktualisierung Agent Zero neu starten. [Prüfergebnisse](STANDARD-TEST-RESULTS.md) unterscheiden erfolgreiche Filterprüfungen, falsche Modellantworten und manuelle Formulartestschritte.


## Gemeinsamer Einstieg ab 1.5 / 0.5

Siehe [Installationsweite Regeln und weiterer Ausblick](INSTANCE-PRIVACY-PLAN.md). Der zusätzliche Privacy Agent vereinheitlicht die Einrichtung; kontrollierte Netzwerkzugänge bleiben ein späterer eigener Ausbau.
