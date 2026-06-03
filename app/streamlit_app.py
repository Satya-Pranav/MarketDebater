"""MarketDebater Swarm — Streamlit UI.

Two tabs:
  - Single Debate: live transcript + graded verdict card for one US ticker.
  - Leaderboard:   ranked cross-stock view from the most recent scan
                   (reads ``verdicts/latest/index.json`` from Blob or LOCAL_RESULTS_DIR).

Run:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import os
import sys

# Allow `streamlit run app/streamlit_app.py` to import the `app` package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# On a host (e.g. Streamlit Community Cloud) there is no .env — secrets are set
# in the platform dashboard. Mirror them into the environment BEFORE importing
# config, which reads os.getenv at import time.
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

from app import config, storage, universe
from app.chair import DISCLAIMER
from app.orchestrator import stream_debate

PERSONA = {
    "bull": {"label": "The Perma-Bull", "icon": "🐂", "color": "#16a34a"},
    "bear": {"label": "The Perma-Bear", "icon": "🐻", "color": "#dc2626"},
    "neutral": {"label": "The Risk Manager", "icon": "⚖️", "color": "#6b7280"},
}
VERDICT_COLOR = {
    "Strong Buy": "#15803d",
    "Accumulate": "#65a30d",
    "Hold": "#ca8a04",
    "Reduce": "#dc2626",
}


# --------------------------------------------------------------------------- #
# Renderers                                                                   #
# --------------------------------------------------------------------------- #
def render_snapshot(container, snapshot: dict, news: list[dict], filings: list[dict]) -> None:
    with container:
        st.subheader(
            f"📊 {snapshot.get('company', snapshot['ticker'])}  ·  as of {snapshot['as_of']}"
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            f"Price ({snapshot.get('currency', 'USD')})",
            snapshot["price"],
            f"{snapshot['change_pct']:+}%",
        )
        c2.metric("RSI (14)", snapshot["rsi_14"])
        c3.metric("SMA 50 / 200", f"{snapshot['sma_50']} / {snapshot['sma_200']}")
        c4.metric("52w range", f"{snapshot['week52_low']} – {snapshot['week52_high']}")

        # Show filings-derived fundamentals if present.
        fund_keys = ("revenue", "eps_diluted", "gross_margin", "debt_to_equity")
        fund = {k: snapshot[k] for k in fund_keys if k in snapshot}
        if fund:
            cols = st.columns(len(fund))
            for col, (k, v) in zip(cols, fund.items()):
                if k in {"gross_margin"}:
                    col.metric(k.replace("_", " ").title(), f"{v:.1%}")
                elif k == "revenue":
                    col.metric("Revenue", f"${v / 1e9:.2f}B" if v else "—")
                else:
                    col.metric(k.replace("_", " ").title(), v)

        col_news, col_filings = st.columns(2)
        with col_news:
            with st.expander(f"📰 News ({len(news)})", expanded=False):
                if not news:
                    st.caption("(no news fetched)")
                for n in news[:8]:
                    title = (
                        f"[{n['title']}]({n['url']})" if n.get("url") else n["title"]
                    )
                    st.markdown(f"- {title}  ·  *{n.get('source', '')}*")
        with col_filings:
            with st.expander(f"📄 SEC filings ({len(filings)})", expanded=False):
                if not filings:
                    st.caption("(no filings — set SEC_API_KEY to enable)")
                for f in filings[:6]:
                    head = f"**{f.get('form','')}**  ·  {f.get('filed_at','')[:10]}"
                    if f.get("url"):
                        head += f"  ·  [filing]({f['url']})"
                    st.markdown(head)
                    snippet = (f.get("sections") or "").strip()
                    if snippet:
                        st.caption(snippet[:240] + ("…" if len(snippet) > 240 else ""))


def render_argument(container, ev: dict) -> None:
    persona, arg = ev["persona"], ev["argument"]
    meta = PERSONA[persona]
    with container:
        with st.chat_message(persona, avatar=meta["icon"]):
            st.markdown(
                f"**{meta['label']}**  ·  Round {ev['round']}  ·  "
                f"stance **{arg['stance']}**  ·  confidence {float(arg['confidence']):.0%}"
            )
            for pt in arg.get("points", []):
                st.markdown(f"- {pt.get('claim', '')}")
                cite = pt.get("cited_metric", "")
                if cite:
                    st.caption(f"↳ `{cite}`  ·  {pt.get('source', '')}")


def render_verdict(container, verdict: dict, arguments: dict) -> None:
    with container:
        v = verdict["verdict"]
        color = VERDICT_COLOR.get(v, "#6b7280")
        net = verdict.get("net_bull_score", 0.0)
        st.markdown(
            f"<div style='background:{color};color:white;padding:1rem 1.5rem;"
            f"border-radius:10px;text-align:center;font-size:1.8rem;font-weight:800;"
            f"letter-spacing:.5px'>"
            f"VERDICT — {v}"
            f"<div style='font-size:1rem;font-weight:500;opacity:.9;margin-top:.25rem'>"
            f"net bull score {net:+.2f}</div></div>",
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown(f"**Chair's rationale:** {verdict.get('rationale', '')}")
        st.write("")

        st.markdown("##### How each analyst was graded")
        cols = st.columns(3)
        for col, persona in zip(cols, ["bull", "bear", "neutral"]):
            meta = PERSONA[persona]
            grading = verdict.get("grounding_scores", {}).get(persona, {})
            grounding = float(grading.get("grounding", 0.0))
            confidence = float(arguments.get(persona, {}).get("confidence", 0.0))
            weight = float(verdict.get("weights", {}).get(persona, 0.0))
            with col:
                st.markdown(f"**{meta['icon']} {meta['label']}**")
                # Three bar graphs per persona (grounding, weight, confidence).
                st.progress(min(grounding, 1.0), text=f"Grounding {grounding:.0%}")
                st.progress(min(weight, 1.0), text=f"Weight {weight:.2f}")
                st.progress(min(confidence, 1.0), text=f"Confidence {confidence:.0%}")
                flagged = grading.get("unverified_metrics") or []
                if flagged:
                    st.caption("🚩 Unverified: " + ", ".join(f"`{m}`" for m in flagged))

        st.write("")
        st.info(DISCLAIMER, icon="⚠️")


# --------------------------------------------------------------------------- #
# Leaderboard tab                                                             #
# --------------------------------------------------------------------------- #
def render_leaderboard() -> None:
    st.subheader("🏆 Latest cross-stock leaderboard")
    if not storage.is_configured():
        st.warning(
            "No storage configured. Set `AZURE_STORAGE_CONNECTION_STRING` (Blob) or "
            "`LOCAL_RESULTS_DIR=./out` (filesystem) in `.env`, then run "
            "`python -m app.scan` to populate verdicts."
        )
        return

    dates = storage.list_dates()
    if not dates:
        st.info(
            "No scans found yet. Run a scan to populate the leaderboard:\n\n"
            "```\nLOCAL_RESULTS_DIR=./out python -m app.scan\n```"
        )
        return

    date = st.selectbox("Scan date", ["latest"] + sorted(dates, reverse=True), index=0)
    payload = storage.get_index(date)
    if not payload:
        st.warning(f"No index.json for date={date}. Try a different date.")
        return

    ranked = payload.get("ranked", [])
    st.caption(
        f"Generated {payload.get('generated_at','?')}  ·  {len(ranked)} tickers ranked by `net_bull_score`."
    )

    if not ranked:
        st.info("Index is empty.")
        return

    # Top N table
    top_n = st.slider("Show top N (by net bull score)", 5, max(5, len(ranked)), min(20, len(ranked)))
    top = ranked[:top_n]
    table = [
        {
            "Rank": i + 1,
            "Ticker": r["ticker"],
            "Company": r.get("company", r["ticker"]),
            "Verdict": r.get("verdict", ""),
            "Net Bull": round(r.get("net_bull_score", 0.0), 3),
            "Bull w": round(r.get("weights", {}).get("bull", 0.0), 3),
            "Bear w": round(r.get("weights", {}).get("bear", 0.0), 3),
            "Neutral w": round(r.get("weights", {}).get("neutral", 0.0), 3),
            "As of": r.get("as_of", ""),
        }
        for i, r in enumerate(top)
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)

    # Per-ticker drill-down
    st.markdown("---")
    pick = st.selectbox("Inspect a ticker", [r["ticker"] for r in ranked])
    if pick:
        details = storage.get_verdict(date if date != "latest" else payload.get("date", ""), pick)
        if not details:
            st.warning(f"No detail JSON for {pick} on date={date}.")
            return
        snap = details.get("snapshot", {})
        verdict = details.get("verdict", {})
        args = details.get("arguments", {})
        st.markdown(f"### {snap.get('company', pick)} ({pick})")
        # Reuse the 3-bars renderer.
        render_verdict(st.container(), verdict, args)
        with st.expander("Full debate transcript"):
            for ev in details.get("transcript", []):
                render_argument(st.container(), ev)


# --------------------------------------------------------------------------- #
# Access gate (optional)                                                      #
# --------------------------------------------------------------------------- #
def check_password() -> bool:
    """Gate the app when APP_PASSWORD is set (protects paid Azure calls on a public host).

    No password configured (e.g. local dev) → no gate.
    """
    expected = os.getenv("APP_PASSWORD", "").strip()
    if not expected or st.session_state.get("_authed"):
        return True
    st.warning(
        "🔒 This hosted demo makes real (paid) Azure model calls. "
        "Enter the access password to run debates."
    )
    pw = st.text_input("Access password", type="password")
    if pw and pw == expected:
        st.session_state["_authed"] = True
        return True
    if pw:
        st.error("Incorrect password.")
    return False


# --------------------------------------------------------------------------- #
# Single-debate tab                                                           #
# --------------------------------------------------------------------------- #
def _ticker_options() -> list[str]:
    """Prefer the watchlist; fall back to DEFAULT_TICKERS if the file is unreadable."""
    try:
        return universe.load_tickers()
    except Exception:
        return config.DEFAULT_TICKERS


def render_single_debate() -> None:
    with st.sidebar:
        st.header("Run a debate")
        options = _ticker_options()
        ticker_choice = st.selectbox(
            "Watchlist ticker", options, index=0 if options else None
        )
        custom = st.text_input("…or any US ticker", placeholder="e.g. AAPL, TSLA, NVDA")
        ticker = (custom.strip() or ticker_choice or "AAPL").upper()

        rounds = st.slider(
            "Debate rounds",
            1,
            3,
            value=min(3, max(1, config.DEBATE_ROUNDS)),
            help="3 = opening case + rebuttal + closing argument.",
        )
        demo = st.toggle(
            "Demo mode (offline mock)",
            value=config.MOCK_MODE,
            help="Run the full pipeline from deterministic stubs — no network/Azure.",
        )

        backend = (
            "MOCK"
            if (demo or config.llm_backend() == "none")
            else config.llm_backend().upper()
        )
        persona_model = config.PERSONA_R1_DEPLOYMENT or config.PERSONA_DEPLOYMENT
        st.caption(
            f"Backend: **{backend}**  ·  Chair: `{config.CHAT_DEPLOYMENT}`  ·  "
            f"Personas: `{persona_model}`"
        )
        run = st.button("▶  Run Debate", type="primary", use_container_width=True)

    if not run:
        st.info(
            "Pick a ticker in the sidebar and hit **Run Debate** to watch the committee argue."
        )
        return

    # Apply sidebar choices (orchestrator/llm read these at call time).
    config.MOCK_MODE = demo
    config.DEBATE_ROUNDS = rounds

    snapshot_box = st.container()
    st.divider()
    st.subheader("🗣️ The Debate")
    transcript_box = st.container()
    verdict_box = st.container()

    try:
        with st.spinner(
            f"Fetching prices, news, and filings for {ticker} and convening the committee…"
        ):
            for ev in stream_debate(ticker):
                if ev["type"] == "data":
                    render_snapshot(
                        snapshot_box,
                        ev["snapshot"],
                        ev["news"],
                        ev.get("filings", []),
                    )
                elif ev["type"] == "argument":
                    render_argument(transcript_box, ev)
                elif ev["type"] == "verdict":
                    with verdict_box:
                        st.divider()
                    render_verdict(verdict_box, ev["verdict"], ev["arguments"])
    except Exception as exc:  # keep the demo alive if data/Azure hiccups
        st.error(f"Debate failed for **{ticker}**: {exc}")
        st.info(
            "Try **Demo mode (offline mock)** in the sidebar to run without network/Azure."
        )


# --------------------------------------------------------------------------- #
# App                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(
        page_title="MarketDebater Swarm", page_icon="⚖️", layout="wide"
    )
    st.title("⚖️ MarketDebater Swarm")
    st.caption(
        "An AI investment committee for US stocks: three rival analysts debate "
        "(bull / bear / risk), a Chair grades them on **data grounding** and "
        "confidence, then issues a transparent verdict. Inputs: live prices, "
        "Grok news, and SEC filings (10-K / 10-Q / 8-K)."
    )

    if not check_password():
        st.stop()

    tab_debate, tab_board = st.tabs(["🗣️ Single Debate", "🏆 Leaderboard"])
    with tab_debate:
        render_single_debate()
    with tab_board:
        render_leaderboard()


if __name__ == "__main__":
    main()
