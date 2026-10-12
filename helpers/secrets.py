"""Local payload-only secret checks. Never validate credentials remotely."""
import re

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


def check(text, known=()):
    if any(value and len(value) >= 4 and value in text for value in known):
        raise SecretError("Local Privacy Guard blocked a model request containing a managed credential. Remove the credential from the content.")
    for label, expression in RULES.items():
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
            raise SecretError(f"Local Privacy Guard blocked a model request containing a {label}. Remove the credential from the content.")
