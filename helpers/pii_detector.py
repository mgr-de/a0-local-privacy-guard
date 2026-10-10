"""
Local PII Detection and Anonymization Engine.

Detects PII using regex patterns and spaCy NER (Named Entity Recognition).
All processing happens locally - no data leaves the machine for detection.
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

# spaCy models are loaded lazily to avoid startup cost when plugin is disabled
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
    pii_type: str          # e.g., "EMAIL", "PERSON", "IBAN"
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
REGEX_PATTERNS: Dict[str, Tuple[str, str]] = {
    "EMAIL": (
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "<EMAIL>"
    ),
    "TELEFON": (
        r'(?:\+49|0049|0)\s*[\-/]?\s*(?:\(?\d{2,5}\)?[\s\-/]?)?\d{3,}[\s\-/]?\d{2,}',
        "<TELEFON>"
    ),
    "PHONE": (
        r'\+?[1-9]\d{0,2}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,9}',
        "<TELEFON>"
    ),
    "IBAN": (
        r'\b[A-Z]{2}\d{2}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}(?:[\s]?[A-Z0-9]{1,2})?\b',
        "<IBAN>"
    ),
    "IBAN_DE": (
        r'\bDE\d{20}\b',
        "<IBAN>"
    ),
    "SSN": (
        r'\b\d{3}-\d{2}-\d{4}\b',
        "<SSN>"
    ),
    "CREDIT_CARD": (
        r'\b(?:\d{4}[\s-]?){3}\d{4}\b',
        "<KREDITKARTE>"
    ),
    "PLZ": (
        r'\b\d{5}\b(?=\s)',
        "<PLZ>"
    ),
    "IP": (
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        "<IP>"
    ),
    "DATUM": (
        r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b',
        "<DATUM>"
    ),
    "API_KEY": (
        r'\b(?:sk|pk|api|key|secret|token)[-_]?[a-zA-Z0-9]{20,}\b',
        "<API_KEY>"
    ),
    "STEUER_ID": (
        r'\b\d{11}\b',
        "<STEUER_ID>"
    ),
    "REISEPASS": (
        r'\b[A-Z]\d{8}\b',
        "<REISEPASS>"
    ),
}

GERMAN_PATTERNS: Dict[str, Tuple[str, str]] = {
    "ADRESSE": (
        r'\b(?:Straße|str\.|Weg|Platz|Allee|Gasse|Ring|Damm|Ufer)\s+\d+[a-zA-Z]?\b',
        "<ADRESSE>"
    ),
}

ENGLISH_PATTERNS: Dict[str, Tuple[str, str]] = {
    "ADDRESS": (
        r'\b\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Blvd)\b',
        "<ADRESSE>"
    ),
}


class PIIFilter:
    """Main PII filtering engine."""

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
        self.compiled_patterns = []
        if self.use_regex:
            all_patterns = dict(REGEX_PATTERNS)
            if self.ner_language == "de":
                all_patterns.update(GERMAN_PATTERNS)
            else:
                all_patterns.update(ENGLISH_PATTERNS)
            for cp in self.custom_patterns:
                all_patterns[cp.get("name", "CUSTOM")] = (cp.get("regex", ""), cp.get("replacement", "<CUSTOM>"))

            for name, (pattern, replacement) in all_patterns.items():
                try:
                    self.compiled_patterns.append((name, re.compile(pattern, re.IGNORECASE), replacement))
                except re.error:
                    pass

    def _format_placeholder(self, pii_type: str, replacement: str) -> str:
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
                "DATE": "DATUM", "TIME": "ZEIT",
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
        detections.sort(key=lambda d: (d.start, d.end))
        merged = []
        for det in detections:
            if merged and det.start < merged[-1].end:
                if det.confidence > merged[-1].confidence:
                    merged[-1] = det
                continue
            merged.append(det)
        return merged

    def filter(self, text: str) -> FilterResult:
        """Filter PII from text."""
        if not text:
            return FilterResult(original_text="", filtered_text="", detections=[], mapping={})

        all_detections = []

        if self.use_regex:
            all_detections.extend(self._detect_regex(text))

        if self.use_ner:
            all_detections.extend(self._detect_ner(text))

        detections = self._merge_detections(all_detections)

        # Apply replacements (from end to start to preserve positions)
        filtered = text
        mapping = {}
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
