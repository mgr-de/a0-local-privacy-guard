# Independent Gateway enforcement — 14 October 2026

The central manager now supports Gateway enforcement while Local Guard is disabled. The operator-owned privacy-agent/mode.json explicitly stores local_guard_enabled=false; absent mode files retain full text protection and invalid non-boolean modes block. Central activation stays active. Requesty profile/key ownership, central minimum policy, preset validation and provider restrictions remain enforced. The Local Guard is not wrapped around models and neither PII nor its Secret checks run.

The authenticated setup API exposes gateway_only with explicit KEEP_GATEWAY_DISABLE_LOCAL_GUARD confirmation and an idle-chat check. The UI requires a separate checkbox and labels the active Gateway / disabled Local Guard state. This does not silently re-enable Local Guard on restart, configuration changes or activation. Reactivating Local Guard requires an explicit later operator decision and review.

Native model getters attach a process-local weak reference to their owning agent. Gateway-only central checks use that ownership, instead of requiring a Local Guard filtering proof. Unowned external calls and cross-profile cached wrappers remain blocked. Weak references are not transmitted as request parameters. The ordinary full-protection mode retains its existing text proof requirements.

The existing native-preset policy bridge remains active in Gateway-only mode. Gateway rules still control valid Requesty models and required local embeddings. Disabling the text detector must not restore provider defaults or allow invalid presets. Legacy sidecar installations retain their routes; the provider chooser remains restricted under central activation.

This is a coordinated Git change across Manager, Gateway and Local Guard; it does not publish a new suite release. No credentials, original mappings or private chat text are included in fixtures.

Validation: isolated A0 2.14 — 184 Local + 79 Gateway + 102 Manager Python tests, 32 subtests and 40 Node tests passed. No paid model calls.
