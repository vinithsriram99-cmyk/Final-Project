"""Shared settings for the Public Policy Insight & Impact Analyzer (PPIIA)."""
import os

# Gemini model names change over time (the 2.5 family is being retired in late 2026).
# 'gemini-flash-latest' is an alias for the current Flash model; if every name fails the client asks the API
# which models your key can use and tries those automatically.
# Original note: The app can list the models your key
# can use; these are only the starting suggestions (tried in this order).
DEFAULT_MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_MODELS[0])

# Free-tier friendly limits: one LLM call per bill, text capped to this size.
MAX_LLM_CHARS = 60000
HEAD_CHARS = 45000
TAIL_CHARS = 10000
REQUEST_TIMEOUT = 90

# Sector keyword lexicon used by the rule-based Bill Topic Classifier.
SECTORS = {
    "Agriculture": ["agricultur", "farmer", "crop", "irrigation", "fertili", "seed", "mandi", "agri", "livestock",
                    "fisher", "horticultur", "minimum support price", "produce market"],
    "Finance & Banking": ["bank", "financ", "insurance", "loan", "credit", "tax", "revenue", "investment",
                          "securities", "monetary", "fiscal", "gst", "reserve bank", "microfinance", "pension"],
    "Education": ["educat", "school", "universit", "student", "teacher", "curricul", "scholarship", "literacy",
                  "college", "examination", "academic"],
    "Healthcare": ["health", "hospital", "patient", "medical", "medicine", "drug", "doctor", "clinical",
                   "disease", "pharma", "nurs", "telemedicine"],
    "Technology & Data": ["digital", "data", "software", "cyber", "internet", "artificial intelligence", "online",
                          "platform", "algorithm", "electronic", "telecom", "technolog", "information technology"],
    "Environment & Energy": ["environment", "pollution", "climate", "forest", "emission", "renewable", "energy",
                             "carbon", "wildlife", "biodiversity", "solar", "waste", "ecolog"],
    "Defence & Security": ["defence", "armed forces", "military", "security", "border", "terror", "army",
                           "navy", "air force", "intelligence", "police"],
    "Labour & Employment": ["labour", "worker", "employ", "wage", "trade union", "industrial dispute", "gig",
                            "pension fund", "provident", "workman", "factory"],
    "Infrastructure & Transport": ["infrastructure", "transport", "highway", "railway", "aviation", "port",
                                   "road", "airport", "shipping", "metro", "construction", "urban"],
    "Governance & Law": ["court", "tribunal", "judicial", "offence", "penalt", "constitution", "election",
                         "parliament", "legislat", "administrat", "commission", "citizen", "right to"],
}

SECTOR_NAMES = list(SECTORS)
