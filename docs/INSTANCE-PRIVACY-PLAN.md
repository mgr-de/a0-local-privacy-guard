# Standardschutz, gemeinsamer Privacy Agent und gehärteter Ausblick

## Stand 12. Oktober 2026

Local Privacy Guard 1.5.0 und Requesty 0.5.0 bleiben eigenständig. Requesty Privacy Agent 0.1.0 ergänzt einen gemeinsamen Einrichtungsassistenten und Mindestregeln für alle Profile einer ausdrücklich aktivierten Installation. Profile können eigene zulässige Modelle/Schlüssel nutzen; nicht konfigurierte Profile erben die gemeinsame Basis. Lokale native Modellrouten bleiben möglich. Gespeicherte Profilkonfigurationen, andere Installationen und gemeinsame Presets werden nicht überschrieben.

Die gemeinsame Basis erzwingt EU-Requesty, EU-Modellstandorte sowie keinen Anbieter-Datenaufbewahrungs-/Trainingsgebrauch anhand des Katalogs, lokale Maskierung und lokale Embeddings. Strengere Profilregeln bleiben wirksam. Profil-Schalter können diese Mindestregeln nicht abschwächen. Fehlen erforderliche Komponenten, stoppt der betroffene externe Aufruf. Die Aktivierung ist eine eigene, bestätigte Aktion nach vollständiger Prüfung. Deaktivierung bewahrt Konfigurationen und Zugangsdaten.

Schutzidentitäten werden im Chat gespeichert. Ein Profilwechsel erzeugt keine neue Zuordnung für dessen bestehende Namen. Zuordnungen verschiedener Chats bleiben getrennt. Alte mehrdeutige Platzhalter werden nicht rekonstruiert.

## Konkrete Grenze der Umsetzung

Geprüft werden native Agent-Zero-Modellgetter, Unified Calls/Turns, native Tool-/Vision-Aufrufe und die durch den Filterwrapper verwendeten LangChain-Wege. Der Manager ergänzt einen reversiblen Laufzeit-Guard für alte LangChain-Wrapper: Ein alter externer Wrapper ohne nachgewiesene Filterpassage wird abgelehnt und muss neu aufgebaut werden. Der Guard ist installationsweit, betreibt aber keinen Dienst und kopiert keine PII-/Routinglogik. Nach Installation und Aktualisierung neu starten.

Originalnamen bleiben lokal sichtbar; Modellhistorie und Denktext bleiben maskiert. Originalbilder dürfen zugelassene Vision-Modelle erreichen. Lokale Textmaskierung bereinigt weder Bildinhalt noch Metadaten. Werkzeuge können Originaldaten an Webseiten, Uploadziele oder andere Empfänger senden. Die Freigabe eines Modellanbieters ist keine Webseitenfreigabe.

Diese Plugins sind keine Sicherheits-Sandbox: Code-Ausführung und fremde Netzwerkclients können außerhalb der unterstützten Modellpfade arbeiten; Agenten mit Schreibzugriff auf dieselben Dateien können Schutzdateien verändern. Kein Schutzversprechen gegen Administratoren oder absichtliche Manipulation. Unabhängige Netzwerkdurchsetzung bleibt zusätzliche Infrastruktur.

## Requesty-Konto

Empfohlen werden EU-Serving-Region, Requesty-ZDR, verpflichtendes Anbieter-ZDR und geprüfte EU-Approved-Models. Der Screenshot dient als datierte Anleitung. Manuelle Bestätigung ist keine API-Verifikation und übersteuert keinen technischen ZDR-Schalter. Kontoweite Regeln betreffen andere Anwendungen desselben Kontos; Metadaten werden weiterhin gespeichert.

## Später: ausdrücklich gehärtete Instanz

Eine eigene Instanz mit Schutzmanager außerhalb des Agenten, separatem Schutzdienst, getrennten Credentials und kontrollierten Netzwerkzugängen kann auch Werkzeugübertragungen begrenzen. Freigaben gelten dann für konkrete Daten, Empfänger, Zweck und Aufgabe. Neue Empfänger oder zusätzliche Daten benötigen eine neue Entscheidung; Formulare müssen vor dem Eintragen freigegeben sein. Bildanalyse und Webseitenübertragung bleiben getrennte Freigaben. Dieser Ausbau ist nicht Bestandteil von 0.1.0.

## Abnahme

Native Transportgrenzen werden mit simulierten Antworten geprüft. Der mehrsprachige Korpus bewertet bekannte synthetische Werte und Tokenkontinuität, nicht allgemeine Anonymisierung oder freie LLM-Antwortqualität. Früher dokumentierte Live-Foto-Formular-Tests hatten manuelle Abschlussschritte; sie werden nicht nachträglich als vollautomatische Abnahme des Managers dargestellt. Menschliche Nutzertests bleiben eine eigene Produktvalidierung.

Externe Tests dürfen nur das verbleibende kumulative 5-Euro-Budget verwenden; bestehende Reservierungen bleiben erhalten. In dieser Einführung werden keine weiteren kostenpflichtigen Modellantworten angefordert. Ollama ist weder Produktintegration noch Voraussetzung.
