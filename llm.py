"""Gemini client (plain REST - no SDK needed) + the single structured-analysis prompt.

One API call per bill keeps usage inside the free tier. If the call fails, the
analyzer falls back to an offline extractive summary so the app never crashes.
"""
import json
import re
import time

import requests

from config import DEFAULT_MODELS, GEMINI_BASE, REQUEST_TIMEOUT, SECTOR_NAMES


class LLMError(Exception):
    pass


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODELS[0], fallback_models=None, timeout: int = REQUEST_TIMEOUT):
        if not api_key or not api_key.strip():
            raise LLMError("No Gemini API key provided.")
        self.key = api_key.strip()
        self.model = model
        self.fallbacks = [m for m in (fallback_models or DEFAULT_MODELS) if m != model]
        self.timeout = timeout
        self.last_model_used = None

    # -- helpers ---------------------------------------------------------
    def _headers(self):
        return {"x-goog-api-key": self.key, "Content-Type": "application/json"}

    def list_models(self):
        """Models this key can use for generateContent (call this if a model name stops working)."""
        r = requests.get(f"{GEMINI_BASE}/models?pageSize=200", headers=self._headers(), timeout=self.timeout)
        if r.status_code != 200:
            raise LLMError(self._explain(r))
        names = []
        for m in r.json().get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                names.append(m["name"].split("/")[-1])
        return sorted(names)

    @staticmethod
    def _explain(resp) -> str:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text[:200])
        except Exception:
            msg = resp.text[:200]
        hints = {400: "Bad request or invalid API key.", 403: "API key not allowed for this model/region.",
                 404: "Model name not found - pick another model.", 429: "Rate limit / free-tier quota reached."}
        return f"HTTP {resp.status_code}: {hints.get(resp.status_code, '')} {msg}".strip()

    @staticmethod
    def _parse_json(text: str):
        t = text.strip()
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", t, re.S)
            if m:
                return json.loads(m.group(0))
            raise

    def _call(self, model: str, prompt: str):
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
        url = f"{GEMINI_BASE}/models/{model}:generateContent"
        last = None
        for attempt in range(3):
            r = requests.post(url, headers=self._headers(), json=body, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                try:
                    return self._parse_json(data["candidates"][0]["content"]["parts"][0]["text"])
                except (KeyError, IndexError, json.JSONDecodeError) as exc:
                    raise LLMError(f"Model returned an unreadable answer ({exc}).") from exc
            last = self._explain(r)
            if r.status_code in (429, 500, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            break
        raise LLMError(last or "Unknown error")

    # -- public ----------------------------------------------------------
    def generate_json(self, prompt: str):
        errors = []
        for model in [self.model] + self.fallbacks:
            try:
                out = self._call(model, prompt)
                self.last_model_used = model
                return out
            except LLMError as exc:
                errors.append(f"{model}: {exc}")
                if "unreadable" not in str(exc) and "404" not in str(exc) and "429" not in str(exc):
                    break  # key/permission problem - other models will fail the same way
        # every configured name returned 404 (model retired): ask the API what this key can use and try those
        if errors and all("HTTP 404" in e for e in errors):
            tried = {self.model, *self.fallbacks}
            try:
                names = self.list_models()
            except LLMError as exc:
                errors.append(f"list_models: {exc}")
                names = []
            skip = ("tts", "image", "audio", "live", "embed", "native", "transcribe", "omni", "imagen", "veo")
            usable = [n for n in names if "flash" in n and not any(s in n for s in skip) and n not in tried]
            usable.sort(key=lambda n: ("lite" in n, n))      # full Flash models first, lite ones last
            for model in usable[:3]:
                try:
                    out = self._call(model, prompt)
                    self.last_model_used = model
                    return out
                except LLMError as exc:
                    errors.append(f"{model}: {exc}")
        raise LLMError(" | ".join(errors))


PROMPT = """You are a public-policy analyst explaining Indian Government Bills to ordinary citizens.
Read the bill text and return ONE JSON object only (no markdown), using ONLY facts supported by the text.
If something is not in the text, use an empty list or "Not stated" - never invent clauses, dates or acts.
Write in plain language an 8th-grade student can follow.

Hints from rule-based analysis (verify against the text):
- Likely sectors: {sectors}
- Earlier laws/bills mentioned: {acts}

JSON schema:
{{
 "title": str, "ministry": str, "objective": str (1-3 sentences: why the bill exists),
 "summary_lines": [10-20 short plain-language lines: "What does this bill mean for a normal person?"],
 "key_provisions": [str],
 "related_acts": [{{"name": str, "relation": "amends|repeals|builds on|related", "note": str}}],
 "stakeholders": {{"citizens": [str], "businesses": [str], "government": [str], "industries_markets": [str], "ngos": [str]}},
 "affected_industries": [{{"sector": one of {sector_names}, "effect": "Benefit|Restriction|Mixed", "reason": str}}],
 "impact": {{"short_term": [str] (0-1 year), "medium_term": [str] (1-5 years), "long_term": [str] (>5 years)}},
 "positives": [str], "negatives": [str],
 "new_business_opportunities": [str],
 "risks_and_unintended_consequences": [str],
 "controversial_areas": [str], "possible_public_backlash": [str], "implementation_challenges": [str]
}}

BILL TEXT:
\"\"\"
{text}
\"\"\"
"""


def build_prompt(text: str, sectors, acts) -> str:
    return PROMPT.format(text=text, sectors=", ".join(sectors) or "unknown",
                         acts="; ".join(acts) or "none detected", sector_names=json.dumps(SECTOR_NAMES))
