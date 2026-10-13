"""Local payload-only secret checks. Never validate credentials remotely."""
import re
import json
from usr.plugins.local_privacy_guard.helpers.code_regions import assignment_references

# Recognizable credential formats and context-bound generic credentials.
# Deliberately do not treat every random identifier as a secret.
RULES = {
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "API token": r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{20,})\b",
    "credential assignment": r"(?i)(?:password|passwd|passwort|api[_ -]?key|access[_ -]?token|client[_ -]?secret|authorization)[\"']?\s*[=:]\s*[\"']?(?:Bearer\s+)?([^\s\"'<>;,]{4,})",
    "credential URL": r"(?i)\b(?:https?|postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s/:]+:[^\s/@]+@",
}


class SecretError(ValueError):
    pass


def check(text, known=(), _depth=0):
    if any(value and len(value) >= 4 and value in text for value in known):
        raise SecretError("Local Privacy Guard blocked a model request containing a managed credential. Remove the credential from the content.")
    # Recognizable secrets are never exempted by source syntax or JSON tags.
    for label, expression in RULES.items():
        if label == 'credential assignment':
            continue
        if re.search(expression, text):
            raise SecretError(f"Local Privacy Guard blocked a model request containing a {label}. Remove the credential from the content.")
    if _depth > 32:
        raise SecretError('Local secret inspection exceeded its structured depth limit.')
    candidate = text.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', candidate, re.DOTALL)
    if fenced:
        candidate = fenced[1]
    try:
        structured = json.loads(candidate) if candidate.startswith(('{', '[')) else None
    except (ValueError, RecursionError):
        structured = None
    if isinstance(structured, (dict, list)):
        def inspect(value, depth):
            if depth > 32:
                raise SecretError('Local secret inspection exceeded its structured depth limit.')
            if isinstance(value, str):
                check(value, known, depth)
            elif isinstance(value, list):
                for part in value:
                    inspect(part, depth + 1)
            elif isinstance(value, dict):
                for key, part in value.items():
                    check(key, known, depth + 1)
                    if isinstance(part, str) and re.fullmatch(r'(?i)(?:password|passwd|passwort|api[_ -]?key|access[_ -]?token|client[_ -]?secret|authorization)', key):
                        check(key + '=' + json.dumps(part), known, depth + 1)
                    inspect(part, depth + 1)
        inspect(structured, _depth + 1)
        return
    references = None
    for label, expression in {'credential assignment': RULES['credential assignment']}.items():
        for match in re.finditer(expression, text):
            if label == "credential assignment" and match.group(1).lower() in {
                "example", "placeholder", "redacted", "undefined", "synthetic", "changeme", "********",
                "none", "null", "true", "false",
            }:
                continue
            if label=='credential assignment' and re.fullmatch(r'§§secret\([A-Za-z0-9_.-]+\)',match.group(1)):
                continue  # Native local secret reference, not its value.
            if label=='credential assignment' and re.fullmatch(r'\$(?:[A-Z_][A-Z0-9_]*|\{[A-Z_][A-Z0-9_]*\})',match.group(1)):
                continue  # Conventional environment reference, not its value.
            if references is None:
                references = assignment_references(text)
            if any(start == match.start(1) and match.end(1) <= end for start, end in references):
                continue  # Parsed source reference, not a literal credential.
            raise SecretError(f"Local Privacy Guard blocked a model request containing a {label}. Remove the credential from the content.")
