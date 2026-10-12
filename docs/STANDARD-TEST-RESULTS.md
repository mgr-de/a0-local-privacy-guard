# Standardschutz 1.4 / Requesty 0.4 – Prüfung am 12.10.2026

Die bestehenden Plugins wurden am nativen Agent-Zero-Modellpfad verstärkt. Ollama ist **keine Nutzungsvoraussetzung**: Requesty-only wurde mit einem eigenen Testprofil einschließlich externer Fotoanalyse und drei automatischen Formulareingaben geprüft. Lokale Chatmodelle wurden ausschließlich für kostenlose Entwicklungstests verwendet. Textfilter, lokale sentence-transformers-Embeddings und optionale OCR benötigen keinen Ollama-Server.

## Änderungen

Zugelassene native Presets bleiben wählbar; Main, Utility und Browser/Vision müssen die aktive Profilpolicy erfüllen. Inkompatible Anbieter, Transportparameter und nicht bestätigte Vision-Fähigkeiten werden abgelehnt, ohne die Auswahl still zu ändern. Lokale Ollama-Routen werden nur als lokal akzeptiert, wenn `/api/show` lokale Modellgewichte bestätigt; Cloud-Aliase zählen nicht als lokale Verarbeitung. Es findet dabei keine Chatübertragung statt. Diese Prüfung läuft ausschließlich bei einer ausdrücklich gewählten Ollama-Route. [Ollama Cloud](https://docs.ollama.com/cloud), [ShowResponse](https://raw.githubusercontent.com/ollama/ollama/main/api/types.go).

Unteragenten übernehmen die Mindestanforderungen des geschützten Stammchats, auch wenn ihre eigenen Profilhooks deaktiviert sind. Dazu installieren die Lebenszyklushooks kleine native Adapter unter `usr/extensions/python`; sie sind bei unabhängigen anderen Chats wirkungslos und schreiben keine gemeinsamen Presets. Besitznachweise liegen außerhalb des Plugin-Verzeichnisses, damit ZIP-Aktualisierungen sie erhalten. Fremde oder nachträglich veränderte Adapter werden nicht überschrieben bzw. gelöscht. Dies ist kein zusätzlicher Dienst.

Alle nativen Textblöcke einschließlich Systemtext, Werkzeugergebnissen, Kontextkürzung und Speichertext werden auf Kopien geprüft. Neue SQLite-Zuordnungen sind pro Projekt, Schutzprofil und Chat getrennt; vollständige Platzhalter werden lokal für Anzeige und Werkzeugargumente zurückübersetzt. Kanonische Historie und Denktext bleiben maskiert. Streaming wird vor Ausgabe gepuffert; Zählercallbacks übertragen keine ungeprüften Textteile. Fehlende benötigte spaCy-Modelle und ungültige Filter stoppen externe Textaufrufe. Erkannte Secrets blockieren Modellinhalte; Fehlermeldungen enthalten keine Originalwerte. Authentifizierung bleibt Teil des Transports.

Der Schutzstatus trennt tatsächliche Route, Textfilter, konfigurierte lokale Embeddings und nicht abgedeckte Bild-/Werkzeugpfade. Originalbilder bleiben für zugelassene Vision-Modelle möglich; der permanente Hinweis erklärt die Grenze. OCR mit vorhandenem Tesseract ist optional und bereinigt keine Bilder. Es wurden keine allgemeinen Browserfreigaben oder zusätzlichen Bildrestriktionen eingeführt.

## Ergebnisse

| Prüfung | Ergebnis | Reichweite |
|---|---|---|
| Python / Frontend | 93 Local-Tests, 77 Requesty-Tests plus 32 Unterprüfungen; 19 Frontend-Tests bestanden | Native Agent-Zero-v2.13-Umgebung; Regressionstransporte simuliert; Pydantic-Abkündigungswarnungen vorhanden. Beide Python-Suiten separat starten, da Testmodule gleichnamig sind. |
| Abschließender Code: Deutsch, Englisch, gemischt, je 40 Nachrichten | 120/120 Eingaben exakt rückübersetzbar, keine vollständigen bekannten Testwerte im erfassten Texttransport | Gemma 3 4B; freie Modellantworten sind dadurch nicht als inhaltlich korrekt nachgewiesen. |
| Deutsch, Englisch, gemischt, je 100 Nachrichten | 300/300 Eingaben exakt rückübersetzbar, keine vollständigen bekannten Testwerte im erfassten Texttransport | Lauf vor den letzten Alias-/Sprachauswahlkorrekturen; zusätzlich 100 gemischte Nachrichten nach Sprachauswahlkorrektur erfolgreich. |
| Vier Personen, Ehe, Geschäftspartnerschaft, Geschwister, wechselnde Schulden | 100/100 Zustände entsprechen exakt der Erwartung | Abschließender Filter, gemischte Sprache, Gemma 3 4B; ausdrücklich vorgegebenes vierfeldriges JSON-Schema. Ohne Schemabeispiel zuvor 0/100 strenge Formatfreigaben. |
| Reasoning | 40/40 Eingaben exakt rückübersetzbar, keine vollständigen bekannten Testwerte; 40 Aufrufe mit Denktext, zwei leere Schlussantworten | Qwen 3 8B; früherer Entwicklungsstand. Kleine Tokenbudgets begrenzen Denk- und Schlussausgabe. |
| Kontextkürzung | Native Kompaktierung erfasst und bekannte vollständige Testwerte maskiert | Separater Aufrufpfadtest; kein allgemeiner Nachweis inhaltlich verlustfreier Zusammenfassung. |
| Speicher und Neustart | Echte FAISS-Indizes getrennt, Marker wiedergefunden, Chat/Profil/Override wiederaufgenommen, vorherige Einstellungen unverändert | Speicher-, Kompaktierungs- und Reasoning-Nachweise stammen aus früheren Entwicklungsständen; finale Regressionen sichern diese Pfade zusätzlich. |
| Neue produktive Zuordnung über Prozessneustart | Exakte Wiederherstellung, gleiche Tokens, fremdes Profil kann nicht dekodieren; Datei 0600 | Keine Verschlüsselung; lokale Originalwerte benötigen Schutz und Backup. |
| Unteragenten / alte Wrapper / Secrets | Native Unteragenten mit deaktivierten eigenen Plugins bleiben geschützt; unabhängiger Chat unverändert; direkte Vision-Calls und alte Wrapper geprüft; synthetische Schlüssel aus Chat, Datei-, Werkzeug- und Fehlertext blockiert | Kein echter Schlüsselversand; keine Garantie für beliebige unbekannte Secrets oder fremde rohe Modellclients. |
| Requesty-Text | Drei erfolgreiche zusätzliche DeepSeek-Flash-Aufrufe; bekannte vollständige Werte maskiert | Früher Entwicklungsstand mit temporärer Testpolicy-Überlagerung; keine Prüfung des serverseitigen PII-/Secret-Dienstes. |
| Foto zu nativem Browserformular | Originalbild extern verarbeitet; zugelassene Route; spätere Textpayloads maskiert; drei Felder automatisch ausgefüllt; alle vier Empfangswerte anschließend exakt | Letzte IBAN-Eingabe und Absenden manuell nach Budgetstopp. Vollständig automatischer Cloud-Abschluss nicht nachgewiesen. Lokale kleine Modelle scheiterten zuvor an Werkzeugargumenten. |

Die gemeinsame Kostendatenbank enthält **4,71994992 Euro reservierte Obergrenzen** einschließlich früherer Tests. Das ist keine bestätigte Anbieterrechnung. Der nächste über die kumulative 5-Euro-Grenze hinausgehende Aufruf wurde vor Versand gestoppt; Reservierungen wurden nicht zurückgesetzt. Der Budgethaken bleibt ausschließlich im bezeichneten Testprofil der isolierten Entwicklungsinstanz aktiv.

## Fehlbefunde und Grenzen

Die Rohdaten enthalten auch Fehlversuche: zunächst übermaskierte deutsche NER englische Anweisungen und Rollenbuchstaben; der strenge Beziehungstest scheiterte damit. Sprachauswahl und geschützte Protokollfelder wurden korrigiert. Ein bekanntes kurzes Namensfragment darf neue Nachnamen oder neue E-Mail-Adressen nicht nur teilweise maskieren; größere vollständige Treffer haben jetzt Vorrang. Die jeweiligen Regressionen decken diese Befunde ab.

Auch der finale freie 40-Nachrichten-Lauf enthält erfundene Beziehungen und vom Modell veränderte oder ohne Klammern ausgegebene Tokenfragmente. Solche Fragmente sind nicht zuverlässig rückübersetzbar. Eine exakte Eingaberückübersetzung bedeutet weder korrekte Antworten noch garantiert vollständig lesbare Ausgabe. Von Agent Zero gekürzte Chat-Titel mit unvollständigen Tokens erhalten einen neutralen Titel; historische mehrdeutige Platzhalter werden nicht rekonstruiert.

„Keine vollständigen bekannten Testwerte“ bezieht sich auf die festgelegten synthetischen Werte in allen erfassten Textblöcken. Es beweist weder allgemeine PII-Freiheit noch Abwesenheit indirekter Identifikatoren, unbekannter Werte oder sämtlicher Teilfragmente. Bildbytes werden getrennt erfasst und nicht durch Textprüfungen als sicher eingestuft. Webseiten können Formulareingaben bereits beim Tippen verarbeiten. Die Standardplugins kontrollieren nicht jeden Werkzeugtransfer und sind keine Netzwerk- oder Betriebssystem-Sandbox.

## Einführung

Installations-/Aktualisierungshooks ausführen und Agent Zero anschließend neu starten, damit native Adapter geladen werden. Profilkonfigurationen und Zugangsdaten vor nativen ZIP-Ersetzungen sichern; der Rahmen kann Plugin-Daten entfernen. Bestehende Einstellungen bleiben durch die Runtime-Umsetzung erhalten. Neue Zuordnungen entstehen ab 1.4; keine unsichere Rekonstruktion alter Tokens.

Ein zusätzlicher Privacy Hardened Agent mit eigener Instanz, Schutzmanager, lokalem Schutzdienst, Netzwerkregeln und aufgabenbezogenen Freigaben ist ausschließlich als optionaler Ausblick dokumentiert. Er wurde hier nicht gebaut. Wiederholungsprogramme liegen in `tools/privacy_benchmark` des Local-Repositories; nur in einer eigenen Testinstanz mit synthetischen Daten ausführen.
