#!/usr/bin/env python3
"""
Local PII Detection and Anonymization Engine.

Detects PII using regex patterns and spaCy NER (Named Entity Recognition).
All processing happens locally - no data leaves the machine for detection.
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

# spaCy models are loaded lazily to reduce startup cost when plugin is disabled
_nlp_models: Dict[str, object] = {}


def _get_nlp(language: str = "de"):
    """Lazy-load spaCy model for the given language."""
    global _nlp_models
    if language in _nlp_models:
        return _nlp_models[language]
    try:
        import spacy
        model_name = f"{language}_core_news_sm" if language == "de" else f"{language}_core_web_sm"
        nlp = spacy.load(model_name)
        _nlp_models[language] = nlp
        return nlp
    except Exception:
        return None


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


# Standard regex patterns for common PII types
# Use raw strings (r-prefix) with SINGLE backslashes for regex metacharacters
# In Python source: r"\b" means the string contains: \b (word boundary in regex)
REGEX_PATTERNS: Dict[str, Tuple[str, str]] = {
    # Email addresses
    "EMAIL": (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "<EMAIL>"
    ),

    # German phone numbers (simplified pattern - no nested groups)
    "TELEFON": (
        r"(?<![\w.])(?:\+49|0049|0)[\s./()-]?\d{2,5}[\s./()-]?\d{1,4}[\s./()-]?\d{1,9}(?![\w.])",
        "<TELEFON>"
    ),

    # International phone numbers
    "TELEFON_INTL": (
        r"\+\d{1,3}[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,9}",
        "<TELEFON>"
    ),

    # International Bank Account Number (IBAN) with spaces
    "IBAN": (
        r"\b[A-Z]{2}\d{2}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}(?:[\s]?[A-Z0-9]{1,2})?\b",
        "<IBAN>"
    ),

    # German IBAN without spaces
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

    # German postal codes (standalone 5 digits)
    "PLZ": (
        r"\b\d{5}\b(?=\s|$|[,.])",
        "<PLZ>"
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
        r"|\b\d{1,2}\.\s?(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s?\d{2,4}\b",
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

    # Passport numbers (various formats)
    "REISEPASS": (
        r"\b[A-Z]\d{8}\b",
        "<REISEPASS>"
    ),
}

# German-specific patterns
GERMAN_PATTERNS: Dict[str, Tuple[str, str]] = {
    # German addresses (street + number) - includes ß in straße
    "ADRESSE": (
        r"\b(?:\w*(?:stra\u00dfe|strasse)|str\.|weg|platz|allee|gasse|ring|damm|ufer|chaussee|promenade)\s+\d+[a-zA-Z]?\b",
        "<ADRESSE>"
    ),
}

# English-specific patterns
ENGLISH_PATTERNS: Dict[str, Tuple[str, str]] = {
    # English addresses (number + street + type)
    "ADDRESS": (
        r"\b\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Blvd|Boulevard)\b",
        "<ADRESSE>"
    ),
}


class PIIFilter:
    """Main PII filtering engine."""

    # Common words that spaCy often misclassifies as entities
    NER_SKIP_WORDS = {
        "tel", "email", "mail", "datum", "name", "ort", "adresse",
        "telefon", "date", "call", "fax", "ip", "web", "key", "api",
        "herr", "frau", "dr", "prof",
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.use_regex = self.config.get("use_regex", True)
        self.use_ner = self.config.get("use_ner", True)
        self.ner_language = self.config.get("ner_language", "de")
        self.action = self.config.get("action", "redact")
        self.custom_patterns = self.config.get("custom_patterns", [])
        self.ner_entity_types = self.config.get("ner_entity_types", [])
        self.store_mapping = self.config.get("store_mapping", False)
        self.placeholder_format = self.config.get("placeholder_format", "<{type}>")

        # Compile regex patterns
        self.compiled_patterns: List[Tuple[str, re.Pattern, str]] = []
        if self.use_regex:
            all_patterns = dict(REGEX_PATTERNS)
            if self.ner_language == "de":
                all_patterns.update(GERMAN_PATTERNS)
            else:
                all_patterns.update(ENGLISH_PATTERNS)
            for cp in self.custom_patterns:
                all_patterns[cp.get("name", "CUSTOM")] = (cp.get("regex", ""), "<CUSTOM>")
            for name, (pattern, replacement) in all_patterns.items():
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self.compiled_patterns.append((name, compiled, replacement))
                except re.error:
                    pass

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
        if not self.use_ner:
            return []
        nlp = _get_nlp(self.ner_language)
        if nlp is None:
            return []
        detections = []
        doc = nlp(text)
        for ent in doc.ents:
            label_map = {
                "PER": "PERSON", "PERSON": "PERSON",
                "LOC": "ORT", "GPE": "ORT",
                "ORG": "ORGANISATION",
                "DATE": "DATUM", "TIME": "DATUM",
            }
            pii_type = label_map.get(ent.label_, ent.label_)
            if self.ner_entity_types and ent.label_ not in self.ner_entity_types:
                continue
            placeholder = self._format_placeholder(pii_type, f"<{pii_type}>")
            detections.append(PIIDetection(
                pii_type=pii_type,
                original=ent.text,
                start=ent.start_char,
                end=ent.end_char,
                replacement=placeholder,
                source="ner",
                confidence=0.85
            ))
        return detections

    def _merge_detections(self, detections: List[PIIDetection]) -> List[PIIDetection]:
        """Merge detections. REGEX ALWAYS wins over NER on overlap."""
        regex_dets = [d for d in detections if d.source == "regex"]
        regex_dets.sort(key=lambda d: d.start)
        ner_dets = [d for d in detections if d.source == "ner"]

        # Filter NER false positives: skip single common words
        ner_dets = [d for d in ner_dets if not (
            d.original.lower().strip() in self.NER_SKIP_WORDS and len(d.original.split()) == 1
        )]

        # Remove NER detections that overlap with regex detections
        filtered_ner = []
        for ner in ner_dets:
            overlaps = any(ner.start < reg.end and reg.start < ner.end for reg in regex_dets)
            if not overlaps:
                filtered_ner.append(ner)

        merged = sorted(regex_dets + filtered_ner, key=lambda d: d.start)
        return merged

    def filter(self, text: str) -> FilterResult:
        """Filter PII from text."""
        if not text:
            return FilterResult(original_text="", filtered_text="", detections=[], mapping={})

        all_detections: List[PIIDetection] = []

        if self.use_regex:
            all_detections.extend(self._detect_regex(text))
        if self.use_ner:
            all_detections.extend(self._detect_ner(text))

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


def create_filter(config: dict = None) -> PIIFilter:
    """Factory function to create a PIIFilter instance."""
    return PIIFilter(config)
