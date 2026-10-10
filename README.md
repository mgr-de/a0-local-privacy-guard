# 🛡️ Local Privacy Guard

**Comprehensive local privacy protection for Agent Zero**

[![Agent Zero Plugin](https://img.shields.io/badge/Agent%20Zero-Plugin-blue)](https://github.com/agent0ai/agent-zero)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## What does this plugin do?

Local Privacy Guard protects your personal data when using Agent Zero with external LLM APIs. It combines three privacy measures into one plugin:

| Feature | Description |
|---------|-------------|
| 🔒 **PII Filter** | Detects and anonymizes personally identifiable information (emails, phones, IBANs, addresses, names, etc.) **before** any message leaves your machine — with **multi-language support** |
| 🧠 **Local Embedding** | Forces memory embeddings to run 100% locally using sentence-transformers — no memory content is sent to external APIs |
| ✅ **Privacy Verification** | Checks on startup that all privacy-relevant components are configured for local-only operation |

### Why is this needed?

Many LLM gateway providers (like Requesty) offer strong compliance features (EU-only routing, Zero Data Retention, No Training), but **PII scanning is often Enterprise-only**. This plugin compensates by anonymizing PII **locally** before data ever reaches the provider.

Similarly, Agent Zero's default memory embedding configuration may use external API endpoints. This plugin ensures embeddings are computed entirely on your machine.

---

## 🌍 Multi-Language Support

The PII filter supports **multiple languages simultaneously**. Select which languages to load in the plugin settings:

| Language | Code | spaCy Model | Special PII Types |
|----------|------|-------------|-------------------|
| 🇬🇧 **English** | `en` | `en_core_web_sm` | **Always loaded** (base requirement) |
| 🇩🇪 Deutsch | `de` | `de_core_news_sm` | Steuer-ID, German addresses |
| 🇫🇷 Français | `fr` | `fr_core_news_sm` | NIR (Social Security), SIREN (Company ID) |
| 🇪🇸 Español | `es` | `es_core_news_sm` | DNI (National ID) |
| 🇮🇹 Italiano | `it` | `it_core_news_sm` | Codice Fiscale (Tax Code) |
| 🇳🇱 Nederlands | `nl` | `nl_core_news_sm` | — |
| 🇵🇹 Português | `pt` | `pt_core_news_sm` | — |
| 🇵🇱 Polski | `pl` | `pl_core_news_sm` | — |

> ⚠️ **Note**: Each additional language requires its spaCy model (~50-100 MB RAM). Select only languages you actually need.

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
│  │  │(regex+NER)  │    │    Text      │    │ (FAISS)│  │    │
│  │  └─────────────┘    └──────────────┘    └────────┘  │    │
│  │         │                                    ▲       │    │
│  │         │                            ┌───────┴──────┐│    │
│  │         │                            │   Embedding  ││    │
│  │         │                            │   100% local ││    │
│  │         │                            │  (sentence-  ││    │
│  │         │                            │  transformers)│   │
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
5. Select your languages in the plugin settings

### Manual Installation
```bash
# Copy plugin to Agent Zero
cp -r local_privacy_guard /a0/usr/plugins/

# Install spaCy language models (English is required, add others as needed)
/opt/venv-a0/bin/python -m spacy download en_core_web_sm  # REQUIRED (base)
/opt/venv-a0/bin/python -m spacy download de_core_news_sm  # German
# /opt/venv-a0/bin/python -m spacy download fr_core_news_sm  # French
# /opt/venv-a0/bin/python -m spacy download es_core_news_sm  # Spanish
# /opt/venv-a0/bin/python -m spacy download it_core_news_sm  # Italian

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
| `action` | `redact` | What to do: `redact` (replace), `block` (stop message), `log_only` (just log) |
| `languages` | `["de"]` | **List of languages** to load. English (`en`) is **always included automatically** |
| `log_detections` | `true` | Log detected PII to agent log |
| `store_mapping` | `false` | Store placeholder→original mapping in memory (session only) |

### Local Embedding Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Configure local embeddings |
| `model` | `paraphrase-multilingual-MiniLM-L12-v2` | sentence-transformers model (multilingual, 384 dims) |
| `auto_configure` | `true` | Automatically update presets.yaml on startup |
| `verify_local` | `true` | Verify embedding runs locally |

### Detected PII Types

The plugin detects and anonymizes:

| Category | Types |
|----------|-------|
| **Contact** | Email addresses, phone numbers (DE/FR/ES/IT/EN/INTL) |
| **Financial** | IBAN (all EU), credit cards, API keys |
| **Identity** | Names (NER), passport numbers, Steuer-ID (DE), DNI (ES), NIR (FR), Codice Fiscale (IT) |
| **Location** | Addresses (DE/EN/FR/ES/IT), postal codes, IP addresses |
| **Dates** | Dates (multiple formats) |
| **Technical** | URLs (with sensitive params), UUIDs, secrets |
| **Organizations** | Company names (NER) |

---

## Usage

Once installed and enabled, the plugin works **automatically**:

1. **Before every LLM call**, messages are scanned for PII (in all selected languages)
2. **Detected PII is replaced** with placeholders like `<EMAIL>`, `<PERSON>`, `<TELEFON>`
3. **Only anonymized text** is sent to the LLM provider
4. **Memory embeddings** are computed locally — no memory content leaves your machine

### Example

**You type:**
> "Mein Name ist Anna Müller, meine E-Mail ist anna@example.com und meine IBAN ist DE89 3704 0044 0532 0130 00"

**Sent to LLM:**
> "Mein Name ist <PERSON>, meine E-Mail ist <EMAIL> und meine IBAN ist <IBAN>"

---

## Requirements

- Agent Zero (latest version)
- Python packages: `spacy`, `sentence-transformers` (installed automatically)
- spaCy language models:
  - `en_core_web_sm` — **required** (always loaded)
  - Additional models based on your language selection (downloaded on install)

---

## Privacy & Security

- 🏠 **100% local processing** — no data is sent to external services for PII detection
- ✅ **No telemetry** — the plugin does not phone home
- 🔌 **No external API calls** — all detection and embedding is done locally
- ✅ **Open source** — audit the code yourself
- ⚠️ **store_mapping** — if enabled, PII is stored in memory during the session (disable for maximum privacy).

---

## Troubleshooting

### spaCy model not found
```bash
/opt/venv-a0/bin/python -m spacy download en_core_web_sm  # Always needed
/opt/venv-a0/bin/python -m spacy download de_core_news_sm  # If German enabled
```

### Embedding still uses external API
Check `/a0/usr/plugins/_model_config/presets.yaml` — the embedding model name must start with `sentence-transformers/`. The plugin configures this automatically.

### Plugin not loading
1. Check Agent Zero logs for errors
2. Verify plugin is enabled in Settings → Plugins
3. Restart Agent Zero

### Language not working
- Verify the spaCy model is installed: `/opt/venv-a0/bin/python -m spacy info <model_name>`
- Restart Agent Zero after changing languages

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.

### Adding a new language

To add support for a new language:
1. Add the spaCy model to `SPACY_MODEL_NAMES` in `helpers/pii_detector.py`
2. Add label mapping to `LABEL_MAPS`
3. Create language-specific patterns (e.g., `FRENCH_PATTERNS`) and add to `LANGUAGE_PATTERNS`
4. Add the spaCy model to `hooks.py` for auto-installation
5. Add the language checkbox to `webui/config.html`
