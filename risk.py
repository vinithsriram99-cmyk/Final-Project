"""Risk & Controversy Detector - flags clause patterns that raise cost, rights, or friction concerns."""
import re

from preprocess import split_sentences

RULES = {
    "Penalties & criminal liability": ["imprisonment", "fine which may", "penalt", "offence", "cognizable",
                                       "non-bailable", "punishable", "prosecution"],
    "Wide executive discretion": ["as may be prescribed", "the central government may", "the government may by notification",
                                  "notwithstanding anything", "exempt", "in public interest", "may, by order",
                                  "as it may deem fit"],
    "Privacy & civil-rights concerns": ["surveillance", "search and seizure", "intercept", "personal data", "arrest",
                                        "detention", "without warrant", "monitor", "biometric", "consent"],
    "Compliance cost for businesses": ["licen", "registration", "compliance", "audit", "annual return", "fee",
                                       "cess", "levy", "certificat", "mandatory"],
    "Centre-State friction": ["state government", "concurrent list", "states shall", "union territor", "federal"],
    "Retrospective effect": ["deemed to have come into force", "retrospective", "shall be deemed"],
    "Implementation challenges": ["rules shall be framed", "constituted", "tribunal", "authority shall", "within a period of",
                                  "transition", "notified", "establish"],
}


def detect_risks(text: str, max_examples: int = 2):
    sentences = split_sentences(text)
    out = []
    for category, kws in RULES.items():
        hits = []
        for s in sentences:
            sl = s.lower()
            if any(re.search(r"\b" + re.escape(k), sl) for k in kws):
                hits.append(s)
        n = len(hits)
        if n:
            sev = "High" if n >= 8 else "Medium" if n >= 3 else "Low"
            out.append({"category": category, "mentions": n, "severity": sev,
                        "examples": [h[:260] for h in hits[:max_examples]]})
    return sorted(out, key=lambda r: r["mentions"], reverse=True)
