# pipeline/cleaner.py
import re


# ── Patterns that repeat at the bottom of every case ──────────────────────────
# These are boilerplate lines that appear on every single decision and carry
# no legal meaning — we strip them before chunking.
FOOTER_PATTERNS = [
    r"H\s+ΑΝΤΙΠΡΟΕΔΡΟΣ\s+Η\s+ΓΡΑΜΜΑΤΕΑΣ",       # "H ΑΝΤΙΠΡΟΕΔΡΟΣ Η ΓΡΑΜΜΑΤΕΑΣ"
    r"Ο\s+ΠΡΟΕΔΡΟΣ\s+Η\s+ΓΡΑΜΜΑΤΕΑΣ",             # "Ο ΠΡΟΕΔΡΟΣ Η ΓΡΑΜΜΑΤΕΑΣ"
    r"ΔΗΜΟΣΙΕΥΘΗΚΕ\s+σε\s+δημόσια\s+συνεδρίαση[^.]*\.",  # publication line
    r"Κρίθηκε\s+και\s+αποφασίσθηκε[^.]*\.",        # decision line
    r"ΚΡΙΘΗΚΕ,?\s+αποφασίσθηκε[^.]*\.",            # alternate decision line
]


def clean(text: str) -> str:
    """
    Clean a single case text and return the cleaned version.
    Runs four steps in order: strip footer, normalize whitespace,
    clean line by line, final strip.
    """
    if not text:
        return ""

    text = _strip_footer(text)
    text = _normalize_whitespace(text)
    text = _clean_lines(text)
    text = text.strip()

    return text


# ── Step 1 ─────────────────────────────────────────────────────────────────────

def _strip_footer(text: str) -> str:
    """
    Remove boilerplate lines that appear at the bottom of every case.

    Every Greek court decision ends with the same closing lines:
      - "ΚΡΙΘΗΚΕ, αποφασίσθηκε στην Αθήνα, στις 8 Ιανουαρίου 2020."
      - "ΔΗΜΟΣΙΕΥΘΗΚΕ σε δημόσια συνεδρίαση στο ακροατήριό του..."
      - "H ΑΝΤΙΠΡΟΕΔΡΟΣ Η ΓΡΑΜΜΑΤΕΑΣ"

    These carry no legal content — they're just formalities. We remove them
    so they don't end up in chunks and pollute embeddings with meaningless text.

    We use re.sub() with each pattern. The flags mean:
      - re.IGNORECASE: matches regardless of upper/lowercase
      - re.MULTILINE: ^ and $ match start/end of each line, not just the whole string
    """
    for pattern in FOOTER_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
    return text


# ── Step 2 ─────────────────────────────────────────────────────────────────────

def _normalize_whitespace(text: str) -> str:
    """
    Collapse excessive blank lines into a single blank line.

    When text is extracted from HTML via BeautifulSoup, you often end up with
    3, 4, or 5 consecutive empty lines between paragraphs. This is visual noise
    that doesn't add meaning. We reduce any run of 2+ newlines down to exactly
    2 (one blank line between paragraphs), which is clean and readable.

    The regex \\n{3,} means "3 or more newline characters in a row".
    We replace them with just \\n\\n (two newlines = one blank line).
    """
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ── Step 3 ─────────────────────────────────────────────────────────────────────

def _clean_lines(text: str) -> str:
    """
    Process the text line by line and clean each one individually.

    For each line we do two things:
      1. Strip leading and trailing whitespace (.strip())
         e.g. "   some text   " → "some text"

      2. Collapse multiple spaces within the line into one
         e.g. "some    text" → "some text"
         The regex \\s+ means "one or more whitespace characters".
         We replace with a single space.

    We then filter out lines that are completely empty after cleaning,
    and rejoin everything back into a single string with newlines.

    This handles the messy output from BeautifulSoup where lines often
    have inconsistent indentation and spacing from the original HTML.
    """
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        line = re.sub(r"\s+", " ", line)
        cleaned.append(line)

    # Rejoin — we keep empty lines because they mark paragraph boundaries,
    # which are important for the chunker to work with later
    return "\n".join(cleaned)
