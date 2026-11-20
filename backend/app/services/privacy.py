"""PII redaction and anonymity helpers."""

import re
import secrets

from app.core.config import settings

_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),                    # emails
    re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"),         # Indian mobile numbers
    re.compile(r"\b\d{2,4}[A-Za-z]{2,4}\d{4,10}\b"),                # 0801CS211001
    re.compile(r"\b[A-Za-z]{1,5}\d{5,14}\b"),                       # ENR0001234
]
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def redact_pii(text: str, extra_tokens: list[str] | None = None) -> tuple[str, bool]:
    """Best-effort redaction. Returns (clean_text, was_anything_redacted)."""
    changed = False
    out = text
    for token in extra_tokens or []:
        if token and token.lower() in out.lower():
            out = re.sub(re.escape(token), "[redacted]", out, flags=re.IGNORECASE)
            changed = True
    for pattern in _PATTERNS:
        out, n = pattern.subn("[redacted]", out)
        changed = changed or n > 0
    return out, changed


def new_anon_code() -> str:
    return "ANON-" + "".join(secrets.choice(_ALPHABET) for _ in range(4))


def shared_issue_message(report_count: int) -> str:
    """k-anonymity: the exact count is only shown once enough students reported."""
    if report_count >= settings.K_ANON_MIN:
        return f"{report_count} students have reported this issue"
    return "Your complaint is linked to a shared issue" if report_count > 1 else "Your complaint is being handled as a new issue"


STUDENT_STATUS_LABEL = {
    "pending": "Received", "open": "Received", "assigned": "Assigned to staff",
    "in_progress": "Work in progress", "awaiting_verification": "Fix submitted, being checked",
    "resolved": "Resolved, please give feedback", "closed": "Closed", "reopened": "Reopened",
    "rejected": "Rejected", "merged": "Linked to another issue",
}
