# 🛡️ Local Privacy Guard

**Comprehensive local privacy protection for Agent Zero**

[![Agent Zero Plugin](https://img.shields.io/badge/Agent%20Zero-Plugin-blue)](https://github.com/agent0ai/agent-zero)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## What does this plugin do?

Local Privacy Guard protects your personal data when using Agent Zero with external LLM APIs. It combines three privacy measures into one plugin:

| Feature | Description |
|---------|-------------|
| 🔍 **PII Filter** | Detects and anonymizes personally identifiable information (names, emails, phone numbers, IBANs, addresses, etc.) **before** any message leaves your machine |
| 🧠 **Local Embedding** | Configures memory embeddings to run 100% locally using sentence-transformers — no memory content is sent to external APIs |
| ✅ **Privacy Verification** | Checks on startup that all privacy-relevant components are configured for local-only operation |

### Why is this needed?

Many LLM gateway providers (like Requesty) offer strong compliance features (EU-only routing, Zero Data Retention, No Training), but **PII scanning is often Enterprise-only**. This plugin compensates by anonymizing PII **locally** before data ever reaches the provider.

Similarly, Agent Zero's default memory embedding configuration may use external API endpoints. This plugin ensures embeddings are computed entirely on your machine.

---

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR LOCAL MACHINE                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Agent Zero (Docker Container)           │    │
│  │                                                      │    │
│  │  ┌─────────────┐    ┌──────────────┐    ┌────────┐  │    │
│  │  │ PII Filter  │───▶│  Anonymized  │───▶│ Memory │  │    │
│  │  │  (regex+NER)│    │    Text      │    │ (FAISS)│  │    │
│  │  └─────────────┘    └──────────────┘    └────────┘  │    │
│  │         │                                    ▲       │    │
│  │         │                            ┌───────┴──────┐│    │
│  │         │                            │   Embedding  ││    │
│  │         │                            │   100% local ││    │
│  │         │                            │  (sentence-  ││    │
│  │         │                            │  transformers)││   │
│  │         │                            └──────────────┘│    │
│  │         ▼                                           │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │     ONLY anonymized data leaves the machine  │    │    │
│  │  │    "<PERSON>", "<EMAIL>" instead of real PII   │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│                              │                              │
│                              ▼                              │
│                    ┌─────────────────┐                      │
│                    │   INTERNET      │                      │
│                    └─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Installation

### From Plugin Hub (recommended)
1. Open Agent Zero WebUI → **Settings** → **Plugins**
2. Search for **"Local Privacy Guard"**
3. Click **Install**
4. Enable the plugin

### Manual Installation
```bash
# Copy plugin to Agent Zero
cp -r local_privacy_guard /a0/usr/plugins/

# Install spaCy language models (required for NER)
/opt/venv-a0/bin/python -m spacy download de_core_news_sm
/opt/venv-a0/bin/python -m spacy download en_core_web_sm

# Restart Agent Zero
```

---

## Configuration

Go to **Settings** → **Plugins** → **Local Privacy Guard** to configure:

### PII Filter Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Master switch for PII filtering |
| `use_regex` | `true` | Fast regex pattern matching |
| `use_ner` | `true` | AI-based Named Entity Recognition (spaCy) |
| `action` | `redact` | What to do: `redact` (replace), `block` (stop message), `log_only` (testing) |
| `ner_language` | `de` | Language for NER: `de`, `en`, `fr`, `es` |
| `log_detections` | `true` | Log detected PII to agent log |
| `store_mapping` | `false` | Store placeholder→original mapping in memory (session only) |

### Local Embedding Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Configure local embeddings |
| `model` | `paraphrase-multilingual-MiniLM-L12-v2` | sentence-transformers model (multilingual, 384 dims) |
| `auto_configure_presets` | `true` | Automatically update presets.yaml on startup |
| `verify_local` | `true` | Verify embedding runs locally |

### Detected PII Types

The plugin detects and anonymizes:

| Category | Examples |
|----------|----------|
| **Contact** | Email addresses, phone numbers (DE/US/INTL) |
| **Financial** | IBAN, credit card numbers, SSN |
| **Identity** | Names (NER), passport numbers, Steuer-ID |
| **Location** | Addresses (DE/EN), postal codes, IP addresses |
| **Temporal** | Dates (multiple formats) |
| **Technical** | API keys, secrets |
| **Organizations** | Company names (NER) |

---

## Usage

Once installed and enabled, the plugin works **automatically**:

1. **Before every LLM call**, messages are scanned for PII
2. **Detected PII is replaced** with placeholders like `<EMAIL>`, `<PERSON>`, `<TELEFON>`
3. **Only anonymized text** is sent to the LLM provider
4. **Memory embeddings** are computed locally — no memory content leaves your machine

### Example

**Your message:**
> "Mein Name ist Max Mustermann, meine E-Mail ist <EMAIL> und meine IBAN ist DE89 3704 0044 0532 0130 00"

**Sent to LLM:**
> "Mein Name ist <PERSON>, meine E-Mail ist <EMAIL> und meine IBAN ist <IBAN>"

---

## Requirements

- Agent Zero (latest version)
- Python packages: `spacy`, `sentence-transformers` (installed automatically)
- spaCy language models: `de_core_news_sm`, `en_core_web_sm` (downloaded on install)

---

## Privacy & Security

- ✅ **100% local processing** — no data is sent to external services for PII detection
- ✅ **No telemetry** — the plugin does not phone home
- ✅ **No external API calls** — all detection and embedding is done locally
- ✅ **Open source** — audit the code yourself
- ⚠️ **store_mapping** — if enabled, PII is stored in memory during the session (for de-anonymization). Keep disabled for maximum privacy.

---

## Troubleshooting

### spaCy model not found
```bash
/opt/venv-a0/bin/python -m spacy download de_core_news_sm
```

### Embedding still uses external API
Check `/a0/usr/plugins/_model_config/presets.yaml` — the embedding model name must start with `sentence-transformers/`. The plugin configures this automatically on startup.

### Plugin not loading
1. Check Agent Zero logs for errors
2. Verify plugin is enabled in Settings → Plugins
3. Restart Agent Zero

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
