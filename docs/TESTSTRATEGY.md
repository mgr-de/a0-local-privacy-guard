# Test Strategy — Local Privacy Guard

## Goals

1. Prevent regressions of the fixed defects (dead extension point, config key
   mismatch, verifier KeyError, unsafe backup/restore, hardcoded paths,
   non-conventional webui).
2. Keep every guarantee of the plugin testable without a running Agent Zero
   instance, real model downloads, or network access.
3. Make the backup/restore lifecycle provably generation-safe.

## Test levels

| Level | Scope | Location | Runner |
|---|---|---|---|
| Unit | Pure helpers (embedding_config, privacy_verifier, pii_detector) | `tests/test_embedding_config.py`, `tests/test_privacy_verifier.py` | pytest, offline |
| Unit | Extension wiring (agent_init, chat + util filters) with fake agents | `tests/test_extensions.py` | pytest, offline |
| Convention | webui/config.html patterns, plugin.yaml schema, extension layout | `tests/test_webui_and_manifest.py` | pytest, offline |
| Smoke | hooks.py uninstall restore contract | `tests/test_webui_and_manifest.py` | pytest, offline |
| Integration (manual) | Full install → agent start → uninstall in a real Agent Zero instance | checklist below | human |

## Isolation technique

- `tests/conftest.py` inserts a production-like project root into `sys.path`
  so imports use the exact runtime paths (`usr.plugins.local_privacy_guard...`).
- Framework modules (`helpers.extension`, `helpers.plugins`) are replaced by
  in-memory stubs; extension classes therefore never need a running backend.
- All file tests run against `tmp_path` fixtures; the real `presets.yaml` is
  never touched.
- `A0_ROOT` fallback of the path resolution is covered explicitly
  (`test_presets_path_resolution_overridable`).

## Key regression tests (defect → test)

| Original defect | Regression test |
|---|---|
| `startup` extension point never dispatched | `test_agent_init_execute_is_sync`, `test_no_flattened_extension_folders` |
| `auto_configure` vs `auto_configure_presets` mismatch | `test_config_html_binds_auto_configure_key`, `test_default_config_matches_ui_keys`, `test_agent_init_respects_auto_configure_off` |
| `verify_embedding` KeyError: model | `test_verify_embedding_no_keyerror_on_valid_local` |
| Full-file backup overwrites user changes | `test_restore_preserves_user_changes`, `test_restore_never_resurrects_removed_presets` |
| Backup not the original state (A→B→C restored B) | `test_generation_safety_a_to_b_to_c_restores_a`, `test_journal_consumed_after_restore_no_replay`, `test_user_change_between_generations_is_recorded` |
| Stale journal replayed by later installs | `test_journal_consumed_after_restore_no_replay` |
| Hardcoded `/a0/...` presets path | `test_presets_path_resolution_overridable` |
| Non-atomic preset writes | `test_atomic_write_leaves_no_temp_files` |
| Utility calls not filtered | `test_util_filter_redacts_strings`, `test_util_filter_block_mode`, `test_filters_share_cache` |
| requesty UI component without backend checker | `test_run_verification_requesty_component_known`, `test_verify_requesty_detects_gateway` |
| Inline script / fetch in config.html | `test_config_html_uses_store_gate_pattern` |

## Manual integration checklist (per release)

1. Install the plugin into a clean Agent Zero instance (Docker) via the
   Plugins UI; verify spaCy models install and `hooks.install()` reports no errors.
2. Start a chat; verify the log shows `[Local Privacy Guard] Configured local
   embedding model: ...` exactly once per context (not per sub-agent).
3. Send a message containing an email address; verify the outgoing request is
   redacted (provider-side request log or PII detection log entry).
4. Trigger a utility call (e.g. chat naming) with PII; verify redaction log.
5. Change the embedding model in the UI; restart; verify presets.yaml contains
   the new model and a backup journal exists.
6. While installed, change a preset manually; uninstall the plugin; verify
   your manual change survived and no removed presets reappeared.
7. Uninstall → reinstall without changing anything → uninstall again;
   verify the second uninstall reports "no backup found".
8. Verify the plugin settings modal renders all sections and Save persists.

## Running

```bash
python -m pytest tests/ -q
```

Requirements: `pytest`, `pyyaml` (no spaCy, no sentence-transformers, no
network needed; NER-dependent paths degrade gracefully and are covered by
the manual checklist).

## Settings redesign 1.2.0

`tests/test_ui_diagnostics.py` checks the fixed synthetic example using real built-in regex logic, redact/block/log-only modes, disabled detection, invalid input and missing name models. It confirms that arbitrary custom patterns and mapping persistence are not used in the UI example. `node --test tests/test_privacy_store.mjs` checks changed settings, persistent errors and late results after closing.

The HTML convention test permits one external store module and continues to reject inline scripts and raw fetch calls. The example API inherits Agent Zero authentication and CSRF requirements. It does not modify presets or configuration.

In an isolated Agent Zero v2.13 instance, verify the real settings dialog, save/scope behavior and the example API. At 390px viewport width, check all language labels and controls; with keyboard navigation check focus visibility and expanded details. Successful regex output must not hide unavailable spaCy models. A browser example is not a provider privacy audit or an active-chat protection check.
