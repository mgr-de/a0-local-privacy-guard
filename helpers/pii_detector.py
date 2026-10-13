#!/usr/bin/env python3
"""
Local PII Detection and Anonymization Engine.

Detects PII using regex patterns and spaCy NER (Named Entity Recognition).
All processing happens locally - no data leaves the machine for detection.

Multi-language support: English (en) is ALWAYS loaded as base language.
Additional languages can be enabled in plugin settings.
"""

import re
import os
import time
import threading
try:
    from .detection_cache import spans, fingerprint, configuration
except ImportError:
    from detection_cache import spans, fingerprint, configuration
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# spaCy models are loaded lazily to reduce startup cost when plugin is disabled
_nlp_models: Dict[str, object] = {}
_nlp_lock = threading.RLock()

# spaCy model names per language
# English (en) is ALWAYS loaded as the base language
SPACY_MODEL_NAMES: Dict[str, str] = {
    "en": "en_core_web_sm",       # Base - always installed
    "de": "de_core_news_sm",
    "fr": "fr_core_news_sm",
    "es": "es_core_news_sm",
    "it": "it_core_news_sm",
    "nl": "nl_core_news_sm",
    "pt": "pt_core_news_sm",
    "pl": "pl_core_news_sm",
}

# Base language - always loaded, cannot be disabled
BASE_LANGUAGE = "en"

# Language-specific label mappings (spaCy labels can vary slightly by language)
LABEL_MAPS: Dict[str, Dict[str, str]] = {
    "en": {
        "PERSON": "PERSON",
        "ORG": "ORGANISATION",
        "GPE": "ORT",
        "LOC": "ORT",
        "DATE": "DATUM",
        "TIME": "DATUM",
    },
    "de": {
        "PER": "PERSON",
        "LOC": "ORT",
        "ORG": "ORGANISATION",
        "DATE": "DATUM",
        "TIME": "DATUM",
    },
    "fr": {
        "PER": "PERSON",
        "LOC": "ORT",
        "ORG": "ORGANISATION",
        "DATE": "DATUM",
        "TIME": "DATUM",
    },
    "es": {
        "PER": "PERSON",
        "LOC": "ORT",
        "ORG": "ORGANISATION",
        "DATE": "DATUM",
        "TIME": "DATUM",
    },
    "it": {
        "PER": "PERSON",
        "LOC": "ORT",
        "ORG": "ORGANISATION",
        "DATE": "DATUM",
        "TIME": "DATUM",
    },
}


def _get_nlp(language: str = BASE_LANGUAGE):
    """Lazy-load spaCy model for the given language."""
    global _nlp_models
    if language in _nlp_models:
        return _nlp_models[language]
    try:
        import spacy
        model_name = SPACY_MODEL_NAMES.get(language)
        if model_name is None:
            return None
        nlp = spacy.load(model_name)
        _nlp_models[language] = nlp
        return nlp
    except Exception:
        return None


def get_available_languages() -> List[str]:
    """Return list of languages that have spaCy models configured."""
    return list(SPACY_MODEL_NAMES.keys())


def get_installed_languages() -> List[str]:
    """Return list of languages with successfully loaded spaCy models."""
    installed = []
    for lang in SPACY_MODEL_NAMES.keys():
        if _get_nlp(lang) is not None:
            installed.append(lang)
    return installed


@dataclass
class PIIDetection:
    """Represents a single PII detection."""
    pii_type: str          # e.g., "EMAIL", "TELEFON", "IBAN"
    original: str          # The original PII text
    start: int             # Start position in text
    end: int               # End position in text
    replacement: str       # The placeholder to use
    source: str            # "regex" or "ner"
    confidence: float = 1.0
    language: str = ""     # Detected language (for NER detections)


@dataclass
class FilterResult:
    """Result of PII filtering."""
    original_text: str
    filtered_text: str
    detections: List[PIIDetection] = field(default_factory=list)
    mapping: Dict[str, str] = field(default_factory=dict)

    @property
    def has_pii(self) -> bool:
        return len(self.detections) > 0

    @property
    def pii_count(self) -> int:
        return len(self.detections)


# ============================================================================
# UNIVERSAL PATTERNS (work across all languages)
# ============================================================================
UNIVERSAL_PATTERNS: Dict[str, Tuple[str, str]] = {
    # Email addresses
    "EMAIL": (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "<EMAIL>"
    ),

    # International Bank Account Number (IBAN) with spaces
    "IBAN": (
        r"\b[A-Z]{2}\d{2}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}(?:[\s]?[A-Z0-9]{1,2})?\b",
        "<IBAN>"
    ),

    # German IBAN without spaces (DE)
    "IBAN_DE": (
        r"\bDE\d{20}\b",
        "<IBAN>"
    ),

    # US Social Security Number
    "SSN": (
        r"\b\d{3}-\d{2}-\d{4}\b",
        "<SSN>"
    ),

    # Credit card numbers (Visa, Mastercard, Amex, etc.)
    "CREDIT_CARD": (
        r"\b(?:\d{4}[\s-]?){3}\d{4}\b",
        "<KREDITKARTE>"
    ),

    # IP addresses (IPv4)
    "IP": (
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "<IP>"
    ),

    # Dates (various formats)
    "DATUM": (
        r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b"
        r"|\b\d{4}-\d{2}-\d{2}\b"
        r"|\b\d{1,2}\.\s?(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s?\d{2,4}\b",
        "<DATUM>"
    ),

    # API keys (common prefixes)
    "API_KEY": (
        r"\b(?:sk|pk|api|key|secret|token)[-_]?[a-zA-Z0-9]{20,}\b",
        "<API_KEY>"
    ),

    # German Steuer-ID (11 digits, first digit 1-9, NOT starting with 0)
    "STEUER_ID": (
        r"(?<!\d)[1-9]\d{10}(?!\d)",
        "<STEUER_ID>"
    ),

    # Passport numbers (letter + 8 digits, common format)
    "REISEPASS": (
        r"\b[A-Z]\d{8}\b",
        "<REISEPASS>"
    ),

    # International phone numbers (simplified)
    "TELEFON_INTL": (
        r"\+\d{1,3}[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,9}",
        "<TELEFON>"
    ),

    # URLs (may contain sensitive query params)
    "URL": (
        r"\bhttps?://[^\s<>\"]+\b",
        "<URL>"
    ),

    # UUIDs
    "UUID": (
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        "<UUID>"
    ),
}

# ============================================================================
# GERMAN-SPECIFIC PATTERNS
# ============================================================================
GERMAN_PATTERNS: Dict[str, Tuple[str, str]] = {
    # German phone numbers
    "TELEFON": (
        r"(?<![\w.])(?:\+49|0049|0)[\s./()-]?\d{2,5}[\s./()-]?\d{1,4}[\s./()-]?\d{1,9}(?![\w.])",
        "<TELEFON>"
    ),

    # German postal codes (standalone 5 digits)
    "PLZ": (
        r"\b\d{5}\b(?=\s|$|[,.])",
        "<PLZ>"
    ),

    # German addresses (street + number) - includes ß in straße
    "ADRESSE": (
        r"\b(?:\w*[Ss]tra[ßSs]e|[Ss]trasse|\w*[Ss]tr\.?|[Ww]eg|[Pp]latz|[Aa]llee|[Gg]asse|[Rr]ing|[Dd]amm|[Uu]fer|[Cc]haussee|[Pp]romenade)\s+\d+[a-zA-Z]?\b",
        "<ADRESSE>"
    ),
}

# ============================================================================
# ENGLISH-SPECIFIC PATTERNS
# ============================================================================
ENGLISH_PATTERNS: Dict[str, Tuple[str, str]] = {
    # English phone numbers (US/UK style)
    "TELEFON": (
        r"(?<![\w.])(?:\+1|1|0)?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w.])",
        "<TELEFON>"
    ),

    # US ZIP codes (standalone 5 digits or 5+4)
    "PLZ": (
        r"\b\d{5}(?:-\d{4})?\b",
        "<PLZ>"
    ),

    # English addresses (number + street + type)
    "ADDRESS": (
        r"\b\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Blvd|Boulevard)\b",
        "<ADRESSE>"
    ),
}

# ============================================================================
# FRENCH-SPECIFIC PATTERNS
# ============================================================================
FRENCH_PATTERNS: Dict[str, Tuple[str, str]] = {
    # French phone numbers (01-05 or +33)
    "TELEFON": (
        r"(?<![\w.])(?:\+33|0033|0)[\s.-]?[1-9][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}(?![\w.])",
        "<TELEFON>"
    ),

    # French postal codes (5 digits)
    "PLZ": (
        r"\b\d{5}\b(?=\s|$|[,.])",
        "<PLZ>"
    ),

    # French addresses (rue, avenue, boulevard, etc.)
    "ADRESSE": (
        r"\b(?:[Rr]ue|[Aa]venue|[Aa]v\.|[Bb]oulevard|[Bb]d\.|[Pp]lace|[Pp]l\.|[Cc]hemin|[Cc]h\.|[Ii]mpasse|[Ii]mp\.|[Qq]uai|[Aa]llée|[Aa]ll)\s+[^\s]+(?:\s+[^\s]+){0,2}\s+\d+[a-zA-Z]?\b",
        "<ADRESSE>"
    ),

    # French NIR (Numéro de sécurité sociale - 15 digits)
    "NIR": (
        r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b",
        "<NIR>"
    ),

    # French SIREN (9 digits, company registration)
    "SIREN": (
        r"(?<!\d)\d{9}(?!\d)",
        "<SIREN>"
    ),
}

# ============================================================================
# SPANISH-SPECIFIC PATTERNS
# ============================================================================
SPANISH_PATTERNS: Dict[str, Tuple[str, str]] = {
    # Spanish phone numbers (6xx, 7xx, 9xx or +34)
    "TELEFON": (
        r"(?<![\w.])(?:\+34|0034)?[\s.-]?[6-9]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}(?![\w.])",
        "<TELEFON>"
    ),

    # Spanish postal codes (5 digits)
    "PLZ": (
        r"\b\d{5}\b(?=\s|$|[,.])",
        "<PLZ>"
    ),

    # Spanish addresses (calle, avenida, plaza, etc.)
    "ADRESSE": (
        r"\b(?:[Cc]alle|[Cc]/|[Aa]vda|[Aa]venida|[Pp]laza|[Pp]za|[Pp]aseo|[Cc]amino|[Cc]arretera)\s+[^\s]+(?:\s+[^\s]+){0,2}\s+\d+[a-zA-Z]?\b",
        "<ADRESSE>"
    ),

    # Spanish DNI (8 digits + letter)
    "DNI": (
        r"\b\d{8}[A-Za-z]\b",
        "<DNI>"
    ),
}

# ============================================================================
# ITALIAN-SPECIFIC PATTERNS
# ============================================================================
ITALIAN_PATTERNS: Dict[str, Tuple[str, str]] = {
    # Italian phone numbers (+39 or 0x)
    "TELEFON": (
        r"(?<![\w.])(?:\+39|0039)?[\s.-]?0?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?![\w.])",
        "<TELEFON>"
    ),

    # Italian postal codes (CAP - 5 digits)
    "PLZ": (
        r"\b\d{5}\b(?=\s|$|[,.])",
        "<PLZ>"
    ),

    # Italian addresses (via, piazza, corso, etc.)
    "ADRESSE": (
        r"\b(?:[Vv]ia|[Vv]iale|[Pp]iazza|[Pp]za|[Cc]orso|[Ll]argo|[Ss]trada|[Pp]iazzale)\s+[^\s]+(?:\s+[^\s]+){0,2}\s+\d+[a-zA-Z]?\b",
        "<ADRESSE>"
    ),

    # Italian Codice Fiscale (16 chars, alphanumeric)
    "CODICE_FISCALE": (
        r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b",
        "<CODICE_FISCALE>"
    ),
}

# Language -> patterns mapping
LANGUAGE_PATTERNS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "de": GERMAN_PATTERNS,
    "en": ENGLISH_PATTERNS,
    "fr": FRENCH_PATTERNS,
    "es": SPANISH_PATTERNS,
    "it": ITALIAN_PATTERNS,
}


# ============================================================================
# PII FILTER ENGINE
# ============================================================================
class PIIFilter:
    """Main PII filtering engine with multi-language support."""

    # Common words that spaCy often misclassifies as entities
    NER_SKIP_WORDS = {
        "tel", "email", "mail", "datum", "name", "ort", "adresse", "address",
        "telefon", "phone", "date", "call", "fax", "ip", "web", "key", "api",
        "herr", "frau", "dr", "prof", "monsieur", "madame", "mme", "mr",
        "señor", "señora", "sr", "sra", "signore", "signora", "sig",
        "iban", "ready", "okay", "confirm", "summarize", "bestätige",
        "geschäftspartner", "partner", "partnership", "contacts",
        "user", "assistant", "agent", "agent zero", "response", "tool", "tools",
        "css", "html", "javascript", "python", "typescript", "playwright", "json", "vision_load", "code_execution_tool", "call_subordinate", "english", "german",
        "browser", "skills_tool", "memory_load", "memory_save", "memory_delete",
        "text_editor", "text_editor_remote", "a0", "workdir", "paths", "query",
        "action", "text", "selector", "ref", "browser_id", "value", "type",
        "content", "state", "url", "submit", "metadata", "parameters",
        "boolean", "bool", "number", "integer", "float", "string", "str", "null", "object", "array",
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.scope = self.config.get('_cache_scope') or os.urandom(16)
        requested_backend = self.config.get('backend', 'local')
        if requested_backend not in {'local', 'presidio', 'nym'}:
            raise ValueError('Unknown local detection backend.')
        # Retired evaluation settings remain readable without rewriting user
        # files or mapping rows. There is exactly one production detector.
        self.backend = 'local'
        self.config = {k: v for k, v in self.config.items()
                       if not k.startswith(('nym_', 'presidio_'))}
        self.config['backend'] = 'local'
        self.signature = configuration({k:v for k,v in self.config.items() if not k.startswith('_')})
        self.metrics = {'ner_seconds':0.0,'regex_seconds':0.0,'cache_hits':0,'ner_units':0,'characters':0}
        self.use_regex = self.config.get("use_regex", True)
        self.use_ner = self.config.get("use_ner", True)
        self.action = self.config.get("action", "redact")
        self.custom_patterns = self.config.get("custom_patterns", [])
        self.ner_entity_types = self.config.get("ner_entity_types", [])
        self.store_mapping = self.config.get("store_mapping", False)
        self.placeholder_format = self.config.get("placeholder_format", "<{type}>")

        # Languages for NER - English always included as base
        ner_languages = self.config.get("languages", ["de"])
        if BASE_LANGUAGE not in ner_languages:
            ner_languages = [BASE_LANGUAGE] + list(ner_languages)
        self.ner_languages = ner_languages
        self.skip_words = set(self.NER_SKIP_WORDS)
        if self.use_ner:
            import importlib
            for language in ner_languages:
                try:
                    self.skip_words.update(importlib.import_module(f"spacy.lang.{language}.stop_words").STOP_WORDS)
                except ImportError:
                    pass
        # Primary language for language-specific regex patterns
        self.primary_language = ner_languages[0] if ner_languages else BASE_LANGUAGE

        # Compile regex patterns
        self.compiled_patterns: List[Tuple[str, re.Pattern, str]] = []
        if self.use_regex:
            all_patterns = dict(UNIVERSAL_PATTERNS)

            # Add patterns for ALL configured languages
            for lang in self.ner_languages:
                lang_patterns = LANGUAGE_PATTERNS.get(lang, {})
                all_patterns.update(lang_patterns)

            # Add custom patterns
            for cp in self.custom_patterns:
                all_patterns[cp.get("name", "CUSTOM")] = (cp.get("regex", ""), "<CUSTOM>")

            # Compile all patterns
            for name, (pattern, replacement) in all_patterns.items():
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    if compiled.match(''):
                        raise ValueError('A local filter pattern matches empty text. Correct the custom pattern before continuing.')
                    self.compiled_patterns.append((name, compiled, replacement))
                except re.error:
                    raise ValueError('A local filter pattern is invalid. Correct custom pattern syntax before continuing.') from None

    def is_non_entity(self, value):
        normalized=' '.join(value.casefold().split()).strip(' ,.:;')
        return normalized in self.skip_words or normalized in {
            'ich bin','ich bin herr','ich bin frau','i am','i am mr','i am mrs','i am ms',
            'my name is','mein name ist',
        }

    def _format_placeholder(self, pii_type: str, replacement: str) -> str:
        """Format the placeholder for a detection."""
        if replacement.startswith("<") and replacement.endswith(">"):
            return replacement
        if "{type}" in self.placeholder_format:
            return self.placeholder_format.format(type=pii_type)
        return replacement

    def _detect_regex(self, text: str) -> List[PIIDetection]:
        detections = []
        for name, pattern, replacement in self.compiled_patterns:
            for match in pattern.finditer(text):
                placeholder = self._format_placeholder(name, replacement)
                detections.append(PIIDetection(
                    pii_type=name,
                    original=match.group(),
                    start=match.start(),
                    end=match.end(),
                    replacement=placeholder,
                    source="regex",
                    confidence=1.0
                ))
        return detections

    def _detect_ner(self, text: str) -> List[PIIDetection]:
        """Detect PII using NER spaCy models for all configured languages."""
        if not self.use_ner:
            return []

        started=time.perf_counter()
        paragraphs=list(re.finditer(r'[^\n]+',text))
        jobs={};results={};pending={};models={}
        de_words=set('der die das und ist sind mit für von nicht schuldet verheiratet personen bleibt unverändert beziehungen geschäftspartner telefon'.split())
        en_words=set('the and is are with for from not owes married people unchanged relationships return only to of'.split())
        for i,paragraph in enumerate(paragraphs):
            unit=paragraph.group()
            if len(unit.strip())<=1:continue
            languages=self.ner_languages
            if set(languages)=={'en','de'}:
                words=re.findall(r'\w+',unit.casefold())
                german=sum(w in de_words for w in words);english=sum(w in en_words for w in words)
                if german>=2 and german>=english:languages=['de']
                elif english>=2 and english>german:languages=['en']
            for lang in languages:
                nlp=_get_nlp(lang)
                if nlp is None:continue
                # Paragraphs are fixed independent recognition units. No outside
                # context is supplied to either backend. Model identity/version
                # and the complete recognizer configuration invalidate reuse.
                if lang not in models:models[lang]=configuration({'name':SPACY_MODEL_NAMES.get(lang),'meta':getattr(nlp,'meta',{}),'instance':id(nlp)})
                model=models[lang]
                key=(self.scope,self.signature,self.backend,lang,model,fingerprint(unit),'paragraph-v1')
                cached=spans.get(key)
                if cached is not None:
                    self.metrics['cache_hits']+=1;results[(i,lang)]=cached
                else:
                    if key not in pending:jobs.setdefault(lang,[]).append((i,unit,key,nlp));pending[key]=[]
                    pending[key].append(i)
        for lang,work in jobs.items():
            with _nlp_lock:
                nlp=work[0][3]
                docs=nlp.pipe([w[1] for w in work],batch_size=32) if hasattr(nlp,'pipe') else (nlp(w[1]) for w in work)
                label_map=LABEL_MAPS.get(lang,{**LABEL_MAPS[BASE_LANGUAGE],'PER':'PERSON','persName':'PERSON','orgName':'ORGANISATION','placeName':'ORT','geogName':'ORT','date':'DATUM','time':'DATUM'})
                batches=([ (ent.start_char,ent.end_char,label_map.get(ent.label_,ent.label_),'ner',0.85,lang)
                    for ent in doc.ents if (ent.label_ in self.ner_entity_types if self.ner_entity_types else ent.label_ in label_map)
                    and not (len(ent.text.strip())==1 and ent.text.strip().isalpha()) ] for doc in docs)
                for (i,unit,key,_),hits in zip(work,batches,strict=True):
                    hits=tuple(hits);spans.put(key,hits)
                    for position in pending[key]:results[(position,lang)]=hits
                    self.metrics['ner_units']+=1;self.metrics['characters']+=len(unit)
        detections=[];seen=set()
        # Restore original paragraph/language priority, independent of batching.
        for i,paragraph in enumerate(paragraphs):
            for lang in self.ner_languages:
                for start,end,kind,source,score,language in results.get((i,lang),()):
                    original=paragraph.group()[start:end]
                    key=(start+paragraph.start(),end+paragraph.start(),original.lower())
                    if key in seen:continue
                    seen.add(key)
                    detections.append(PIIDetection(kind,original,key[0],key[1],self._format_placeholder(kind,f'<{kind}>'),source,score,language))
        self.metrics['ner_seconds']+=time.perf_counter()-started
        return detections

    def _merge_detections(self, detections: List[PIIDetection]) -> List[PIIDetection]:
        """Merge detections. Regex ALWAYS wins over NER on overlap."""
        # Select whole structured values first, then non-overlapping names.
        # Never apply two replacements to overlapping original offsets.
        priority = {"IBAN_DE": 0, "IBAN": 0, "EMAIL": 1, "KREDITKARTE": 2}
        regex_dets = sorted((d for d in detections if d.source == "regex"),
                            key=lambda d: (priority.get(d.pii_type, 3), -(d.end-d.start), d.start))
        selected_regex = []
        for det in regex_dets:
            if not any(det.start < other.end and other.start < det.end for other in selected_regex):
                selected_regex.append(det)
        regex_dets = selected_regex
        ner_dets = [d for d in detections if d.source == "ner"]

        # Filter NER false positives: skip single known non-PII words
        ner_dets = [d for d in ner_dets if not (
            self.is_non_entity(d.original)
        )]

        # Remove NER detections that overlap with regex detections
        filtered_ner = []
        for ner in ner_dets:
            overlaps = any(ner.start < reg.end and reg.start < ner.end for reg in regex_dets)
            if not overlaps:
                filtered_ner.append(ner)

        selected_ner = []
        for det in sorted(filtered_ner, key=lambda d: (-(d.end-d.start), -d.confidence, d.start)):
            if not any(det.start < other.end and other.start < det.end for other in selected_ner):
                selected_ner.append(det)
        merged = sorted(regex_dets + selected_ner, key=lambda d: d.start)
        return merged

    def filter(self, text: str, *, code_hint: str = '') -> FilterResult:
        """Filter PII from text."""
        if not text:
            return FilterResult(original_text="", filtered_text="", detections=[], mapping={})

        all_detections: List[PIIDetection] = []
        from usr.plugins.local_privacy_guard.helpers.code_regions import analysis_text
        scan = analysis_text(text, code_hint)
        strong = {'EMAIL', 'IBAN', 'IBAN_DE', 'API_KEY'}
        strong.update(pattern.get('name', 'CUSTOM') for pattern in self.config.get('custom_patterns', []))

        if self.use_regex:
            started=time.perf_counter()
            all_detections.extend(self._detect_regex(scan))
            if scan != text:
                # Explicit custom rules and recognizable contact/key formats
                # also cover unquoted code; numeric syntax is preserved.
                all_detections.extend(hit for hit in self._detect_regex(text) if hit.pii_type in strong)
            self.metrics['regex_seconds']+=time.perf_counter()-started
        if self.use_ner:
            all_detections.extend(self._detect_ner(scan))

        # A recognition span must never bridge masked syntax between literals.
        all_detections = [hit for hit in all_detections if
            scan[hit.start:hit.end] == text[hit.start:hit.end] or
            (hit.source == 'regex' and scan != text and hit.pii_type in strong)]

        detections = self._merge_detections(all_detections)

        # Apply replacements from end to start to preserve positions
        filtered = text
        mapping: Dict[str, str] = {}
        for det in sorted(detections, key=lambda d: d.start, reverse=True):
            filtered = filtered[:det.start] + det.replacement + filtered[det.end:]
            if self.store_mapping:
                mapping[det.replacement] = det.original

        return FilterResult(
            original_text=text,
            filtered_text=filtered,
            detections=detections,
            mapping=mapping
        )

    def get_loaded_languages(self) -> List[str]:
        """Return list of languages with successfully loaded spaCy models."""
        loaded = []
        for lang in self.ner_languages:
            if _get_nlp(lang) is not None:
                loaded.append(lang)
        return loaded


def create_filter(config: dict = None) -> PIIFilter:
    """Factory function to create a PIIFilter instance."""
    return PIIFilter(config)
