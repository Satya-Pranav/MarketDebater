"""MarketDebater Swarm — Streamlit UI (Phase 3).

Live debate transcript + graded verdict card over the orchestrator's event stream.

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

from app import config
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
def render_snapshot(container, snapshot: dict, news: list[dict]) -> None:
    with container:
        st.subheader(f"📊 {snapshot.get('company', snapshot['ticker'])}  ·  as of {snapshot['as_of']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            f"Price ({snapshot.get('currency', 'INR')})",
            snapshot["price"],
            f"{snapshot['change_pct']:+}%",
        )
        c2.metric("RSI (14)", snapshot["rsi_14"])
        c3.metric("SMA 50 / 200", f"{snapshot['sma_50']} / {snapshot['sma_200']}")
        c4.metric("52w range", f"{snapshot['week52_low']} – {snapshot['week52_high']}")
        if news:
            with st.expander(f"📰 {len(news)} news headlines fed to the committee"):
                for n in news:
                    title = n.get("url") and f"[{n['title']}]({n['url']})" or n["title"]
                    st.markdown(f"- {title}  ·  *{n.get('source', '')}*")


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
        st.markdown(
            f"<div style='background:{color};color:white;padding:1rem 1.5rem;"
            f"border-radius:10px;text-align:center;font-size:1.8rem;font-weight:800;"
            f"letter-spacing:.5px'>VERDICT — {v}</div>",
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
                st.progress(min(grounding, 1.0), text=f"Grounding {grounding:.0%}")
                st.progress(min(confidence, 1.0), text=f"Confidence {confidence:.0%}")
                st.caption(f"Final weight: **{weight}**")
                flagged = grading.get("unverified_metrics") or []
                if flagged:
                    st.caption("🚩 Unverified: " + ", ".join(f"`{m}`" for m in flagged))

        st.write("")
        st.info(DISCLAIMER, icon="⚠️")


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
    st.warning("🔒 This hosted demo makes real (paid) Azure model calls. Enter the access password to run debates.")
    pw = st.text_input("Access password", type="password")
    if pw and pw == expected:
        st.session_state["_authed"] = True
        return True
    if pw:
        st.error("Incorrect password.")
    return False


# --------------------------------------------------------------------------- #
# App                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title="MarketDebater Swarm", page_icon="⚖️", layout="wide")
    st.title("⚖️ MarketDebater Swarm")
    st.caption(
        "An AI investment committee: three rival analysts debate, a Chair grades them on "
        "**data grounding** and confidence, then issues a transparent verdict."
    )

    if not check_password():
        st.stop()

    with st.sidebar:
        st.header("Run a debate")
        ticker_choice = st.selectbox("Nifty-50 ticker", config.DEFAULT_TICKERS, index=0)
        custom = st.text_input("…or a custom NSE ticker", placeholder="e.g. WIPRO.NS")
        ticker = (custom.strip() or ticker_choice).upper()

        rounds = st.slider("Debate rounds", 1, 2, value=config.DEBATE_ROUNDS,
                           help="2 = opening case + one rebuttal.")
        demo = st.toggle("Demo mode (offline mock)", value=config.MOCK_MODE,
                         help="Run the full pipeline from deterministic stubs — no network/Azure.")

        backend = "MOCK" if (demo or config.llm_backend() == "none") else config.llm_backend().upper()
        st.caption(f"LLM backend: **{backend}**  ·  model: `{config.CHAT_DEPLOYMENT}`")
        run = st.button("▶  Run Debate", type="primary", use_container_width=True)

    if not run:
        st.info("Pick a ticker in the sidebar and hit **Run Debate** to watch the committee argue.")
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
        with st.spinner(f"Fetching data and convening the committee for {ticker}…"):
            for ev in stream_debate(ticker):
                if ev["type"] == "data":
                    render_snapshot(snapshot_box, ev["snapshot"], ev["news"])
                elif ev["type"] == "argument":
                    render_argument(transcript_box, ev)
                elif ev["type"] == "verdict":
                    with verdict_box:
                        st.divider()
                    render_verdict(verdict_box, ev["verdict"], ev["arguments"])
    except Exception as exc:  # keep the demo alive if data/Azure hiccups
        st.error(f"Debate failed for **{ticker}**: {exc}")
        st.info("Try **Demo mode (offline mock)** in the sidebar to run without network/Azure.")


if __name__ == "__main__":
    main()
