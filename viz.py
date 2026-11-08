"""Charts used by the dashboard (matplotlib -> figure objects)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TYPE_COLORS = {"Amendment": "#e67e22", "Repeal": "#c0392b", "Replaces": "#8e44ad", "Ordinance": "#16a085",
               "Related law": "#2980b9", "Committee review": "#27ae60", "Dated event": "#7f8c8d", "This bill": "#000000"}


def _valid_year(y) -> bool:
    try:
        return y is not None and y == y and 1800 < int(y) < 2200   # y == y is False for NaN
    except (TypeError, ValueError):
        return False


def dependency_dot(rows, bill_title: str = "This Bill") -> str:
    """Graphviz DOT source: the bill in the centre, linked to earlier acts, amendments and committees."""
    def esc(s):
        return str(s).replace('"', "'")[:90]
    lines = ["digraph G {", "rankdir=LR;", 'node [fontname="Helvetica", fontsize=10, style=filled];',
             f'bill [label="{esc(bill_title)}", shape=box, fillcolor="#ffe699", penwidth=2];']
    for i, r in enumerate(rows):
        year = int(r["year"]) if _valid_year(r.get("year")) else None
        label = esc(r["event"]) + (f" ({year})" if year and str(year) not in str(r["event"]) else "")
        color = TYPE_COLORS.get(r["type"], "#555555")
        shape = "ellipse" if r["type"] == "Committee review" else "box"
        lines.append(f'n{i} [label="{label}", shape={shape}, fillcolor="white", color="{color}"];')
        if r["type"] == "Committee review":
            lines.append(f'n{i} -> bill [label="reviewed", color="{color}"];')
        else:
            lines.append(f'bill -> n{i} [label="{esc(r["type"])}", color="{color}", fontcolor="{color}"];')
    lines.append("}")
    return "\n".join(lines)


def timeline_figure(rows, bill_title: str = ""):
    """Horizontal timeline of dated items (undated ones are listed by the caller)."""
    dated = [dict(r, year=int(r["year"])) for r in rows if _valid_year(r.get("year"))]
    if not dated:
        return None
    import re
    m = re.search(r"((?:19|20)\d\d)\s*$", bill_title or "")
    if m:
        dated = dated + [{"year": int(m.group(1)), "event": "This Bill", "type": "This bill"}]
    dated.sort(key=lambda r: r["year"])
    fig, ax = plt.subplots(figsize=(9, max(2.5, 0.45 * len(dated) + 1)))
    for i, r in enumerate(dated):
        ax.scatter(r["year"], i, color=TYPE_COLORS.get(r["type"], "#555"), s=70, zorder=3)
        ax.text(r["year"] + 0.3, i, f"{r['event'][:55]}  ({r['type']})", va="center", fontsize=8)
    ax.set_yticks([]); ax.invert_yaxis()
    lo, hi = min(r["year"] for r in dated), max(r["year"] for r in dated)
    ax.set_xlim(lo - 2, hi + 28)
    ax.set_xlabel("Year"); ax.grid(axis="x", alpha=0.3)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig


def sector_scores_figure(scores: dict):
    items = sorted(((k, v) for k, v in scores.items() if v > 0), key=lambda kv: kv[1])
    if not items:
        return None
    fig, ax = plt.subplots(figsize=(6, 0.4 * len(items) + 1))
    ax.barh([k for k, _ in items], [v for _, v in items], color="#2980b9")
    ax.set_xlabel("Keyword evidence (weighted hits)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    return fig
