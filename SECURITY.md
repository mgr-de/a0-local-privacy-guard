# Security policy

A0 Privacy Suite is an independent community beta for local Agent Zero installations. Version 0.9.3 is supported on a best-effort basis; older releases and evaluation archive branches are not supported for new deployments. There is no security audit certification or completeness guarantee.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/mgr-de/a0-local-privacy-guard/security/advisories/new) for suspected bypasses, credential exposure, path traversal or other vulnerabilities. Do not open a public issue containing secrets, personal data, original chats, mappings or a working exploit. Provide the suite and Agent Zero versions, a minimal synthetic reproduction, expected and observed behavior, and whether instance protection or a Developer exception was active. Rotate exposed credentials through their provider. Reports will be triaged as maintainer availability permits; no response-time or bounty promise is made.

## Deployment and limits

Bind Agent Zero to loopback or a trusted private network. Strongly prefer operator authentication, especially before granting unmasked Developer chats. When no login is configured, everyone who can access the UI can manage these grants. Authentication becomes mandatory at these endpoints when configured in A0. CSRF checks remain enabled.

Supported model text is screened locally; detection can miss PII. A Developer exception sends the entire model text context without PII replacement, including recalled memory and subordinate-agent text, while Secret screening remains active. Secret screening is detection, not a guarantee against every possible credential. Requesty routing/provider metadata checks do not independently audit provider practices or verify Requesty's own retention. Images, browser traffic, raw tool networking and arbitrary filesystem access have separate limits; this suite is not a sandbox.

Original mappings, keys and chats remain local user data. Stored keys and mappings are not encrypted by this plugin; protect the host, backups and account. Never attach production state to a support ticket. Update all suite components together and restart A0. An active central policy must be explicitly deactivated before disabling or uninstalling required components. Deactivation does not automatically erase user data.
