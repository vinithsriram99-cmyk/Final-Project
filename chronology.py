"""Chronology Builder - finds earlier Acts/Bills, amendments, repeals, committee reviews and dates."""
import re

import pandas as pd

from preprocess import MONTHS, split_sentences

_W = r"[A-Z][A-Za-z&]*"
_PHRASE = rf"{_W}(?:\s+(?:and|of|for)\s+{_W}|\s+{_W})*"
CODE_ON_RE = re.compile(rf"\b(Code on {_PHRASE}),\s*((?:19|20)\d{{2}})")
ANCHOR_RE = re.compile(r"\b(Act|Code|Ordinance|Bill),?\s+((?:1[89]|20)\d{2})")
CONNECTORS = {"and", "of", "for", "on", "the", "in", "to", "&"}
COMMITTEE_RE = re.compile(
    rf"((?:Departmental(?:ly[- ]Related)?\s+)?Standing Committee on {_PHRASE}"
    rf"|(?:Joint|Select|Expert)\s+Committee(?:\s+on\s+{_PHRASE})?"
    rf"|Law Commission(?:\s+of India)?)")
DATE_RE = re.compile(rf"\b(\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s*,?\s*((?:19|20)\d\d))", re.I)
LEAD = {"The", "Under", "Since", "Section", "Sections", "By", "In", "Of", "Whereas", "With", "From", "And", "Also"}


def _relation(sentence: str) -> str:
    s = sentence.lower()
    if "repeal" in s:
        return "Repeal"
    if "replace" in s or "supersede" in s:
        return "Replaces"
    if "amend" in s:
        return "Amendment"
    if "ordinance" in s:
        return "Ordinance"
    return "Related law"


def _clean_name(name: str) -> str:
    words = re.sub(r"\s+", " ", name).strip().split(" ")
    while words and words[0] in LEAD:
        words.pop(0)
    return " ".join(words).rstrip(",")


def _norm(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", "", name.lower())
    n = re.sub(r"\b(the|bill|act)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def _law_name(sent: str, m) -> str:
    """Walk backwards from 'Act, 2010' over capitalised words / connectors to recover the full name."""
    toks = sent[:m.start()].split()
    kept = []
    for tok in reversed(toks):
        bare = tok.strip("()[],;:\"'")
        if not bare:
            break
        if bare[0].isupper() or bare.lower() in CONNECTORS:
            kept.append(tok.strip(",;:\"'"))
            if len(kept) >= 12:
                break
        else:
            break
    kept.reverse()
    while kept and (kept[0].strip("()") in LEAD or kept[0].lower() in CONNECTORS):
        kept.pop(0)
    if not kept:
        return ""
    return f"{' '.join(kept)} {m.group(1)}, {m.group(2)}"


def build_chronology(text: str, title: str = "") -> pd.DataFrame:
    rows, seen = [], set()
    own = _norm(title)
    for sent in split_sentences(text):
        for m in ANCHOR_RE.finditer(sent):
            name = _law_name(sent, m)
            if not name:
                continue
            key = _norm(name)
            if key in seen or key == own:
                continue
            seen.add(key)
            rows.append({"year": int(m.group(2)), "event": name, "type": _relation(sent), "context": sent[:220]})
        for m in CODE_ON_RE.finditer(sent):
            name = f"{m.group(1)}, {m.group(2)}"
            key = _norm(name)
            if key not in seen:
                seen.add(key)
                rows.append({"year": int(m.group(2)), "event": name, "type": _relation(sent), "context": sent[:220]})
        for m in COMMITTEE_RE.finditer(sent):
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            key = "c:" + name.lower()
            if key in seen:
                continue
            seen.add(key)
            ys = [(abs(y.start() - m.end()), int(y.group(1))) for y in re.finditer(r"\b((?:19|20)\d\d)\b", sent)]
            ys = [y for _, y in sorted(ys)]
            rows.append({"year": int(ys[0]) if ys else None, "event": name, "type": "Committee review",
                         "context": sent[:220]})
        for m in DATE_RE.finditer(sent):
            key = "d:" + m.group(1).lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({"year": int(m.group(2)), "event": m.group(1), "type": "Dated event", "context": sent[:220]})
    df = pd.DataFrame(rows, columns=["year", "event", "type", "context"])
    if not df.empty:
        df = df.sort_values("year", na_position="last").reset_index(drop=True)
    return df
