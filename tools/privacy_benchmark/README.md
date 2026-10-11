# Opt-in integration harness — experimental, synthetic data only

These programs are comparison and diagnostic tools, not plugin runtime code. They require a disposable Agent Zero v2.13 Docker test instance and existing Ollama models. Copy this directory to `/tmp/privacy-benchmark` in that instance. Do not run the prepare scripts in a production installation: they create test profiles/chats and diagnostic files. The browser capture extension must be installed only in its named test profile. Server restarts are manual test-instance actions.

The scripts use environment-specific paths and Python 3.12. The benchmark environment used Presidio 2.2.358, spaCy 3.8.16 with English/German 3.8 models and LLM Guard 0.3.16. LLM Guard runs in a separate environment because of native dependency conflicts. It uses cached models offline. Environment setup is not automated; language model availability must be checked in the actual server environment as well as the benchmark environment.

The Presidio adapter is experimental and keeps original values in mapping files. It is not an encrypted vault or production integration. Native session mappings may lose identity continuity on restart. Existing directory paths and profile names must be adapted for independent repeats.

`requesty_live_test.py` is the only paid external test: it uses the configured `agent0` profile and requires explicit API-budget authorization. It does not enable hosted Guardrails. Preserve its budget ledger; do not reset it between repeated paid calls. The local model tests reject external model routes, but these scripts are not a network sandbox for arbitrary tools.

# Wiederholung der Tests

Alle Daten sind fiktiv. Live-Tests ausdrücklich nur in einer eigenen Agent-Zero-Testinstanz ausführen. Die Programme erlauben im lokalen Vergleich ausschließlich `http://host.docker.internal:11434` und Ollama-Modelle. Die Pfade beziehen sich auf die verwendete Docker-Testinstanz und müssen bei anderen Installationen angepasst werden.

Benötigt werden das native Agent-Zero-Python unter `/opt/venv-a0/bin/python`, die separat eingerichtete Benchmark-Umgebung unter `/opt/privacybench-venv`, die beigefügten Programme unter `/tmp/privacy-benchmark` und die vorhandenen Ollama-Modelle. Sprachmodelle für die PII-Erkennung in der Benchmark-Umgebung ersetzen nicht die erforderlichen Modelle im tatsächlichen Serverprozess.

```sh
cd /a0
/opt/venv-a0/bin/python /tmp/privacy-benchmark/extended_agent_test.py --output /tmp/privacy-benchmark/new-local --monologue --turns 40 --variants presidio,local --languages de,en,mixed
/opt/venv-a0/bin/python /tmp/privacy-benchmark/extended_agent_test.py --output /tmp/privacy-benchmark/new-thinking --model qwen3:8b --provider ollama_chat --turns 40 --variants presidio --languages mixed
/opt/venv-a0/bin/python /tmp/privacy-benchmark/extended_agent_test.py --output /tmp/privacy-benchmark/new-llmguard --turns 40 --variants llm_guard --languages en
/opt/venv-a0/bin/python /tmp/privacy-benchmark/memory_profile_test.py prepare
/opt/venv-a0/bin/python /tmp/privacy-benchmark/memory_profile_test.py resume
/opt/venv-a0/bin/python /tmp/privacy-benchmark/mapping_restart_test.py prepare
/opt/venv-a0/bin/python /tmp/privacy-benchmark/mapping_restart_test.py resume
/opt/venv-a0/bin/python /tmp/privacy-benchmark/compaction_profile_probe.py
```

Die Skripte erzeugen eigene Testprofile bzw. verwenden eindeutig benannte Testprofile. Wiederholungen können vorhandene Testartefakte ergänzen; für unabhängige Vergleichsläufe sollten neue Ausgabeordner und neue Profilnamen verwendet werden. Im LLM-Guard-Test wird der Erkennungsprozess nach 20 Nachrichten neu gestartet: Seine native Zuordnung ist nicht persistent.

`prepare_browser_test.py` erzeugt einen neuen gespeicherten Chat mit eigenem Profil. Der Webserver muss diesen Chat anschließend laden. `browser_capture_extension.py` wurde ausschließlich im Testprofil für die beiden Aufrufpunkte `chat_model_call_before` und `util_model_call_before` installiert. Die 40 Nachrichten liegen im Browser-Testprotokoll; nach Nachricht 26 wurde die native Funktion Compact aufgerufen. Nach einem Steuerungs-Timeout immer den sichtbaren bzw. gespeicherten Verlauf prüfen, um Dopplungen zu verhindern.

`requesty_live_test.py` verwendet das vorhandene aktive Agent-0-Requesty-Profil, schreibt dessen Einstellungen nicht und verursacht API-Kosten. Es enthält eine vorgeschaltete SQLite-Kostenkontrolle mit 5-Euro-Grenze sowie eine Prüfung auf bekannte vollständige Testwerte. Unbekannte Tokenpreise, fremde Modelle und fremde Routen sind nicht zulässig. Diesen Test nur mit ausdrücklich erlaubtem Budget und Zugriff auf das eigene Testkonto ausführen. Die Kostendatenbank bei Wiederholungen beibehalten, damit das gemeinsame Budget nicht zurückgesetzt wird.

Die Erkennung vollständiger bekannter Testwerte ist kein allgemeiner Nachweis von PII-Freiheit. Rohdaten und Fehlbefunde sind Bestandteil des Ergebnisses, einschließlich leerer Modellantworten und falscher Beziehungen. Produktive Presidio-Integration und Reparaturen der aufgefundenen Filterlücken sind nicht Teil dieses experimentellen Vergleichscodes.

## Automatische Beziehungsauswertung

`relationship_graph_test.py` erzeugt 40 tatsächliche lokale Aufrufe mit einem erwarteten Zustand je Nachricht. `evaluate_graph.py` wertet die gespeicherten Antworten getrennt nach Inhalt und strengem JSON-Format aus:

```sh
cd /a0
/opt/venv-a0/bin/python /tmp/privacy-benchmark/relationship_graph_test.py
python evaluate_graph.py relationship-graph-results.json relationship-graph-evaluation.json
```

Für die Offline-Auswertung müssen die beiden Dateipfade zum gespeicherten Ergebnis angepasst werden. Der Browser-Neustarttest verlangt zusätzlich: Testchat sichern, ausschließlich die Testinstanz neu starten, denselben Chat öffnen, eine weitere Nachricht senden und Profil, lokalen Modelltransport sowie Antwort prüfen. Die beigefügten Nachweise zeigen den abgeschlossenen Lauf; Inhalte und Format können trotz technisch erfolgreicher Ausführung fehlschlagen.
