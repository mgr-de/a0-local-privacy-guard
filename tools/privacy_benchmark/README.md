# Opt-in integration harness — experimental, synthetic data only

These programs are comparison and diagnostic tools, not plugin runtime code. They require a disposable Agent Zero v2.13 Docker test instance. Local LLM comparisons use the developer's existing Ollama models; **Ollama is never a plugin usage prerequisite**. Requesty-only tests use an explicitly authorized profile/key and shared budget. Copy this directory to `/tmp/privacy-benchmark` in that instance. Do not run prepare scripts in production: they create test profiles/chats and diagnostic files. Server restarts are manual test-instance actions.

The scripts use environment-specific paths and Python 3.12. The benchmark environment used Presidio 2.2.358, spaCy 3.8.16 with English/German 3.8 models and LLM Guard 0.3.16. LLM Guard runs in a separate environment because of native dependency conflicts. It uses cached models offline. Environment setup is not automated; language model availability must be checked in the actual server environment as well as the benchmark environment.

The Presidio adapter is experimental and keeps original values in mapping files. It is not an encrypted vault or production integration. Historical pre-1.4 session mappings can lose identity continuity; the current production mapping has a separate process-restart test. Existing paths and profile names must be adapted for independent repeats.

`requesty_live_test.py`, `standard_requesty_test.py` and the native Requesty browser test make paid external calls and require explicit API-budget authorization. They do not enable hosted Guardrails. Preserve the same budget ledger across all tests; never reset its existing reservations. Local model tests reject external model routes; these programs are not a network sandbox for arbitrary tools.

## Production 1.4 integration tests

`standard_runtime_test.py` captures the final native model transport, including all system/tool/message text blocks. It records exact input restoration and known full synthetic value leaks separately from model answers and reasoning. Run with `--turns 40` or `--turns 100`, `--languages de,en,mixed`. `standard_graph_test.py` evaluates four relationship/debt fields against deterministic updates over 40 or 100 turns; model/schema errors are failures, never proof of successful reasoning.

`standard_mapping_restart.py prepare` followed by `resume` in a separate process tests the production SQLite mapping. `memory_profile_test.py` uses real isolated FAISS indices and persisted chat restoration; `compaction_profile_probe.py` captures native context compaction.

`prepare_requesty_browser.py` explicitly clones the existing test-account setup into its own disposable profile, including a separately owned local credential file. It never changes the source profile. Before opening the prepared chat, install `browser_budget.py` as `_ZZ_test_budget.py` under BOTH `usr/extensions/python/_functions/models/LiteLLMChatWrapper/{unified_call,unified_turn}/start`, restart only the test UI server, and verify `BrowserTestBudget` is present in each extension list. It applies only to the named test profile. Preserve `/tmp/privacy-benchmark/requesty-live/budget.sqlite`. Every paid attempt reserves a conservative upper bound; missing prices or an exceeded 5 EUR total stop the call. The capture contains synthetic message/image content, never transport credentials. Remove test-only hooks after testing, keeping the ledger.

`form_fixture.py` serves a disposable contact form and creates a fictional contact-card image. Drive the actual Agent Zero chat/browser UI for the photo-to-form test. Record original image processing independently of text leak checks; OCR and text masking do not sanitize pixels. The installed-plugin tests require en/de spaCy models in the actual `/opt/venv-a0` server environment, not just a benchmark environment.

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
