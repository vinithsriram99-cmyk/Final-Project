"""Downloadable PDF summary (reportlab)."""
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_MAP = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "₹": "Rs. ",
        "•": "-", "…": "..."}


def _s(x) -> str:
    t = str(x)
    for k, v in _MAP.items():
        t = t.replace(k, v)
    return escape(t.encode("latin-1", "replace").decode("latin-1"))


def build_pdf(r: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Bill summary")
    ss = getSampleStyleSheet()
    h1, h2, body = ss["Title"], ss["Heading2"], ParagraphStyle("b", parent=ss["BodyText"], leading=14)
    bullet = ParagraphStyle("bl", parent=body, leftIndent=14, bulletIndent=2)
    story = [Paragraph(_s(r["title"]), h1),
             Paragraph(f"<b>Ministry:</b> {_s(r['ministry'])}", body),
             Paragraph(f"<b>Sectors:</b> {_s(', '.join(s['sector'] for s in r['detected_sectors']))}", body),
             Spacer(1, 8), Paragraph("Objective", h2), Paragraph(_s(r["objective"]), body)]

    def bullets(title, items):
        if items:
            story.append(Paragraph(title, h2))
            for it in items:
                story.append(Paragraph(_s(it if isinstance(it, str) else it.get("name") or it), bullet, bulletText="-"))

    bullets("What does this bill mean for a normal person?", r["summary_lines"])
    bullets("Key provisions", r["key_provisions"])
    if r["affected_industries"]:
        story.append(Paragraph("Industry impact", h2))
        rows = [["Sector", "Effect", "Reason"]] + [[_s(i.get("sector", "")), _s(i.get("effect", "")),
                Paragraph(_s(i.get("reason", "")), body)] for i in r["affected_industries"] if isinstance(i, dict)]
        tb = Table(rows, colWidths=[4 * cm, 2.5 * cm, 10 * cm])
        tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(tb)
    for label, key in [("Short term (0-1 year)", "short_term"), ("Medium term (1-5 years)", "medium_term"),
                       ("Long term (>5 years)", "long_term")]:
        bullets(label, r["impact"][key])
    bullets("Positives", r["positives"]); bullets("Negatives", r["negatives"])
    bullets("Risks & unintended consequences", r["risks_and_unintended_consequences"])
    bullets("Controversial areas", r["controversial_areas"])
    if r["rule_based_risks"]:
        story.append(Paragraph("Clause-level risk flags (rule-based)", h2))
        for x in r["rule_based_risks"]:
            story.append(Paragraph(f"<b>{_s(x['category'])}</b> - {x['severity']} ({x['mentions']} mentions)", bullet, bulletText="-"))
    story += [Spacer(1, 12), Paragraph("<i>AI-generated summary for general understanding. It is not legal advice; "
                                       "read the official bill for authoritative text.</i>", body)]
    doc.build(story)
    return buf.getvalue()
