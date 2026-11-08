"""Step 2 - clean bill text and pull out simple structure (title, ministry, objects & reasons)."""
import re

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def clean_text(raw: str) -> str:
    t = raw.replace("\r", "\n").replace(" ", " ")
    t = re.sub(r"-\n(?=[a-z])", "", t)                      # re-join hyphenated line breaks
    t = re.sub(r"(?im)^\s*(page\s+\d+(\s+of\s+\d+)?|\d+)\s*$", "", t)  # page numbers
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def to_paragraphs(text: str) -> str:
    """Single newlines inside a paragraph become spaces (PDF line wraps)."""
    return re.sub(r"(?<!\n)\n(?!\n)", " ", text)


def split_sentences(text: str):
    flat = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z(\d])", flat)
    return [p.strip() for p in parts if len(p.strip()) > 25]


def extract_title(text: str) -> str:
    for line in text.splitlines()[:80]:
        line = line.strip()
        if 8 < len(line) < 160 and re.search(r"\bbill,?\s*(19|20)\d\d\W*$", line, re.I):
            return line.title() if line.isupper() else line
    m = re.search(r"(?:The\s+)?[A-Z][A-Za-z0-9 ,&()'\-]{4,120}?\bBill,?\s*(?:19|20)\d\d", text)
    if m:
        s = re.sub(r"\s+", " ", m.group(0))
        return s.title() if s.isupper() else s
    return "Untitled bill"


def extract_ministry(text: str) -> str:
    m = re.search(r"(Ministry of [A-Z][A-Za-z&\- ]{3,60}?)(?=\)|\.|\n|,|\s+and\s+the|\s+\(|$)", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"Minister of ([A-Z][A-Za-z&\- ]{3,50}?)(?=\)|\.|\n|,|\s+and\s+the|\s+\(|$)", text)
    return f"Ministry of {m.group(1).strip()}" if m else "Not stated"


def strip_headings(text: str) -> str:
    """Drop short ALL-CAPS heading lines (titles, 'STATEMENT OF OBJECTS...') before sentence extraction."""
    keep = [ln for ln in text.splitlines() if not (0 < len(ln.strip()) <= 120 and ln.strip().isupper())]
    return "\n".join(keep)


def extract_objects_reasons(text: str) -> str:
    """Text after 'Statement of Objects and Reasons' up to the first numbered clause / next heading (needs newlines)."""
    m = re.search(r"statement of objects and reasons\s*(.+?)(?=\n\s*(?:a\s+)?bill\s+to\b|\n\s*\d+\.\s|\n\s*(?:chapter|clause)\s+[ivx\d]|\Z)",
                  text, re.I | re.S)
    if m:
        body = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(body) > 60:
            return body[:2500]
    return ""


def truncate_for_llm(text: str, max_chars: int, head: int, tail: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:head] + "\n\n[... middle of the document omitted for length ...]\n\n" + text[-tail:]
