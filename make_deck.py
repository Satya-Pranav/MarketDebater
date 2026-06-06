"""Generate MarketDebaters_Deck.pdf — 10-slide submission deck.

Run:  python make_deck.py
Out:  MarketDebaters_Deck.pdf  (landscape letter, ~10 pages, < 1 MB)
"""
from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

OUT_PATH = "MarketDebaters_Deck.pdf"

# ── Page geometry ───────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(letter)  # 11" x 8.5"
MARGIN = 0.55 * inch

# ── Palette (matches the Django UI theme) ──────────────────────────────────
BG_DARK = colors.HexColor("#0f172a")
BG_PANEL = colors.HexColor("#1e293b")
BORDER = colors.HexColor("#334155")
TEXT_PRIMARY = colors.HexColor("#f1f5f9")
TEXT_SECONDARY = colors.HexColor("#cbd5e1")
TEXT_MUTED = colors.HexColor("#94a3b8")
ACCENT = colors.HexColor("#38bdf8")
ACCENT_DEEP = colors.HexColor("#0ea5e9")
BULL = colors.HexColor("#22c55e")
BEAR = colors.HexColor("#ef4444")
NEUTRAL = colors.HexColor("#94a3b8")
CHAIR = colors.HexColor("#f59e0b")
SUCCESS = colors.HexColor("#22c55e")


# ── Shared drawing helpers ─────────────────────────────────────────────────
def page_bg(c):
    c.setFillColor(BG_DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def slide_header(c, slide_num: int, title: str, eyebrow: str | None = None):
    # Top decorative line
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2)
    c.line(MARGIN, PAGE_H - 0.4 * inch, MARGIN + 0.8 * inch, PAGE_H - 0.4 * inch)

    # Slide counter
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 10)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.4 * inch, f"{slide_num} / 10")

    # Eyebrow (small caps)
    y = PAGE_H - 0.8 * inch
    if eyebrow:
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(MARGIN, y, eyebrow.upper())
        y -= 0.35 * inch

    # Title
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(MARGIN, y, title)


def slide_footer(c):
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, 0.35 * inch, "MarketDebater Swarm · Team MarketDebaters · Educational only — not investment advice")
    c.drawRightString(PAGE_W - MARGIN, 0.35 * inch, "github.com/Satya-Pranav/MarketDebater")


def bullet_text(c, x: float, y: float, items: list[str], width: float, font_size: int = 12, leading: float = 0.32):
    """Render a list of bullets at (x, y). Wraps long lines crudely on word boundaries."""
    c.setFont("Helvetica", font_size)
    for item in items:
        c.setFillColor(ACCENT)
        c.drawString(x, y, "▸")
        c.setFillColor(TEXT_SECONDARY)
        # crude wrap
        words = item.split(" ")
        line = ""
        line_y = y
        for w in words:
            test = (line + " " + w).strip()
            if c.stringWidth(test, "Helvetica", font_size) > width - 0.3 * inch:
                c.drawString(x + 0.3 * inch, line_y, line)
                line_y -= 0.22 * inch
                line = w
            else:
                line = test
        if line:
            c.drawString(x + 0.3 * inch, line_y, line)
        y = line_y - leading * inch


def panel(c, x: float, y: float, w: float, h: float, title: str | None = None, accent_color=ACCENT):
    c.setFillColor(BG_PANEL)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
    if title:
        c.setStrokeColor(accent_color)
        c.setLineWidth(2)
        c.line(x, y + h - 0.05 * inch, x + 0.6 * inch, y + h - 0.05 * inch)
        c.setFillColor(accent_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + 0.15 * inch, y + h - 0.3 * inch, title.upper())


# ── Slide 1: Cover ─────────────────────────────────────────────────────────
def slide_cover(c):
    page_bg(c)

    # Top + bottom accent bars frame the slide.
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 0.12 * inch, PAGE_W, 0.12 * inch, fill=1, stroke=0)
    c.rect(0, 0, PAGE_W, 0.12 * inch, fill=1, stroke=0)

    # Centered logo triangle (small).
    cx = PAGE_W / 2
    logo_top_y = PAGE_H - 1.05 * inch
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2.5)
    c.line(cx, logo_top_y, cx + 0.32 * inch, logo_top_y - 0.55 * inch)
    c.line(cx + 0.32 * inch, logo_top_y - 0.55 * inch, cx - 0.32 * inch, logo_top_y - 0.55 * inch)
    c.line(cx - 0.32 * inch, logo_top_y - 0.55 * inch, cx, logo_top_y)

    # Eyebrow text.
    y = PAGE_H - 1.95 * inch
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(cx, y, "TEAM MARKETDEBATERS   ·   HACKATHON SUBMISSION")

    # Project title — single line, big.
    y -= 0.85 * inch
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 54)
    c.drawCentredString(cx, y, "MarketDebater Swarm")

    # Tagline directly under the title.
    y -= 0.55 * inch
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, y, "A debate-based AI investment committee for US-listed stocks")

    # Short horizontal divider rule for visual rhythm.
    y -= 0.45 * inch
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.8)
    c.line(cx - 1.6 * inch, y, cx + 1.6 * inch, y)

    # Differentiator pill — centered, generous padding.
    y -= 0.85 * inch
    pill_w = 8.6 * inch
    pill_h = 0.85 * inch
    c.setFillColor(BG_PANEL)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.5)
    c.roundRect(cx - pill_w / 2, y, pill_w, pill_h, 10, fill=1, stroke=1)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(cx, y + pill_h - 0.28 * inch, "THE DIFFERENTIATOR")
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica", 12)
    c.drawCentredString(
        cx,
        y + 0.28 * inch,
        "Hallucinated numbers don't reach the verdict — a deterministic Python verifier catches them first.",
    )

    # "Built by" section — two columns, Satya Pranav first.
    y -= 1.45 * inch
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, y, "BUILT BY")

    member_y = y - 0.45 * inch
    members = [
        {"name": "P Satya Pranav", "handle": "@pranavps47", "x_offset": -1.95 * inch},
        {"name": "PVR Pratyusha", "handle": "@PVRPratyusha", "x_offset": +1.95 * inch},
    ]
    for m in members:
        mx = cx + m["x_offset"]
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(mx, member_y, m["name"])
        c.setFillColor(ACCENT)
        c.setFont("Helvetica", 12)
        c.drawCentredString(mx, member_y - 0.32 * inch, m["handle"])

    # Vertical divider between the two team columns.
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.6)
    c.line(cx, member_y + 0.25 * inch, cx, member_y - 0.45 * inch)

    # Live URL at the very bottom.
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 10)
    c.drawCentredString(cx, 0.85 * inch, "LIVE DEMO")
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(cx, 0.58 * inch, "web-production-f16ae.up.railway.app")


# ── Slide 2: The Problem ───────────────────────────────────────────────────
def slide_problem(c):
    page_bg(c)
    slide_header(c, 2, "Retail investors get one-sided AI advice", eyebrow="The Problem")

    # Three problem cards
    card_w = (PAGE_W - 2 * MARGIN - 0.6 * inch) / 3
    card_h = 3.2 * inch
    y = 3 * inch

    cards = [
        {
            "icon": "💬",
            "title": "Chatbot consensus",
            "body": "ChatGPT, Gemini, Copilot all present a single confident opinion. No dissent, no devil's advocate, no risk frame.",
        },
        {
            "icon": "🎲",
            "title": "Hallucinated stats",
            "body": "Numbers in LLM-generated investment write-ups are wrong ~10–20% of the time and the user has no way to know which.",
        },
        {
            "icon": "📚",
            "title": "Information overload",
            "body": "Prices, news, 10-Ks, 10-Qs, 8-Ks, XBRL fundamentals — no single workflow grounds an opinion against all three at once.",
        },
    ]
    for i, card in enumerate(cards):
        x = MARGIN + i * (card_w + 0.3 * inch)
        panel(c, x, y, card_w, card_h, title=None)
        c.setFont("Helvetica", 32)
        c.drawString(x + 0.3 * inch, y + card_h - 0.7 * inch, card["icon"])
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(x + 0.3 * inch, y + card_h - 1.3 * inch, card["title"])
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 11)
        # crude wrap
        words = card["body"].split(" ")
        line = ""
        line_y = y + card_h - 1.7 * inch
        for w in words:
            test = (line + " " + w).strip()
            if c.stringWidth(test, "Helvetica", 11) > card_w - 0.6 * inch:
                c.drawString(x + 0.3 * inch, line_y, line)
                line_y -= 0.2 * inch
                line = w
            else:
                line = test
        c.drawString(x + 0.3 * inch, line_y, line)

    # Punchline
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, 2.4 * inch,
                 "→ Investors need visible disagreement and verifiable claims, not another confident voice.")

    slide_footer(c)


# ── Slide 3: The Solution ──────────────────────────────────────────────────
def slide_solution(c):
    page_bg(c)
    slide_header(c, 3, "A debate, fact-checked by code", eyebrow="The Solution")

    # Left: bullet list
    bullet_text(
        c,
        MARGIN,
        PAGE_H - 1.9 * inch,
        [
            "Three rival persona LLMs argue each stock — PermaBull, PermaBear, Risk Manager.",
            "All three argue from one immutable snapshot of prices, news, and SEC filings.",
            "A deterministic Python verifier re-checks every numeric claim against the snapshot.",
            "A separate Chair LLM weights only verified arguments and issues a transparent verdict.",
            "Verdicts persist to a daily ranked leaderboard — top buys and top shorts in one view.",
        ],
        PAGE_W * 0.55 - MARGIN,
        font_size=13,
        leading=0.38,
    )

    # Right: verdict preview panel
    px, py, pw, ph = PAGE_W * 0.55, 1.5 * inch, PAGE_W - PAGE_W * 0.55 - MARGIN, PAGE_H - 2.8 * inch
    panel(c, px, py, pw, ph, title="Verdict ▸ AAPL · 1 round", accent_color=ACCENT)

    # Inside the panel — verdict pill
    c.setFillColor(BULL)
    c.roundRect(px + 0.3 * inch, py + ph - 1.2 * inch, 1.4 * inch, 0.4 * inch, 12, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(px + 1.0 * inch, py + ph - 1.07 * inch, "ACCUMULATE")

    # Persona bars
    persona_rows = [("PermaBull", 0.82, BULL), ("PermaBear", 0.35, BEAR), ("Risk Manager", 0.55, NEUTRAL)]
    bar_y = py + ph - 2.0 * inch
    for label, weight, color in persona_rows:
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10)
        c.drawString(px + 0.3 * inch, bar_y, label)
        # bar background
        c.setFillColor(BORDER)
        c.roundRect(px + 1.6 * inch, bar_y - 0.05 * inch, pw - 2.4 * inch, 0.18 * inch, 3, fill=1, stroke=0)
        # bar fill
        c.setFillColor(color)
        c.roundRect(px + 1.6 * inch, bar_y - 0.05 * inch, (pw - 2.4 * inch) * weight, 0.18 * inch, 3, fill=1, stroke=0)
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica", 9)
        c.drawRightString(px + pw - 0.3 * inch, bar_y, f"{weight:.2f}")
        bar_y -= 0.35 * inch

    # Footer note
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(px + 0.3 * inch, py + 0.3 * inch, "Net bull score = bull weight − bear weight = +0.47")

    slide_footer(c)


# ── Slide 4: Architecture ──────────────────────────────────────────────────
def slide_architecture(c):
    page_bg(c)
    slide_header(c, 4, "Five tiers, one immutable snapshot", eyebrow="Architecture")

    cx = PAGE_W / 2
    top_y = PAGE_H - 1.7 * inch

    # Tier 1: Data sources (3 boxes)
    sources = [
        ("yfinance", "EOD OHLCV\n+ technicals", BULL),
        ("Grok 4.1 Fast", "News editor", CHAIR),
        ("sec-api.io", "10-K · 10-Q · 8-K\n+ XBRL fundamentals", ACCENT_DEEP),
    ]
    box_w, box_h = 1.85 * inch, 0.95 * inch
    spacing = 0.3 * inch
    total_w = box_w * 3 + spacing * 2
    start_x = cx - total_w / 2
    for i, (name, desc, color) in enumerate(sources):
        x = start_x + i * (box_w + spacing)
        c.setFillColor(BG_PANEL)
        c.setStrokeColor(color)
        c.setLineWidth(1.5)
        c.roundRect(x, top_y - box_h, box_w, box_h, 6, fill=1, stroke=1)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x + box_w / 2, top_y - 0.35 * inch, name)
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 9)
        lines = desc.split("\n")
        for j, line in enumerate(lines):
            c.drawCentredString(x + box_w / 2, top_y - 0.6 * inch - j * 0.18 * inch, line)
        # arrow down
        arrow_y = top_y - box_h - 0.05 * inch
        c.setStrokeColor(TEXT_MUTED)
        c.setLineWidth(1.2)
        c.line(x + box_w / 2, arrow_y, x + box_w / 2, arrow_y - 0.35 * inch)
        c.line(x + box_w / 2 - 0.06 * inch, arrow_y - 0.27 * inch, x + box_w / 2, arrow_y - 0.35 * inch)
        c.line(x + box_w / 2 + 0.06 * inch, arrow_y - 0.27 * inch, x + box_w / 2, arrow_y - 0.35 * inch)

    # Tier 2: Snapshot
    snap_y = top_y - box_h - 0.45 * inch
    snap_w = total_w
    snap_h = 0.55 * inch
    c.setFillColor(BG_PANEL)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2)
    c.roundRect(start_x, snap_y - snap_h, snap_w, snap_h, 6, fill=1, stroke=1)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx, snap_y - 0.22 * inch, "IMMUTABLE SNAPSHOT  ·  filings metrics folded in")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, snap_y - 0.42 * inch, "single source of truth — every persona argues from this")

    # Arrow down
    c.setStrokeColor(TEXT_MUTED)
    c.setLineWidth(1.2)
    ay = snap_y - snap_h - 0.05 * inch
    c.line(cx, ay, cx, ay - 0.3 * inch)
    c.line(cx - 0.06 * inch, ay - 0.22 * inch, cx, ay - 0.3 * inch)
    c.line(cx + 0.06 * inch, ay - 0.22 * inch, cx, ay - 0.3 * inch)

    # Tier 3: Personas (3 boxes — wider, with the subtitle on its own line)
    persona_y = ay - 0.35 * inch
    p_box_w = 1.95 * inch
    p_box_h = 0.7 * inch
    p_total = p_box_w * 3 + spacing * 2
    p_start = cx - p_total / 2
    personas = [("PermaBull", BULL), ("PermaBear", BEAR), ("Risk Manager", NEUTRAL)]
    for i, (name, color) in enumerate(personas):
        x = p_start + i * (p_box_w + spacing)
        c.setFillColor(BG_PANEL)
        c.setStrokeColor(color)
        c.setLineWidth(1.5)
        c.roundRect(x, persona_y - p_box_h, p_box_w, p_box_h, 6, fill=1, stroke=1)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(x + p_box_w / 2, persona_y - 0.32 * inch, name)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawCentredString(x + p_box_w / 2, persona_y - 0.55 * inch, "DeepSeek-V4-Flash")

    # Arrow from persona row down to the Verifier/Chair tier.
    arr_top = persona_y - p_box_h - 0.05 * inch
    arr_bot = arr_top - 0.4 * inch
    c.setStrokeColor(TEXT_MUTED)
    c.setLineWidth(1.2)
    c.line(cx, arr_top, cx, arr_bot)
    c.line(cx - 0.06 * inch, arr_bot + 0.08 * inch, cx, arr_bot)
    c.line(cx + 0.06 * inch, arr_bot + 0.08 * inch, cx, arr_bot)

    # Tier 4: Verifier + Chair (two boxes side by side)
    vc_y = arr_bot - 0.1 * inch
    vw, vh = 3.2 * inch, 0.85 * inch
    c.setFillColor(BG_PANEL)
    c.setStrokeColor(SUCCESS)
    c.setLineWidth(2)
    c.roundRect(cx - vw - 0.15 * inch, vc_y - vh, vw, vh, 6, fill=1, stroke=1)
    c.setFillColor(SUCCESS)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx - vw / 2 - 0.15 * inch, vc_y - 0.3 * inch, "DETERMINISTIC VERIFIER")
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx - vw / 2 - 0.15 * inch, vc_y - 0.5 * inch, "pure Python — re-checks every numeric claim")
    c.drawCentredString(cx - vw / 2 - 0.15 * inch, vc_y - 0.65 * inch, "against the snapshot · no LLM, no randomness")

    c.setFillColor(BG_PANEL)
    c.setStrokeColor(CHAIR)
    c.roundRect(cx + 0.15 * inch, vc_y - vh, vw, vh, 6, fill=1, stroke=1)
    c.setFillColor(CHAIR)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx + vw / 2 + 0.15 * inch, vc_y - 0.3 * inch, "CHAIR · LLM-AS-JUDGE")
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx + vw / 2 + 0.15 * inch, vc_y - 0.5 * inch, "weights = grounding × confidence")
    c.drawCentredString(cx + vw / 2 + 0.15 * inch, vc_y - 0.65 * inch, "issues final verdict + rationale")

    # Arrow from Verifier/Chair tier down to the verdict bar.
    arr2_top = vc_y - vh - 0.05 * inch
    arr2_bot = arr2_top - 0.3 * inch
    c.setStrokeColor(TEXT_MUTED)
    c.setLineWidth(1.2)
    c.line(cx, arr2_top, cx, arr2_bot)
    c.line(cx - 0.06 * inch, arr2_bot + 0.08 * inch, cx, arr2_bot)
    c.line(cx + 0.06 * inch, arr2_bot + 0.08 * inch, cx, arr2_bot)

    # Tier 5: Verdict + Storage — bar widened to fit the full label.
    final_w = 9.4 * inch
    final_h = 0.5 * inch
    final_y = arr2_bot - 0.15 * inch
    c.setFillColor(BG_PANEL)
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.5)
    c.roundRect(cx - final_w / 2, final_y - final_h, final_w, final_h, 8, fill=1, stroke=1)
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(
        cx, final_y - 0.24 * inch,
        "VERDICT  ·  Strong Buy / Accumulate / Hold / Reduce  →  Azure Blob (ranked daily leaderboard)",
    )

    slide_footer(c)


# ── Slide 5: Differentiator ────────────────────────────────────────────────
def slide_differentiator(c):
    page_bg(c)
    slide_header(c, 5, "Hallucinated numbers don't reach the verdict", eyebrow="The Differentiator")

    # Two side-by-side panels: bad claim vs verified
    panel_w = (PAGE_W - 2 * MARGIN - 0.4 * inch) / 2
    panel_h = 3.5 * inch
    py = 2.3 * inch

    # Left: bad claim
    panel(c, MARGIN, py, panel_w, panel_h, title="✗ HALLUCINATED CLAIM", accent_color=BEAR)
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN + 0.2 * inch, py + panel_h - 0.8 * inch, "PermaBull says:")
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica-Oblique", 11)
    c.drawString(MARGIN + 0.2 * inch, py + panel_h - 1.1 * inch, "\"AAPL's revenue=$999B beats every peer — clear buy.\"")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Courier", 9)
    c.drawString(MARGIN + 0.2 * inch, py + panel_h - 1.5 * inch, "cited_metric=revenue=999000000000")

    # Verifier code-ish line
    code_y = py + 0.7 * inch
    c.setFillColor(colors.HexColor("#0a1220"))
    c.roundRect(MARGIN + 0.2 * inch, code_y, panel_w - 0.4 * inch, 1.5 * inch, 4, fill=1, stroke=0)
    c.setFillColor(BEAR)
    c.setFont("Courier-Bold", 9)
    c.drawString(MARGIN + 0.35 * inch, code_y + 1.25 * inch, "verify_grounding(claim, snapshot):")
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Courier", 9)
    c.drawString(MARGIN + 0.35 * inch, code_y + 1.05 * inch, "  truth = snapshot['revenue']  # 395.76B")
    c.drawString(MARGIN + 0.35 * inch, code_y + 0.85 * inch, "  claimed = 999_000_000_000")
    c.drawString(MARGIN + 0.35 * inch, code_y + 0.65 * inch, "  if abs(claimed - truth)/truth > 0.05:")
    c.setFillColor(BEAR)
    c.drawString(MARGIN + 0.35 * inch, code_y + 0.45 * inch, "      reject_as_hallucination()")
    c.setFillColor(BEAR)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN + 0.2 * inch, py + 0.3 * inch, "→ PermaBull's weight slashed by the Chair")

    # Right: verified claim
    px = MARGIN + panel_w + 0.4 * inch
    panel(c, px, py, panel_w, panel_h, title="✓ VERIFIED CLAIM", accent_color=SUCCESS)
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(px + 0.2 * inch, py + panel_h - 0.8 * inch, "PermaBull says:")
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica-Oblique", 11)
    c.drawString(px + 0.2 * inch, py + panel_h - 1.1 * inch, "\"AAPL's RSI=42 leaves headroom for a move up.\"")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Courier", 9)
    c.drawString(px + 0.2 * inch, py + panel_h - 1.5 * inch, "cited_metric=rsi_14=42.3")

    code_y = py + 0.7 * inch
    c.setFillColor(colors.HexColor("#0a1220"))
    c.roundRect(px + 0.2 * inch, code_y, panel_w - 0.4 * inch, 1.5 * inch, 4, fill=1, stroke=0)
    c.setFillColor(SUCCESS)
    c.setFont("Courier-Bold", 9)
    c.drawString(px + 0.35 * inch, code_y + 1.25 * inch, "verify_grounding(claim, snapshot):")
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Courier", 9)
    c.drawString(px + 0.35 * inch, code_y + 1.05 * inch, "  truth = snapshot['rsi_14']  # 42.50")
    c.drawString(px + 0.35 * inch, code_y + 0.85 * inch, "  claimed = 42.3")
    c.drawString(px + 0.35 * inch, code_y + 0.65 * inch, "  if abs(claimed - truth)/truth < 0.05:")
    c.setFillColor(SUCCESS)
    c.drawString(px + 0.35 * inch, code_y + 0.45 * inch, "      accept(grounding=1.0)")
    c.setFillColor(SUCCESS)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(px + 0.2 * inch, py + 0.3 * inch, "→ Full weight carried into the verdict")

    # Bottom emphasis
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(PAGE_W / 2, 1.7 * inch,
                        "If grounding were an LLM call, this whole project would be theatre.")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, 1.45 * inch,
                        "It's pure Python with regex, value lookups, and arithmetic recomputation. Unit tests are first-class.")

    slide_footer(c)


# ── Slide 6: AI Integration ────────────────────────────────────────────────
def slide_ai(c):
    page_bg(c)
    slide_header(c, 6, "Three LLM roles, one Azure key", eyebrow="AI Integration")

    # Three cards
    card_w = (PAGE_W - 2 * MARGIN - 0.6 * inch) / 3
    card_h = 4 * inch
    y = 1.7 * inch

    roles = [
        {
            "title": "PERSONAS",
            "color": BULL,
            "model": "DeepSeek-V4-Flash",
            "subtitle": "(DeepSeek-R1 wired, off by default)",
            "purpose": "Three rival arguments per ticker per round.",
            "details": [
                "Same model, 3 system prompts.",
                "Structured JSON output:",
                "  {stance, points, confidence}",
                "Each point ships a cited_metric=name=value.",
                "Round 3 must address top opponent point.",
            ],
        },
        {
            "title": "CHAIR (JUDGE)",
            "color": CHAIR,
            "model": "DeepSeek-V4-Flash",
            "subtitle": "(separate role from personas)",
            "purpose": "Weights only verified claims; issues verdict.",
            "details": [
                "Reads grounding × confidence",
                "Picks Strong Buy / Accumulate / Hold / Reduce.",
                "Emits a transparent rationale.",
                "Different prompt = different blind spots than",
                "the personas it judges.",
            ],
        },
        {
            "title": "NEWS EDITOR",
            "color": ACCENT,
            "model": "Grok 4.1 Fast Reasoning",
            "subtitle": "(via Azure AI Foundry catalog)",
            "purpose": "Filters and summarizes RSS to top items.",
            "details": [
                "Pulls 20 RSS headlines per ticker.",
                "Selects 8 most material; tight summaries.",
                "Same Azure key, no separate xAI account.",
                "Disable via GROK_MODEL='' to fall back",
                "to raw RSS without LLM editing.",
            ],
        },
    ]
    for i, role in enumerate(roles):
        x = MARGIN + i * (card_w + 0.3 * inch)
        panel(c, x, y, card_w, card_h, title=role["title"], accent_color=role["color"])
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x + 0.25 * inch, y + card_h - 0.85 * inch, role["model"])
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(x + 0.25 * inch, y + card_h - 1.05 * inch, role["subtitle"])
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 0.25 * inch, y + card_h - 1.4 * inch, role["purpose"])
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10)
        dy = y + card_h - 1.8 * inch
        for line in role["details"]:
            c.drawString(x + 0.25 * inch, dy, line)
            dy -= 0.22 * inch

    # Footer: orchestration note
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(PAGE_W / 2, 1.1 * inch,
                        "All three reachable through Azure AI Foundry's OpenAI-compatible /openai/v1 endpoint  ·  one key, three model deployments")

    slide_footer(c)


# ── Slide 7: Demo screenshot — Single Debate ───────────────────────────────
def slide_demo_debate(c):
    page_bg(c)
    slide_header(c, 7, "Verdict page · grounded debate transcript", eyebrow="Demo — Single Debate")

    # Mockup of the result page
    x = MARGIN + 0.2 * inch
    y = 1.2 * inch
    w = PAGE_W - 2 * MARGIN - 0.4 * inch
    h = 5.3 * inch
    panel(c, x, y, w, h)

    # Top banner
    c.setFillColor(colors.HexColor("#f59e0b").clone(alpha=0.15))
    c.rect(x, y + h - 0.3 * inch, w, 0.3 * inch, fill=1, stroke=0)
    c.setFillColor(CHAIR)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 0.2 * inch, y + h - 0.2 * inch, "⚠ Educational only — not financial advice")

    # Top nav
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 0.3 * inch, y + h - 0.6 * inch, "Single Debate")
    c.setFillColor(TEXT_MUTED)
    c.drawString(x + 1.5 * inch, y + h - 0.6 * inch, "Daily Suggestions")

    # Snapshot card with verdict
    snap_y = y + h - 1.7 * inch
    c.setFillColor(BG_DARK)
    c.setStrokeColor(BORDER)
    c.roundRect(x + 0.3 * inch, snap_y, w - 0.6 * inch, 1 * inch, 6, fill=1, stroke=1)
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(x + 0.5 * inch, snap_y + 0.6 * inch, "Apple Inc.")
    # Verdict inline pill
    c.setFillColor(CHAIR)
    c.roundRect(x + 2.5 * inch, snap_y + 0.55 * inch, 0.7 * inch, 0.3 * inch, 10, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x + 2.85 * inch, snap_y + 0.62 * inch, "HOLD")
    c.setFillColor(BULL)
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(x + w - 0.5 * inch, snap_y + 0.6 * inch, "$307.34")
    c.setFillColor(BULL)
    c.setFont("Helvetica", 10)
    c.drawRightString(x + w - 0.5 * inch, snap_y + 0.35 * inch, "+1.42%")

    # Persona cards row
    persona_y = snap_y - 1.6 * inch
    p_w = (w - 0.8 * inch) / 3
    persona_data = [
        ("PermaBull", 0.85, 0.78, 0.66, BULL),
        ("PermaBear", 0.62, 0.55, 0.34, BEAR),
        ("Risk Manager", 0.90, 0.60, 0.54, NEUTRAL),
    ]
    for i, (name, g, conf, weight, color) in enumerate(persona_data):
        px = x + 0.3 * inch + i * (p_w + 0.1 * inch)
        c.setFillColor(BG_DARK)
        c.setStrokeColor(color)
        c.setLineWidth(1)
        c.roundRect(px, persona_y, p_w, 1.4 * inch, 6, fill=1, stroke=1)
        c.setFillColor(color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(px + 0.15 * inch, persona_y + 1.15 * inch, name)
        # rows
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(px + 0.15 * inch, persona_y + 0.85 * inch, "Grounding")
        c.drawString(px + 0.15 * inch, persona_y + 0.55 * inch, "Confidence")
        c.drawString(px + 0.15 * inch, persona_y + 0.25 * inch, "Weight")
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(px + p_w - 0.15 * inch, persona_y + 0.85 * inch, f"{g:.2f}")
        c.drawRightString(px + p_w - 0.15 * inch, persona_y + 0.55 * inch, f"{conf:.2f}")
        c.drawRightString(px + p_w - 0.15 * inch, persona_y + 0.25 * inch, f"{weight:.3f}")

    # Deep-dive collapsible card preview
    dd_y = persona_y - 1.3 * inch
    c.setFillColor(BG_DARK)
    c.setStrokeColor(BORDER)
    c.roundRect(x + 0.3 * inch, dd_y, w - 0.6 * inch, 1.1 * inch, 6, fill=1, stroke=1)
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 0.5 * inch, dd_y + 0.85 * inch, "Persona Deep-dive ▾")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(x + 2.3 * inch, dd_y + 0.85 * inch, "1 round · each persona's claims, citations & sources")

    # Round badge + claim mock
    c.setFillColor(ACCENT)
    c.roundRect(x + 0.5 * inch, dd_y + 0.45 * inch, 0.95 * inch, 0.22 * inch, 4, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(x + 0.975 * inch, dd_y + 0.52 * inch, "ROUND 1 · CASE")
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.5 * inch, dd_y + 0.22 * inch,
                 "▸ Trading at $307.34, below 52-week high of $321 — room to run.")
    c.setFillColor(ACCENT)
    c.setFont("Courier", 8)
    c.drawString(x + 0.5 * inch, dd_y + 0.05 * inch, "cited_metric=week52_high=321.0")

    slide_footer(c)


# ── Slide 8: Demo screenshot — Daily Suggestions ───────────────────────────
def slide_demo_leaderboard(c):
    page_bg(c)
    slide_header(c, 8, "Leaderboard · top buys and top shorts in one view", eyebrow="Demo — Daily Suggestions")

    x = MARGIN + 0.2 * inch
    y = 1.2 * inch
    w = PAGE_W - 2 * MARGIN - 0.4 * inch
    h = 5.3 * inch
    panel(c, x, y, w, h)

    # Nav
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 0.3 * inch, y + h - 0.6 * inch, "Single Debate")
    c.setFillColor(ACCENT)
    c.drawString(x + 1.5 * inch, y + h - 0.6 * inch, "Daily Suggestions")

    # Scan panel
    sp_y = y + h - 2 * inch
    c.setFillColor(BG_DARK)
    c.setStrokeColor(BORDER)
    c.roundRect(x + 0.3 * inch, sp_y, w - 0.6 * inch, 1.1 * inch, 6, fill=1, stroke=1)
    c.setFillColor(TEXT_PRIMARY)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + 0.5 * inch, sp_y + 0.8 * inch, "Run a fresh scan")
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(x + 0.5 * inch, sp_y + 0.55 * inch, "Trigger a synchronous scan; refreshes the ranking below.")
    # Form mock
    c.setStrokeColor(BORDER)
    c.roundRect(x + 0.5 * inch, sp_y + 0.15 * inch, 3.5 * inch, 0.3 * inch, 4, fill=0, stroke=1)
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Courier", 9)
    c.drawString(x + 0.6 * inch, sp_y + 0.23 * inch, "AAPL,MSFT,GOOGL,NVDA,AMZN")
    c.setFillColor(ACCENT)
    c.roundRect(x + 4.5 * inch, sp_y + 0.15 * inch, 1 * inch, 0.3 * inch, 4, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(x + 5 * inch, sp_y + 0.23 * inch, "Run scan")

    # Table
    table_y = sp_y - 2.6 * inch
    rows = [
        ("1", "GOOGL", "Alphabet Inc.", "Hold", "+0.073", BULL),
        ("2", "AAPL", "Apple Inc.", "Hold", "+0.022", BULL),
        ("3", "AMZN", "Amazon Inc.", "Hold", "0.000", NEUTRAL),
        ("4", "MSFT", "Microsoft Corp.", "Hold", "-0.171", BEAR),
        ("5", "NVDA", "NVIDIA Corp.", "Reduce", "-0.402", BEAR),
    ]
    # Header
    headers = ["#", "TICKER", "COMPANY", "VERDICT", "NET BULL"]
    col_x = [x + 0.5 * inch, x + 1 * inch, x + 2 * inch, x + 4.5 * inch, x + 6.5 * inch]
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica-Bold", 9)
    for i, hd in enumerate(headers):
        c.drawString(col_x[i], table_y + 1.9 * inch, hd)
    # Row separator
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.5)
    c.line(x + 0.3 * inch, table_y + 1.78 * inch, x + w - 0.3 * inch, table_y + 1.78 * inch)
    # Rows
    for i, (rank, tk, co, vd, nb, vd_color) in enumerate(rows):
        row_y = table_y + 1.5 * inch - i * 0.35 * inch
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica", 11)
        c.drawString(col_x[0], row_y, rank)
        # Ticker pill
        c.setFillColor(colors.HexColor("#38bdf8").clone(alpha=0.12))
        c.setStrokeColor(ACCENT)
        c.roundRect(col_x[1] - 0.05 * inch, row_y - 0.03 * inch, 0.55 * inch, 0.22 * inch, 4, fill=1, stroke=1)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(col_x[1] + 0.225 * inch, row_y + 0.05 * inch, tk)
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10)
        c.drawString(col_x[2], row_y, co)
        # Verdict pill
        pill_color = CHAIR if vd == "Hold" else (BEAR if vd in ("Reduce",) else BULL)
        c.setFillColor(pill_color)
        c.roundRect(col_x[3] - 0.05 * inch, row_y - 0.03 * inch, 0.7 * inch, 0.22 * inch, 8, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(col_x[3] + 0.3 * inch, row_y + 0.05 * inch, vd.upper())
        # Net bull
        c.setFillColor(vd_color)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(col_x[4], row_y, nb)
        # Separator
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.3)
        c.line(x + 0.3 * inch, row_y - 0.1 * inch, x + w - 0.3 * inch, row_y - 0.1 * inch)

    slide_footer(c)


# ── Slide 9: Tech stack & deployment ───────────────────────────────────────
def slide_stack(c):
    page_bg(c)
    slide_header(c, 9, "Microsoft-first stack, deploy-anywhere shape", eyebrow="Tech Stack & Deployment")

    # 2x3 grid of tech cards
    cols = 3
    rows = 2
    margin_x = 0.4 * inch
    margin_y = 0.35 * inch
    grid_y = 1.5 * inch
    grid_h = 4.5 * inch
    cell_w = (PAGE_W - 2 * MARGIN - margin_x * (cols - 1)) / cols
    cell_h = (grid_h - margin_y * (rows - 1)) / rows

    cells = [
        {"title": "LLM Brain", "lines": [
            "Azure AI Foundry",
            "/openai/v1 (OpenAI-compatible)",
            "DeepSeek-V4-Flash · DeepSeek-R1",
            "Grok 4.1 Fast Reasoning",
            "Single key, three deployments"
        ], "color": ACCENT},
        {"title": "Frontend", "lines": [
            "Django 6.0 + WhiteNoise",
            "gunicorn (2 workers · 30-min timeout)",
            "Streamlit (collaborator-owned)",
            "Same data contract for both UIs",
            ""
        ], "color": BULL},
        {"title": "Data Sources", "lines": [
            "yfinance — EOD OHLCV + technicals",
            "sec-api.io — 10-K · 10-Q · 8-K + XBRL",
            "Google News RSS → Grok edited",
            "Watchlist or Google Sheet universe",
            ""
        ], "color": CHAIR},
        {"title": "Persistence", "lines": [
            "Azure Blob Storage",
            "verdicts/<date>/<ticker>.json",
            "verdicts/<date>/index.json (ranked)",
            "LOCAL_RESULTS_DIR fallback for dev",
            ""
        ], "color": ACCENT_DEEP},
        {"title": "Search / RAG", "lines": [
            "Azure AI Search (BM25)",
            "Indexes news + filings together",
            "source_type filter at query time",
            "Graceful no-op when unconfigured",
            ""
        ], "color": NEUTRAL},
        {"title": "Hosting & CI", "lines": [
            "Railway (~$5–10 / month)",
            "Auto-deploy from main",
            "GitHub Actions: on-demand scan",
            "Procfile + WhiteNoise = no nginx",
            "Live: web-production-f16ae.up.railway.app"
        ], "color": SUCCESS},
    ]
    for idx, cell in enumerate(cells):
        col = idx % cols
        row = idx // cols
        x = MARGIN + col * (cell_w + margin_x)
        y = grid_y + grid_h - cell_h - row * (cell_h + margin_y)
        panel(c, x, y, cell_w, cell_h, title=cell["title"], accent_color=cell["color"])
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10)
        line_y = y + cell_h - 0.75 * inch
        for ln in cell["lines"]:
            if ln:
                c.setFillColor(ACCENT)
                c.drawString(x + 0.25 * inch, line_y, "·")
                c.setFillColor(TEXT_SECONDARY)
                c.drawString(x + 0.4 * inch, line_y, ln)
            line_y -= 0.24 * inch

    slide_footer(c)


# ── Slide 10: Future versions ──────────────────────────────────────────────
def slide_future(c):
    page_bg(c)
    slide_header(c, 10, "Future versions yet to come", eyebrow="What's Next")

    # Intro line under the title
    c.setFillColor(TEXT_SECONDARY)
    c.setFont("Helvetica", 13)
    c.drawString(
        MARGIN, PAGE_H - 1.7 * inch,
        "What ships next, beyond the hackathon scope — bigger universe, deeper data, real production posture.",
    )

    # 2 rows × 3 cols grid of roadmap cards
    cards = [
        {
            "num": "01",
            "title": "Wider US universe",
            "lines": [
                "Nasdaq 100, S&P 500, Russell 3000.",
                "4.6K-ticker sheet already wired —",
                "one config flip + paid sec-api tier.",
            ],
            "color": BULL,
        },
        {
            "num": "02",
            "title": "IPO coverage",
            "lines": [
                "Ingest S-1 prospectuses pre-listing.",
                "Track lockup expiries + dilution.",
                "Day-one debate when pricing drops.",
            ],
            "color": ACCENT,
        },
        {
            "num": "03",
            "title": "Other markets",
            "lines": [
                "LSE, HKEX, TSE via yfinance suffix.",
                "Return to NSE / BSE where this began.",
                "Per-market filings adapter.",
            ],
            "color": ACCENT_DEEP,
        },
        {
            "num": "04",
            "title": "Earnings calls",
            "lines": [
                "Pull transcripts post-earnings.",
                "Persona Q&A on management tone.",
                "Sentiment delta into the snapshot.",
            ],
            "color": CHAIR,
        },
        {
            "num": "05",
            "title": "Backtested accuracy",
            "lines": [
                "Per-persona win rate vs returns.",
                "Chair auto-learns weighting.",
                "Confidence calibrated on history.",
            ],
            "color": SUCCESS,
        },
        {
            "num": "06",
            "title": "Streaming + mobile",
            "lines": [
                "SSE live transcripts — no 5-min wait.",
                "Background workers for bulk scans.",
                "PWA so it works on phones.",
            ],
            "color": NEUTRAL,
        },
    ]

    cols = 3
    rows = 2
    gap_x = 0.35 * inch
    gap_y = 0.35 * inch
    grid_bottom = 1.05 * inch
    grid_top = PAGE_H - 2.05 * inch  # below the intro line
    grid_h = grid_top - grid_bottom
    cell_w = (PAGE_W - 2 * MARGIN - gap_x * (cols - 1)) / cols
    cell_h = (grid_h - gap_y * (rows - 1)) / rows

    for idx, card in enumerate(cards):
        col = idx % cols
        row = idx // cols
        x = MARGIN + col * (cell_w + gap_x)
        y = grid_bottom + (rows - 1 - row) * (cell_h + gap_y)

        # Card panel
        panel(c, x, y, cell_w, cell_h, accent_color=card["color"])

        # Numbered badge in top-left
        badge_x = x + 0.3 * inch
        badge_y = y + cell_h - 0.85 * inch
        badge_r = 0.28 * inch
        c.setFillColor(card["color"])
        c.circle(badge_x + badge_r, badge_y + badge_r, badge_r, fill=1, stroke=0)
        c.setFillColor(BG_DARK)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(badge_x + badge_r, badge_y + badge_r - 0.075 * inch, card["num"])

        # Title to the right of the badge
        c.setFillColor(TEXT_PRIMARY)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(badge_x + 2 * badge_r + 0.15 * inch, badge_y + badge_r - 0.05 * inch, card["title"])

        # Description lines below
        c.setFillColor(TEXT_SECONDARY)
        c.setFont("Helvetica", 10.5)
        line_y = y + cell_h - 1.45 * inch
        for ln in card["lines"]:
            c.setFillColor(card["color"])
            c.drawString(x + 0.3 * inch, line_y, "·")
            c.setFillColor(TEXT_SECONDARY)
            c.drawString(x + 0.5 * inch, line_y, ln)
            line_y -= 0.26 * inch

    slide_footer(c)


# ── Compose all 10 slides ───────────────────────────────────────────────────
def build_pdf(path: str = OUT_PATH):
    c = canvas.Canvas(path, pagesize=landscape(letter))
    c.setTitle("MarketDebater Swarm — Hackathon Submission Deck")
    c.setAuthor("Team MarketDebaters · PVR Pratyusha & P Satya Pranav")

    for fn in [
        slide_cover,
        slide_problem,
        slide_solution,
        slide_architecture,
        slide_differentiator,
        slide_ai,
        slide_demo_debate,
        slide_demo_leaderboard,
        slide_stack,
        slide_future,
    ]:
        fn(c)
        c.showPage()

    c.save()
    return path


if __name__ == "__main__":
    out = build_pdf()
    print(f"Wrote {out}")
