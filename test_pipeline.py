"""Sanity tests (no internet or API key needed - Gemini is mocked).   Run: python3 test_pipeline.py"""
import csv
import io
import json
from pathlib import Path
from unittest.mock import patch

import analyzer
import classifier
from chronology import build_chronology
from ingest import IngestError, from_pdf_bytes, from_text
from llm import GeminiClient, LLMError
from preprocess import clean_text, extract_ministry, extract_title
from report_pdf import build_pdf
from risk import detect_risks

SAMPLES = Path(__file__).parent / "sample_bills"
FAKE_ANSWER = {
    "title": "Digital Health Bill", "ministry": "Ministry of Health", "objective": "Protect patient data.",
    "summary_lines": [f"Line {i}" for i in range(12)], "key_provisions": ["Hospitals must register"],
    "related_acts": [{"name": "IT Act, 2000", "relation": "builds on", "note": "data"}],
    "stakeholders": {"citizens": ["Patients"], "businesses": ["Hospitals"]},
    "affected_industries": [{"sector": "Healthcare", "effect": "Restriction", "reason": "More compliance"}],
    "impact": {"short_term": ["Registration drive"], "medium_term": ["Audits"], "long_term": ["Trust"]},
    "positives": ["Privacy"], "negatives": ["Cost"],
}


class FakeResp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._p, self.text = status, payload or {}, json.dumps(payload or {})

    def json(self):
        return self._p


def gemini_ok(text):
    return FakeResp(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


def sample(name):
    return (SAMPLES / name).read_text()


def test_clean_and_title():
    assert clean_text("fi-\nnal  text\n\n\n\nPage 3\nok") == "final text\n\nok"
    t = sample("digital_health_records.txt")
    assert extract_title(t) == "The Digital Health Records (Protection) Bill, 2026"
    assert extract_ministry(t) == "Ministry of Health and Family Welfare"


def test_classifier_accuracy_on_samples():
    rows = list(csv.DictReader(open(SAMPLES / "labels.csv")))
    hits = 0
    for row in rows:
        text = sample(row["file"])
        top = classifier.classify(text, extract_title(text))[0]["sector"]
        hits += top == row["true_sector"]
        assert top == row["true_sector"], (row["file"], top)
    print(f"  classifier accuracy on samples: {hits}/{len(rows)}")


def test_chronology_and_risks():
    t = analyzer.to_paragraphs(analyzer.strip_headings(clean_text(sample("digital_health_records.txt"))))
    ch = build_chronology(t, "The Digital Health Records (Protection) Bill, 2026")
    names = ch["event"].tolist()
    assert "Information Technology Act, 2000" in names
    assert "Clinical Establishments (Registration and Regulation) Act, 2010" in names
    assert ch[ch.type == "Committee review"].year.iloc[0] == 2024
    assert not any("Digital Health Records" in n for n in names)   # the bill itself is excluded
    cats = {r["category"] for r in detect_risks(t)}
    assert {"Penalties & criminal liability", "Privacy & civil-rights concerns"} <= cats


def test_ingest_errors_and_pdf_roundtrip():
    for bad in ("", "short"):
        try:
            from_text(bad); assert False
        except IngestError:
            pass
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); y = 800
    for line in sample("farm_produce_marketing.txt").splitlines():
        c.drawString(40, y, line[:110]); y -= 12
        if y < 40:
            c.showPage(); y = 800
    c.save()
    text = from_pdf_bytes(buf.getvalue())
    assert "AGRICULTURAL PRODUCE MARKETING" in text.upper()


def test_offline_analysis_schema():
    r = analyzer.analyze(sample("green_energy_transition.txt"))
    assert r["meta"]["mode"] == "offline-extractive" and r["meta"]["warning"]
    assert r["detected_sectors"][0]["sector"] == "Environment & Energy"
    assert 5 <= len(r["summary_lines"]) <= 20
    assert "Short title" not in r["objective"] and len(r["objective"]) > 80
    assert not any(l.isupper() for l in r["summary_lines"])
    for k in ("stakeholders", "impact", "chronology", "rule_based_risks", "sector_scores"):
        assert k in r
    assert build_pdf(r)[:4] == b"%PDF"


def test_gemini_success_with_markdown_fence():
    with patch("llm.requests.post", return_value=gemini_ok("```json\n" + json.dumps(FAKE_ANSWER) + "\n```")) as post:
        r = analyzer.analyze(sample("digital_health_records.txt"), GeminiClient("key", "m1"))
    assert post.call_count == 1
    assert r["meta"]["mode"] == "gemini" and r["meta"]["model"] == "m1"
    assert r["impact"]["long_term"] == ["Trust"] and r["negatives"] == ["Cost"]
    assert r["stakeholders"]["ngos"] == []             # missing keys are filled in
    assert build_pdf(r)[:4] == b"%PDF"


def test_gemini_retry_then_model_fallback_then_offline():
    seq = [FakeResp(404, {"error": {"message": "model not found"}}), gemini_ok(json.dumps(FAKE_ANSWER))]
    with patch("llm.requests.post", side_effect=seq):
        c = GeminiClient("key", "bad-model", ["good-model"])
        out = c.generate_json("x")
    assert c.last_model_used == "good-model" and out["title"] == "Digital Health Bill"
    # invalid key -> clear error -> analyzer falls back to offline instead of crashing
    with patch("llm.requests.post", return_value=FakeResp(400, {"error": {"message": "API key not valid"}})):
        r = analyzer.analyze(sample("digital_health_records.txt"), GeminiClient("badkey", "m"))
    assert r["meta"]["mode"] == "offline-extractive" and "API key" in r["meta"]["warning"]
    # rate limit retries (sleep patched out) then succeeds
    with patch("llm.time.sleep"), patch("llm.requests.post", side_effect=[FakeResp(429, {}), gemini_ok("{}")]):
        assert GeminiClient("k", "m")._call("m", "p") == {}
    try:
        GeminiClient("")
        assert False
    except LLMError:
        pass


def test_prompt_is_grounded_and_truncated():
    from llm import build_prompt
    from preprocess import truncate_for_llm
    p = build_prompt("BILLTEXT", ["Healthcare"], ["IT Act, 2000"])
    assert "BILLTEXT" in p and "IT Act, 2000" in p and "never invent" in p
    long = "a" * 100000
    cut = truncate_for_llm(long, 60000, 45000, 10000)
    assert len(cut) < 60000 and "omitted" in cut


def test_dependency_graph_and_nan_years():
    from viz import dependency_dot, timeline_figure
    txt = sample("green_energy_transition.txt") + (
        "\n\nThe Standing Committee on Energy examined the proposal before this Bill was introduced.\n"
        "The Electricity Act, 2003 is amended by this Act.")
    r = analyzer.analyze(txt)
    years = [c["year"] for c in r["chronology"]]
    assert 2003 in years and None in years and not any(isinstance(y, float) for y in years)   # whole years, no NaN
    dot = dependency_dot(r["chronology"], r["title"])
    assert dot.startswith("digraph") and "Electricity Act, 2003" in dot and "reviewed" in dot and dot.rstrip().endswith("}")
    assert timeline_figure(r["chronology"], r["title"]) is not None
    assert dependency_dot([], "Empty Bill, 2026").count("->") == 0


def test_model_discovery_when_all_configured_models_are_retired():
    answer = gemini_ok(json.dumps(FAKE_ANSWER))
    gone = FakeResp(404, {"error": {"message": "model is no longer available"}})
    models = FakeResp(200, {"models": [
        {"name": "models/gemini-9-flash-tts", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-9-flash-lite", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-9-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/embedding-9", "supportedGenerationMethods": ["embedContent"]}]})
    c = GeminiClient("key", "old-a", ["old-b"])
    with patch("llm.requests.get", return_value=models), patch("llm.requests.post", side_effect=[gone, gone, answer]):
        out = c.generate_json("x")
    assert c.last_model_used == "gemini-9-flash" and out["title"] == "Digital Health Bill"   # tts / lite / embedding skipped or ranked last
    with patch("llm.requests.get", return_value=FakeResp(403, {"error": {"message": "denied"}})), \
            patch("llm.requests.post", return_value=gone):
        try:
            GeminiClient("key", "old-a", ["old-b"]).generate_json("x")
            assert False
        except LLMError as exc:
            assert "list_models" in str(exc)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
    print("All tests passed")
