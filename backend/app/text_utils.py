"""Shared deterministic text utilities for untrusted input fencing, normalisation, and quote verification.

Non-negotiable rules:
- R1/R4: Deterministic Python only.
- R6/R8: Strict verification, no fuzzy or approximate semantic matching.
"""

from __future__ import annotations

import re

# Comprehensive dash variants:
# U+2010 (hyphen), U+2011 (non-breaking hyphen), U+2012 (figure dash),
# U+2013 (en dash), U+2014 (em dash), U+2015 (horizontal bar), U+2212 (minus sign)
_DASH_VARIANTS = ("‑", "‒", "–", "—", "―", "−", "‐")

# Quotes and apostrophes
_SMART_SINGLE_QUOTES = ("‘", "’", "‚", "‛", "′", "‵", "´", "`")
_SMART_DOUBLE_QUOTES = ("“", "”", "„", "‟", "″", "‶")

# Ellipsis
_ELLIPSIS_CHAR = "…"


def normalize_text_for_comparison(text: str) -> str:
    """Normalize dash variants, smart quotes, ellipsis, whitespace, and case for verbatim comparison.

    Never performs fuzzy matching or word stemming; only normalizes unicode formatting variants.
    """
    if not text:
        return ""

    s = text

    # Dash variants -> ascii hyphen
    for d in _DASH_VARIANTS:
        s = s.replace(d, "-")

    # Ellipsis character -> three dots
    s = s.replace(_ELLIPSIS_CHAR, "...")

    # Smart single quotes and backticks -> ascii single quote
    for q in _SMART_SINGLE_QUOTES:
        s = s.replace(q, "'")

    # Smart double quotes -> ascii double quote
    for q in _SMART_DOUBLE_QUOTES:
        s = s.replace(q, '"')

    # Normalize double quotes to single quote for uniform comparison
    s = s.replace('"', "'")

    # Non-breaking space and other unicode spaces -> standard space
    s = s.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2009", " ").replace("\u200b", "")

    # Collapse all whitespace sequences into a single space
    s = re.sub(r"\s+", " ", s)

    return s.strip().lower()


def verify_quote(quote: str, corpus: str) -> bool:
    """Verify that a quote exists verbatim (modulo formatting normalization) in the source corpus.

    Returns False if quote is empty or absent. Never uses fuzzy matching.
    Tolerates trailing punctuation added by models when quoting a clause from a running sentence.
    """
    if not quote or not corpus:
        return False
    norm_quote = normalize_text_for_comparison(quote)
    if not norm_quote:
        return False
    norm_corpus = normalize_text_for_comparison(corpus)
    if norm_quote in norm_corpus:
        return True
    trimmed_quote = norm_quote.rstrip(".,;:!?\"' ")
    if trimmed_quote and len(trimmed_quote) >= 3 and trimmed_quote in norm_corpus:
        return True
    return False


def neutralize_delimiter(text: str, delimiter: str, replacement: str | None = None) -> str:
    """Neutralize occurrences of closing delimiters in untrusted text to prevent prompt injection."""
    if not text or not delimiter:
        return text or ""
    if replacement is None:
        replacement = delimiter.replace("<", "&lt;").replace(">", "&gt;")
    return text.replace(delimiter, replacement)


def compute_ticket_hash(*, subject: str | None, body: str, channel: str) -> str:
    """Compute deterministic SHA-256 hash of normalized subject, body, and channel."""
    import hashlib

    norm_sub = re.sub(r"\s+", " ", (subject or "").strip().lower())
    norm_body = re.sub(r"\s+", " ", (body or "").strip().lower())
    norm_chan = (channel or "").strip().lower()
    raw = f"{norm_sub}\n{norm_body}\n{norm_chan}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
