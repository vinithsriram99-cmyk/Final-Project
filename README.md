# Public Policy Insight & Impact Analyzer (PPIIA)
*Simplifying Government Bills for Every Citizen*

Upload a Bill (PDF), paste a URL, or paste text. PPIIA returns a plain-language summary, a structured JSON, sector/industry
impact, a chronology of earlier laws, short/medium/long-term impact, and clause-level risk flags - in a Streamlit dashboard
with JSON and PDF downloads. LLM: **Google Gemini (free API key)**.

## How it works
| Step | File | What it does |
| --- | --- | --- |
| Ingest | `ingest.py` | PDF (pypdf, pdfplumber fallback), URL (PDF or HTML), pasted text; friendly errors for scanned PDFs |
| Preprocess | `preprocess.py` | Clean text, title / ministry / Statement of Objects extraction, truncation for the LLM |
| Bill Topic Classifier | `classifier.py` | Transparent multi-label keyword classifier over 10 sectors (title words weigh 5x) |
| Chronology Builder | `chronology.py` | Finds earlier Acts/Codes/Ordinances, amendments, repeals, committee reviews, dated events |
| Dependency graph | `viz.py` (`dependency_dot`) | Draws the bill, the earlier laws it amends/repeals/relates to, and committees as a connected graph (Graphviz DOT) |
| Risk & Controversy Detector | `risk.py` | Flags penalties, executive discretion, privacy/rights, compliance cost, centre-state, retrospective clauses |
| Impact Analyzer + Summariser | `llm.py`, `analyzer.py` | **One** Gemini call returns the JSON (summary, stakeholders, industries, impact horizons, risks); output is validated and missing fields are filled |
| Offline fallback | `analyzer.py` | If there is no key or Gemini fails: extractive summary (TF-IDF) + all rule-based parts - the app never crashes |
| Dashboard | `app.py`, `viz.py`, `report_pdf.py` | Tabs: Summary, JSON, Industry impact, Timeline, Dependency graph, Impact forecast, Risks, Download |

The LLM is told to use only facts in the text and to answer "Not stated" otherwise; rule-based hints (sectors, earlier acts) are
passed to it as grounding. Long bills are trimmed to the first 45k + last 10k characters (free-tier friendly).

## Run locally
```bash
python3 -m pip install -r requirements.txt
python3 test_pipeline.py                         # no key needed; Gemini is mocked
export GEMINI_API_KEY="your-key"                 # get one free at https://aistudio.google.com/apikey  (or paste it in the sidebar)
python3 -m streamlit run app.py
```
Try the **Sample bill** option first (fictional bills in `sample_bills/`), then a real bill PDF from sansad.in.
**Never commit your API key.** `.env` and `.streamlit/secrets.toml` are in `.gitignore`.

**Gemini model names (important).** Google is retiring the Gemini 2.5 family in late 2026, so old model names can return
`404 ... no longer available`. The app now tries `gemini-flash-latest` first and, if every configured name fails, asks the API which
models your key can use and tries those automatically. Gemini model names change. If a model returns "not found" or "quota", click **List models my key can use** in the sidebar
and pick another (the client also automatically tries the next model in `config.DEFAULT_MODELS`).

## Deploy on Hugging Face Spaces (free)
1. huggingface.co -> New Space -> SDK **Streamlit** -> Public.
2. Upload all files from this repo (keep `sample_bills/`).
3. Add this block at the very top of the **Space's** `README.md` (not needed on GitHub):
   ```
   ---
   title: PPIIA
   emoji: 🏛️
   sdk: streamlit
   app_file: app.py
   ---
   ```
4. Space -> Settings -> Variables and secrets -> New secret `GEMINI_API_KEY` = your key.
5. Wait for the build, open the link, run a sample bill. Put that link in your submission.

## Evaluation metrics (project brief)
| Metric | How to measure here |
| --- | --- |
| Bill topic classification accuracy | `test_pipeline.py` scores the classifier on `sample_bills/labels.csv` (6/6). **These samples were written by the project author, so this is a smoke test, not a real accuracy.** Add 15-20 real bills with your own labels to `labels.csv` for a genuine figure. |
| Chronology correctness | Compare the Timeline tab with the bill's own Statement of Objects for 3-5 real bills |
| Relevance of industry impact / summary quality | Read Gemini's output against the bill text; ask 3-5 classmates to rate readability 1-5 |
| Processing time | Shown on the dashboard (offline analysis < 1 s; Gemini adds the API latency) |

## Langflow workflow design
Equivalent flow (build visually in Langflow for the "workflow design" skill): **File/URL loader -> Text splitter/cleaner ->
Prompt (`llm.PROMPT`) -> Google Generative AI (Gemini) -> Structured/JSON parser -> Output**, with the classifier, chronology and risk
steps as Python custom components. The production app uses the same steps directly in code.

## Limitations (be upfront in your viva)
- Summaries and impact forecasts are AI inferences, not legal advice or facts; always verify against the bill.
- The classifier and risk detector are keyword rules; they can miss unusual wording and cannot understand negation.
- Chronology uses patterns like "... Act, 1986"; it will miss acts cited without a year and may list unrelated years.
- Scanned (image) PDFs have no text; sansad.in pages that load with JavaScript may need the PDF downloaded instead.
- Gemini free-tier quotas and model availability change; offline mode is the safety net.


## Test it yourself
```bash
python3 test_pipeline.py        # 10 tests, no internet or API key needed
```
Manual check: run the app, choose **Sample bill**, click **Analyze bill** (offline mode works without a key), then open each tab.
With a Gemini key, tick off **Offline mode** and analyze again; the sidebar shows which model answered.

## Status against the project brief
| Brief item | Where |
| --- | --- |
| Ingest PDF / HTML / URL | `ingest.py` |
| NLP preprocessing | `preprocess.py` |
| Topic classifier, chronology, impact, risks | `classifier.py`, `chronology.py`, `llm.py`, `risk.py` |
| Chronology and dependency graph | Timeline and Dependency graph tabs |
| 10-20 line summary, impact horizons, positives/negatives | Gemini output (`analyzer.py`) |
| Streamlit dashboard, PDF download | `app.py`, `report_pdf.py` |
| Langflow workflow design | `LANGFLOW_DESIGN.md` (design only; no exported flow) |
| Deployed demo link | Hugging Face Spaces (see above); add the link here |
| Video walkthrough | `DEMO_SCRIPT.md` has a 4-minute script |
