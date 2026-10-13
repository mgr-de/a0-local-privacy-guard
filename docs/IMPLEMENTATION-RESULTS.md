> Historical report / plan. The current production decision is spaCy + Regex only; see [PRODUCTION-DETECTOR.md](PRODUCTION-DETECTOR.md). Alternative detector code and evidence are preserved on `archive/cpu-pii-evaluation-2026-10-13`. Older install and backend-selection instructions below are not current release instructions.

# Einführung vom 12. Oktober 2026

Die beiden vorhandenen Plugins wurden erweitert; Requesty Privacy Agent 0.1.0 ergänzt eine gemeinsame Einrichtung und installationsweite Mindestregeln. Installation allein aktiviert diese nicht. Die lokale Testinstanz ist mit DeepSeek Flash als Main und GPT-6-Luna als Utility/Vision vorbereitet; ihre vorhandenen Profile, Schlüssel und Presets wurden erhalten.

## Geprüft

- 185 Python-Tests (Requesty 75, Local Privacy Guard 91, Manager 19), zusätzlich 32 Subtests; 27 Frontend-Tests. Pydantic-Abkündigungswarnungen waren keine Testfehler.
- Native Main-, Utility- und Vision-Aufrufe mit simulierten Transportantworten, auch bei ausgeschalteter Plugin-Erkennung; ausgehende Textmaskierung und lokale Rückübersetzung.
- Anforderungen dürfen durch Profile, NER-Typauswahl oder ersetzte Standard-RegEx nicht abgeschwächt werden. Strengere Profilregeln gelten auch bei gemeinsamen Modellen/Schlüsseln.
- Alte externe LangChain-Wrapper ohne Filterpassage werden gestoppt; der zusätzliche Laufzeit-Guard ist bei Deaktivierung reversibel.
- Aktivierung prüft alle benötigten Modellslots vor dem Setzen des Aktivierungsmarkers. Ungültige Kandidaten aktivieren keinen Teilschutz.
- Endgültige native Chatlöschung entfernt Zuordnungen; Archivierung erhält sie. Prüfsummenfehler stoppen die Abhängigkeitsinstallation vor dem nativen Installer; vorhandene kompatible Plugins bleiben erhalten.
- 16 synthetische NER-Sitzungen in DE, EN, FR, ES, IT, NL, PL und gemischt, jeweils 40/100 Nachrichten: 1.120 exakte Rückübersetzungen, 1.120 stabile vollständige Namensfamilien; keine geprüften vollständigen Kontaktwerte, Namen oder geprüften Namensfragmente im ausgehenden Text. Groß-/Kleinschreibung, Namenskollision, Beziehungs-/Schuldenzustände, maskierte Historie, Kontextkürzung und Wiederöffnung der SQLite-Zuordnung sind enthalten.

## Aussagegrenzen

Das Ergebnis gilt für diesen synthetischen Korpus und die genannten nativen Wege. Keine allgemeine PII-Erkennungsrate, vollständige Anonymisierung oder Unternehmens-Rechtssicherheit. Regex allein schützt Namen nicht ausreichend; die separate Vergleichsauswertung zeigt diese Grenze.

Die Beziehungs-/Schuldenzustände sind ein deterministischer Test-Oracle, keine frei erzeugten LLM-Antworten. Zusätzliche Live-Sitzungen mit 40/100 Modellantworten wurden wegen des bestehenden fast ausgeschöpften Budgets nicht begonnen. Neue kostenpflichtige Modellantworten: null; bestehende konservative Reservierungen bleiben bei 4,71994992 EUR von 5 EUR.

Der aktuelle Vision-Test verwendet einen simulierten nativen Transport: Originalbildinhalt bleibt unverändert und als extern verarbeitet gekennzeichnet, Text wird maskiert. Frühere Live-Foto-Formular-Prüfungen hatten manuelle Abschlussschritte und sind keine vollautomatische Abnahme dieser Manager-Version.

Bedienbarkeit wird im nativen Browser anhand einfacher und technischer Nutzungsszenarien geprüft. Eine empirische Studie mit Personen beider Nutzergruppen wurde nicht durchgeführt. Bilder, Webseitenübertragungen, Code-Ausführung und fremde Netzwerkclients bleiben eigene Grenzen. Die Requesty-Kontocheckliste bleibt eine datierte Nutzerangabe; sie bestätigt keine API-Verifikation und hebt keinen technischen ZDR-Block auf.
