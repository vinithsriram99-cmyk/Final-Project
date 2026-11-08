"""Pipeline: clean -> classify -> chronology -> risks -> LLM analysis (or offline fallback)."""
import time

import numpy as np

import classifier
import chronology
import risk
from config import HEAD_CHARS, MAX_LLM_CHARS, TAIL_CHARS
from llm import GeminiClient, LLMError, build_prompt
from preprocess import (clean_text, extract_ministry, extract_objects_reasons, extract_title, split_sentences,
                        strip_headings, to_paragraphs, truncate_for_llm)

LIST_KEYS = ["summary_lines", "key_provisions", "related_acts", "affected_industries", "positives", "negatives",
             "new_business_opportunities", "risks_and_unintended_consequences", "controversial_areas",
             "possible_public_backlash", "implementation_challenges"]
STAKEHOLDER_KEYS = ["citizens", "businesses", "government", "industries_markets", "ngos"]
IMPACT_KEYS = ["short_term", "medium_term", "long_term"]
NEEDS_LLM = "Needs the Gemini analysis (offline mode cannot infer this)."


def normalize(d: dict) -> dict:
    """Guarantee every expected key exists with the right type, whatever the LLM returned."""
    d = d if isinstance(d, dict) else {}
    out = {"title": str(d.get("title") or "Not stated"), "ministry": str(d.get("ministry") or "Not stated"),
           "objective": str(d.get("objective") or "Not stated")}
    for k in LIST_KEYS:
        v = d.get(k)
        out[k] = v if isinstance(v, list) else ([] if v in (None, "") else [v])
    st = d.get("stakeholders") if isinstance(d.get("stakeholders"), dict) else {}
    out["stakeholders"] = {k: (st.get(k) if isinstance(st.get(k), list) else []) for k in STAKEHOLDER_KEYS}
    im = d.get("impact") if isinstance(d.get("impact"), dict) else {}
    out["impact"] = {k: (im.get(k) if isinstance(im.get(k), list) else []) for k in IMPACT_KEYS}
    return out


def extractive_analysis(text: str, title: str, ministry: str, objective: str, n_lines: int = 12) -> dict:
    """Offline fallback: pick the most representative sentences (TF-IDF centrality). No invention."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    sents = [s for s in split_sentences(text) if 40 <= len(s) <= 320]
    lines = []
    if len(sents) >= 3:
        X = TfidfVectorizer(stop_words="english").fit_transform(sents)
        centroid = np.asarray(X.mean(axis=0))
        score = np.asarray(X @ centroid.T).ravel()
        idx = sorted(np.argsort(score)[::-1][:n_lines])
        lines = [sents[i] for i in idx]
    provisions = [s for s in sents if any(w in s.lower() for w in (" shall ", "is hereby", "may be called", "prescribed"))][:10]
    d = {"title": title, "ministry": ministry, "objective": objective or (lines[0] if lines else "Not stated"),
         "summary_lines": lines, "key_provisions": provisions}
    d = normalize(d)
    d["impact"] = {k: [NEEDS_LLM] for k in IMPACT_KEYS}
    return d


def _clean_rows(chrono) -> list:
    """DataFrame -> list of dicts with whole-number years (or None) instead of float / NaN."""
    rows = []
    for rec in chrono.to_dict(orient="records"):
        y = rec.get("year")
        rec["year"] = int(y) if y is not None and y == y else None
        rows.append(rec)
    return rows


def analyze(raw_text: str, client: GeminiClient = None, source_name: str = "pasted text") -> dict:
    t0 = time.time()
    text = clean_text(raw_text)
    flat = to_paragraphs(strip_headings(text))
    title = extract_title(text)
    ministry = extract_ministry(text)
    objective = extract_objects_reasons(text)

    sectors = classifier.classify(text, title)
    chrono = chronology.build_chronology(flat, title)
    risks = risk.detect_risks(flat)

    mode, model_used, warning = "offline-extractive", None, None
    result = None
    if client is not None:
        try:
            prompt = build_prompt(truncate_for_llm(text, MAX_LLM_CHARS, HEAD_CHARS, TAIL_CHARS),
                                  [s["sector"] for s in sectors],
                                  [e for e in chrono["event"].tolist() if chrono[chrono.event == e].type.iloc[0] != "Committee review"][:12]
                                  if not chrono.empty else [])
            result = normalize(client.generate_json(prompt))
            mode, model_used = "gemini", client.last_model_used
            # keep rule-based facts when the LLM left them blank
            if result["title"] == "Not stated":
                result["title"] = title
            if result["ministry"] == "Not stated":
                result["ministry"] = ministry
        except LLMError as exc:
            warning = f"Gemini analysis failed, showing offline extractive results instead. {exc}"
    if result is None:
        result = extractive_analysis(flat, title, ministry, objective)
        if client is None:
            warning = "No API key: showing offline extractive results (add a Gemini key for full analysis)."

    result.update({
        "source": source_name,
        "detected_sectors": sectors,
        "sector_scores": classifier.all_scores(text, title),
        "chronology": _clean_rows(chrono),
        "rule_based_risks": risks,
        "meta": {"mode": mode, "model": model_used, "characters": len(text), "words": len(text.split()),
                 "processing_seconds": round(time.time() - t0, 2), "warning": warning},
    })
    return result
