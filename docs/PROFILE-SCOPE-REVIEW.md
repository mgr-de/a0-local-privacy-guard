# Prüfung der Agentenprofil-Grenzen

Stand: 11. Oktober 2026. Geprüft wurden Local Privacy Guard und Requesty Privacy Guard in Agent Zero v2.13, ausschließlich in der Testinstanz `privacy-ux-review-test` auf Port 59021. Die gewünschte Grenze ist ein einzelnes Agentenprofil innerhalb derselben Installation, optional zusätzlich getrennt nach Projekt.

## Ergebnis und behobene Überschreitungen

Die vorherige Fassung erfüllte diese Grenze nicht vollständig. Local Privacy Guard schrieb beim Agentenstart die Embeddings aller globalen Modellvorlagen um. Requesty verwendete globale Datenschutzvorgaben, den gemeinsamen API-Schlüsselspeicher und global gespeicherte Modellvorlagen. Seine Deinstallation konnte Vorlagen und Verweise anderer Profile verändern.

Die Umsetzung in Local Privacy Guard 1.3.0 und Requesty 0.3.0 begrenzt die Laufzeitfunktionen und Einrichtung auf ausdrücklich konfigurierte Profile:

| Bereich | Neue Begrenzung | Nachweis |
|---|---|---|
| Aktivierung | Einstellungen müssen für ein konkretes Profil gespeichert sein. Globale und projektweite Einstellungen allein aktivieren keine Schutzfunktionen. | Leere Profilangaben werden abgelehnt; zweites Profil bleibt unverändert. |
| PII-Filter | Filter gehört dem tatsächlichen Agent-Objekt. Konfigurationsänderungen erzeugen einen neuen Filter. Schwache Referenzen verhindern Wiederverwendung nach Objektfreigabe. | Getrennte Filter für zwei Agenten; Änderung am ersten lässt den zweiten Filter unverändert. |
| Blockieren | Unterstützte Modellaufrufe mit erkannten Details werden tatsächlich abgebrochen; bisher wurde nur ein Sperrtext eingesetzt. | Aufruf des geschützten Profils wird gestoppt, der zweite bleibt unbeeinflusst. |
| Embeddings | Local Privacy Guard überschreibt ausschließlich die zur Laufzeit aufgelöste Konfiguration des geschützten Profils. Der Start schreibt keine gemeinsamen Modellvorlagen. | Tatsächliche Framework-Auflösung mit zwei Profilen; gemeinsam gespeicherte Vorlagen bleiben bytegleich. |
| Chat-Overrides | Mit lokalen Embeddings kollidierende Chat-Vorlagen werden abgelehnt. Bei aktivem Requesty-Profilsetup müssen vorhandene Chat-Modellüberschreibungen entfernt werden. | Konflikt wird vor Verwendung der abweichenden Embeddings abgefangen. |
| Requesty-Vorgaben | Eigene Konfiguration pro Projekt/Profil; kein Rückgriff auf alte globale Vorgaben. | Vorgaben von Profil A bleiben beim Ändern von Profil B gleich. |
| Requesty-Schlüssel | Eigene `credentials.json` unter `usr/secrets/requesty/<Projekt-Profil-Hash>/`, außerhalb der Projektverzeichnisse. Kein Schreiben oder Rückgriff auf den globalen API-Schlüsselspeicher. | Unterschiedliche synthetische Schlüssel; Anfrageprüfung nutzt nur den Schlüssel des zugehörigen Profils. |
| Modellsetup | `setup.json` gehört einem Profil. Erstellen aktiviert nicht; Aktivieren/Deaktivieren ist ausdrücklich und profilbezogen. Gemeinsame Vorlagen werden nicht geschrieben. | Erstellen, Aktivieren und Deaktivieren lassen native Auswahl und Dateien des zweiten Profils unverändert. |
| Alte Modellobjekte | Prüfen beim Aufruf weiter ihr zugehöriges Profil, aktive Auswahl, Schlüssel und Vorgaben. | Deaktivierung und Änderung während Katalogprüfung stoppen alte Objekte. Auch ohne registrierte Plugin-Hooks werden Anfragen gestoppt. |
| Testnachweise | An Profil, Projekt, Schlüssel, Vorgaben und Modelle gebunden; zehn Minuten gültig. | Übertragung auf ein anderes Profil wird abgelehnt, selbst bei identischen Modellen. |
| Memory | Geschützte Profile erhalten getrennte Memory-Ordner. Bestehende gemeinsame Erinnerungen werden nicht kopiert oder umgeschrieben. Local Privacy Guard trennt zusätzlich nach lokaler Embedding-Konfiguration. | Tatsächliche Memory-Konfigurationsauflösung und unterschiedliche Verzeichnisse; gespeicherte native Einstellungen bleiben unverändert. |
| Memory-Verarbeitung | Requesty verändert Konsolidierung und Ersetzungsverhalten nur für ein aktiviertes Profilsetup. | Zweites Profil behält die native Konfiguration. |
| Chatstart | Profilbezogener Requesty-Status berücksichtigt den zugehörigen Schlüssel, ohne ihn an die Oberfläche zurückzugeben. | Status für das zweite Profil entspricht exakt dem nativen Ergebnis. |
| Browser-Profilwechsel | Ungespeicherte Schlüssel, Auswahl und Tests werden verworfen; verspätete Antworten eines anderen Profils werden ignoriert. | Automatisierte Oberflächentests und Prüfung im seitlichen Browser. |
| Dateipfade | Leere Profile, Pfadnavigation und Speicherorte außerhalb des Benutzerbaums werden abgelehnt. | Tests für ungültige Profile und ausbrechende Zielpfade. |

## Nutzung und Änderungen gegenüber bisherigen Versionen

In beiden Plugins zuerst im oberen Framework-Bereich ein **Agent profile** auswählen. Bei Requesty danach einen eigenen Profilschlüssel speichern, Datenschutzvorgaben speichern, Katalog laden, synthetischen Test ausführen, Setup erstellen und ausdrücklich **Activate for this profile** wählen. Aktivierung gilt für die Chats dieses Profils und derselben Projektkombination. **Deactivate profile setup** stellt die native Modellwahl wieder her.

Lokale Embeddings und getrennte Memory-Ordner werden nicht durch Änderungen gemeinsamer Vorlagen eingerichtet. Bestehende gemeinsame Erinnerungen bleiben erhalten, erscheinen aber nicht automatisch im neuen geschützten Ordner. Diese bewusste Trennung ist in der Oberfläche erläutert.

Alte globale Requesty-Schlüssel, Modellvorlagen und Local-Privacy-Guard-Backups werden nicht automatisch auf Profile verteilt oder zurückgespielt. Ein älteres `requesty_guarded`-Preset ohne zugehöriges Profilsetup wird gesperrt. Für die Migration ein natives Preset wählen und die gewünschten Profile ausdrücklich einrichten.

## Was diese Begrenzung nicht zusichert

Agentenprofile teilen sich den Agent-Zero-Prozess, das Dateisystem und dieselben Administratorrechte. Die Prüfung belegt die Begrenzung der implementierten Plugin-Aktionen, keine Sicherheitsabschottung gegen beliebigen Agentencode, fremde Tools oder Administratoren. Solche Akteure können außerhalb dieser Hooks direkt Modelle aufrufen oder Dateien lesen. Für gegenseitig nicht vertrauenswürdige Agenten sind getrennte Instanzen erforderlich.

Installation und Aktualisierung von Plugin-Code, Python-/spaCy-Paketen, Providerregistrierung, globale Schalter und vollständige Deinstallation sind weiterhin Framework-Verwaltung für die gesamte Installation. Eine globale Deinstallation kann nicht nur ein Profil betreffen, weil der Plugin-Code gemeinsam installiert ist. Für eine profilbezogene Änderung den Profilschalter beziehungsweise die Requesty-Deaktivierung verwenden. Vor Deinstallation oder ZIP-Austausch die profilbezogenen Daten sichern: Das Framework kann dabei auch gespeicherte Overrides entfernen.

Requesty-Schlüssel sind durch die Dateirechte geschützt, nicht zusätzlich verschlüsselt. Die Linux-Dateien werden atomar mit restriktiven Dateirechten erstellt. Datenschutzvorgaben werden weiterhin gegen Katalogangaben geprüft; die tatsächliche Praxis externer Anbieter wurde nicht unabhängig auditiert. PII-Erkennung kann Details übersehen.

## Validierung

- Local Privacy Guard: 50 Python-Tests im tatsächlichen Framework bestanden.
- Requesty: 55 Python-Tests und 30 Untertests bestanden. Die 50 vorhandenen LangChain/Pydantic-Abkündigungswarnungen betreffen Abhängigkeiten.
- Oberfläche: 13 JavaScript-Testeinträge bestanden, einschließlich Profilwechsel, verspäteter Antworten und expliziter Profilangaben in Einrichtungsvorgängen.
- Alle Modell-/Katalogaufrufe der Tests waren simuliert; es wurden keine echten API-Schlüssel eingegeben und keine kostenpflichtigen Anbieteranfragen ausgelöst.
- Im Browser wurden eigene Requesty-Standardvorgaben für Agent 0 gespeichert. Developer benötigt weiterhin eine eigene Erstkonfiguration. Das lokale E-Mail-Beispiel ersetzt die Adresse durch `<EMAIL>` und meldet die fehlenden englischen/deutschen Namensmodelle.
- Die seitliche Testinstanz bleibt für die weitere Prüfung geöffnet. Produktive Agent-Zero-Instanzen wurden nicht verändert.

Die Änderungen werden in den bestehenden Pull Requests bereitgestellt: [Local Privacy Guard](https://github.com/mgr-de/a0-local-privacy-guard/pull/1) und [Requesty Privacy Guard](https://github.com/mgr-de/a0-requesty-privacy-guard/pull/1). Sie sind nicht automatisch zusammengeführt.
