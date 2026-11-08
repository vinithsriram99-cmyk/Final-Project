"""Bill Topic Classifier - rule-based, multi-label, transparent (keyword lexicon with title boost)."""
import re

from config import SECTORS


def _count(text: str, kw: str) -> int:
    return len(re.findall(r"\b" + re.escape(kw), text))


def classify(text: str, title: str = "", top_k: int = 3, min_hits: int = 3):
    """Return [{sector, score, share}] sorted by score. Title words count 5x."""
    body, head = text.lower(), title.lower()
    scores = {}
    for sector, kws in SECTORS.items():
        s = sum(_count(body, k) + 5 * _count(head, k) for k in kws)
        scores[sector] = s
    total = sum(scores.values()) or 1
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out = [{"sector": s, "score": v, "share": round(v / total, 3)} for s, v in ranked if v >= min_hits]
    return out[:top_k] if out else [{"sector": "Governance & Law", "score": 0, "share": 0.0}]


def all_scores(text: str, title: str = ""):
    body, head = text.lower(), title.lower()
    return {s: sum(_count(body, k) + 5 * _count(head, k) for k in kws) for s, kws in SECTORS.items()}
