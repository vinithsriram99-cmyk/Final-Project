"""Step 1 - get raw text from a PDF, an official URL, or pasted text."""
import io
import re

import requests
from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT

HEADERS = {"User-Agent": "Mozilla/5.0 (PPIIA student project)"}


class IngestError(Exception):
    """Raised with a user-friendly message when a document cannot be read."""


def from_pdf_bytes(data: bytes) -> str:
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        text = ""
    if len(text.strip()) < 200:  # fallback extractor
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        except Exception:
            pass
    if len(text.strip()) < 200:
        raise IngestError("No readable text found in this PDF. It may be a scanned image; "
                          "try a text-based PDF, the HTML version, or paste the text.")
    return text


def from_url(url: str) -> str:
    if not re.match(r"^https?://", url.strip()):
        raise IngestError("Please enter a full URL starting with http:// or https://")
    try:
        resp = requests.get(url.strip(), headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise IngestError(f"Could not download the URL ({exc}). Download the PDF and upload it instead.") from exc
    ctype = resp.headers.get("Content-Type", "").lower()
    if "pdf" in ctype or url.lower().split("?")[0].endswith(".pdf") or resp.content[:4] == b"%PDF":
        return from_pdf_bytes(resp.content)
    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    if len(text.strip()) < 200:
        raise IngestError("The page has too little text (it may load content with JavaScript). "
                          "Download the bill PDF and upload it instead.")
    return text


def from_text(text: str) -> str:
    if not text or len(text.strip()) < 200:
        raise IngestError("Please provide at least a few paragraphs of bill text (200+ characters).")
    return text
