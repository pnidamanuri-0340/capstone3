"""Streamlit front end. Launch with `finlit ui` (or `streamlit run src/finlit/ui/app.py`)."""

from __future__ import annotations

import uuid

import pandas as pd
import plotly.express as px
import streamlit as st
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from finlit import DISCLAIMER
from finlit.agents.registry import AGENTS
from finlit.agents.specialist import text_of
from finlit.config import get_settings
from finlit.logging_setup import setup_logging
from finlit.memory.profiles import LEVELS, RISK, get_store

st.set_page_config(page_title="FinLit · Financial Literacy Agents", page_icon="💡", layout="wide")
settings = get_settings()
setup_logging(settings.log_level)

EXAMPLES = [
    "What is an index fund?",
    "Analyze my saved portfolio",
    "Compare AAPL, MSFT and NVDA",
    "How much should I save monthly for $30,000 in 4 years?",
    "Summarize recent news about the Federal Reserve",
    "Roth vs traditional IRA?",
]


# ------------------------------------------------------------ resources
@st.cache_resource(show_spinner="Preparing knowledge base (first run only)...")
def ensure_knowledge_base() -> dict:
    from finlit.rag.store import collection_counts, ingest_all

    counts = collection_counts()
    if any(v == 0 for v in counts.values()):
        counts = ingest_all()
    return counts


@st.cache_resource
def graph_app():
    from finlit.graph.builder import get_app

    return get_app()


def thread_config() -> dict:
    return {"configurable": {"thread_id": f"{st.session_state.user_id}:{st.session_state.thread_id}"}}


# --------------------------------------------------------------- state
if "user_id" not in st.session_state:
    st.session_state.user_id = "me"
if "thread_id" not in st.session_state:
    st.session_state.thread_id = uuid.uuid4().hex[:8]

try:
    kb_counts = ensure_knowledge_base()
    kb_error = None
except Exception as exc:  # noqa: BLE001
    kb_counts, kb_error = {}, str(exc)

store = get_store()

# --------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("👤 Your profile")
    uid = st.text_input("Profile name / ID", value=st.session_state.user_id,
                        help="Profiles and conversations are stored locally per ID.").strip() or "me"
    if uid != st.session_state.user_id:
        st.session_state.user_id = uid
        st.session_state.thread_id = uuid.uuid4().hex[:8]
        st.rerun()
    profile = store.get(st.session_state.user_id)

    with st.form("profile"):
        name = st.text_input("Display name", profile.name)
        age = st.number_input("Age", min_value=0, max_value=120, value=profile.age or 0, step=1)
        risk = st.selectbox("Risk tolerance", RISK, index=RISK.index(profile.risk_tolerance))
        level = st.selectbox("Knowledge level", LEVELS, index=LEVELS.index(profile.knowledge_level),
                             help="Advances automatically as you explore more topics.")
        goals = st.text_area("Financial goals", profile.goals, height=80,
                             placeholder="e.g. emergency fund by June, house in 5 years")
        watch = st.text_input("Watchlist (comma-separated tickers)", ", ".join(profile.watchlist))
        if st.form_submit_button("Save profile", width="stretch"):
            profile.name, profile.age = name, int(age) or None
            profile.risk_tolerance, profile.knowledge_level, profile.goals = risk, level, goals
            profile.watchlist = [t.strip().upper() for t in watch.split(",") if t.strip()][:20]
            store.save(profile)
            st.success("Profile saved")

    st.caption(f"Questions asked: {profile.interactions} · Topics explored: {len(profile.topics_seen)}")
    if st.button("🆕 New conversation", width="stretch"):
        st.session_state.thread_id = uuid.uuid4().hex[:8]
        st.rerun()

    st.divider()
    st.subheader("⚙️ Status")
    st.markdown(("✅" if settings.has_llm else "❌")
                + f" AI: {settings.provider_label} (`{settings.model_for('agent')}`)")
    st.markdown(("🟡 Sample market data (mock)" if settings.use_mock_market_data
                 else "✅ Live Alpha Vantage data"))
    st.markdown(("✅ Knowledge base: " + f"{sum(kb_counts.values())} chunks") if not kb_error
                else f"❌ Knowledge base: {kb_error}")

# ----------------------------------------------------------------- main
st.title("💡 FinLit — your financial literacy team")
st.caption("Six specialist AI agents grounded in a curated knowledge base. " + DISCLAIMER)

if not settings.has_llm:
    st.warning("**No AI key is set.** Add `OPENAI_API_KEY`, `GOOGLE_API_KEY` (free at aistudio.google.com) or "
               "`ANTHROPIC_API_KEY` to the `.env` file in the app folder, save it and refresh this page. "
               "The Portfolio and Markets tabs still work without it.", icon="🔑")

chat_tab, portfolio_tab, market_tab, about_tab = st.tabs(["💬 Chat", "📊 Portfolio", "📈 Markets", "ℹ️ Agents"])


def render_badge(meta: dict) -> None:
    if not meta:
        return
    info = AGENTS.get(meta.get("agent", ""))
    label = f"{info.icon} {info.name}" if info else meta.get("agent_name", "")
    extra = f" · routing confidence {meta.get('confidence', 0):.0%}" if info else ""
    tools = meta.get("tool_calls") or []
    if tools:
        extra += " · tools: " + ", ".join(sorted(set(tools)))
    st.caption(f"**{label}**{extra}")


with chat_tab:
    history = []
    try:
        snap = graph_app().get_state(thread_config())
        history = snap.values.get("messages", []) if snap and snap.values else []
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load conversation history: {exc}")

    if not history:
        st.markdown("**Try asking:**")
        cols = st.columns(3)
        for i, ex in enumerate(EXAMPLES):
            if cols[i % 3].button(ex, key=f"ex{i}", width="stretch"):
                st.session_state.pending = ex

    for idx, m in enumerate(history):
        if isinstance(m, HumanMessage):
            with st.chat_message("user"):
                st.markdown(text_of(m))
        elif isinstance(m, AIMessage):
            with st.chat_message("assistant", avatar="💡"):
                render_badge(m.additional_kwargs.get("finlit", {}))
                st.markdown(text_of(m))
                if idx == len(history) - 1 and st.session_state.get("last_retrieved"):
                    with st.expander("📚 Retrieved knowledge for this answer"):
                        for i, h in enumerate(st.session_state.last_retrieved, 1):
                            st.markdown(f"**[{i}] {h['section']}** · `{h['source']}` · score {h['score']}")
                            st.caption(h["text"][:400] + ("..." if len(h["text"]) > 400 else ""))

    prompt = st.chat_input("Ask about budgeting, investing, markets, goals or taxes...",
                           disabled=not settings.has_llm or bool(kb_error))
    prompt = prompt or st.session_state.pop("pending", None)

    if prompt and settings.has_llm:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="💡"):
            badge = st.empty()
            body = st.empty()
            streamed, final = "", None
            try:
                with st.spinner("Routing your question..."):
                    stream = graph_app().stream(
                        {"messages": [HumanMessage(prompt)], "user_id": st.session_state.user_id},
                        thread_config(), stream_mode=["messages", "values"])
                    for mode, payload in stream:
                        if mode == "values":
                            final = payload
                            if payload.get("route") in AGENTS and not streamed:
                                info = AGENTS[payload["route"]]
                                badge.caption(f"**{info.icon} {info.name}** is answering...")
                        elif mode == "messages":
                            chunk, meta = payload
                            if (isinstance(chunk, AIMessageChunk)
                                    and str(meta.get("langgraph_node", "")).startswith("agent_")):
                                streamed += text_of(chunk)
                                body.markdown(streamed + "▌")
            except Exception as exc:  # noqa: BLE001
                body.error(f"Something went wrong: {exc}")
            if final and final.get("messages"):
                last = final["messages"][-1]
                with badge.container():
                    render_badge(last.additional_kwargs.get("finlit", {}))
                body.markdown(text_of(last))
                st.session_state.last_retrieved = final.get("retrieved") or []
        st.rerun()

# ------------------------------------------------------------ portfolio
with portfolio_tab:
    from finlit.tools.services import analyze_portfolio

    st.subheader("Your holdings")
    st.caption("Saved holdings are also used by the Portfolio Analysis agent. "
               "Leave price blank to use the latest quote.")
    df = pd.DataFrame(profile.holdings or [], columns=["symbol", "quantity", "price", "asset_class"])
    edited = st.data_editor(
        df, num_rows="dynamic", width="stretch", key="holdings_editor",
        column_config={
            "symbol": st.column_config.TextColumn("Symbol", required=True),
            "quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, required=True),
            "price": st.column_config.NumberColumn("Price (optional)", min_value=0.0),
            "asset_class": st.column_config.SelectboxColumn(
                "Asset class", options=["equity", "bond", "cash", "real_estate", "commodity", "crypto"],
                default="equity"),
        })
    c1, c2 = st.columns(2)
    if c1.button("💾 Save holdings", width="stretch"):
        rows = []
        for r in edited.to_dict("records"):
            if r.get("symbol") and r.get("quantity"):
                price = r.get("price")
                rows.append({"symbol": str(r["symbol"]).upper().strip(), "quantity": float(r["quantity"]),
                             "price": None if pd.isna(price) else float(price),
                             "asset_class": r.get("asset_class") or "equity"})
        profile.holdings = rows
        store.save(profile)
        st.success(f"Saved {len(rows)} holdings")
    if c2.button("📊 Analyze", width="stretch", disabled=not profile.holdings):
        with st.spinner("Fetching prices and computing metrics..."):
            st.session_state.analysis = analyze_portfolio(profile.holdings)

    res = st.session_state.get("analysis")
    if res:
        if res.get("error"):
            st.error(res["error"])
        else:
            st.caption(f"Data source: {res.get('data_source')}")
            m = st.columns(4)
            m[0].metric("Total value", f"${res['total_value']:,.2f}")
            perf = res.get("performance") or {}
            if perf:
                m[1].metric("Period return", f"{perf['total_return']:.1%}", help=f"{perf['period_days']} trading days")
                m[2].metric("Volatility (ann.)", f"{perf['annualized_volatility']:.1%}")
                m[3].metric("Sharpe ratio", f"{perf['sharpe_ratio']:.2f}",
                            help=f"Max drawdown {perf['max_drawdown']:.1%}")
            p1, p2 = st.columns(2)
            p1.plotly_chart(px.pie(names=list(res["by_symbol"]), values=list(res["by_symbol"].values()),
                                   title="By symbol", hole=0.4), width="stretch")
            p2.plotly_chart(px.pie(names=list(res["by_asset_class"]),
                                   values=list(res["by_asset_class"].values()),
                                   title="By asset class", hole=0.4), width="stretch")
        for w in res.get("warnings", []):
            st.warning(w)

# --------------------------------------------------------------- markets
with market_tab:
    from finlit.tools.services import stock_quotes

    st.subheader("Quotes")
    default = ", ".join(profile.watchlist) if profile.watchlist else "AAPL, MSFT, NVDA"
    tickers = st.text_input("Tickers (comma-separated, up to 10)", default)
    if st.button("Get quotes"):
        with st.spinner("Fetching quotes..."):
            st.session_state.quotes = stock_quotes([t for t in tickers.split(",") if t.strip()])
    q = st.session_state.get("quotes")
    if q:
        if q["quotes"]:
            qdf = pd.DataFrame(q["quotes"])[["symbol", "price", "change", "change_percent", "volume",
                                             "latest_trading_day", "source"]]
            st.dataframe(qdf, width="stretch", hide_index=True)
        for e in q["errors"]:
            st.warning(f"{e['symbol']}: {e['error']}")
    if settings.use_mock_market_data:
        st.info("Showing **sample data** (no ALPHA_VANTAGE_API_KEY or mock mode on). Prices are not real.")

# ----------------------------------------------------------------- about
with about_tab:
    st.subheader("Meet the agents")
    cols = st.columns(3)
    for i, a in enumerate(AGENTS.values()):
        with cols[i % 3].container(border=True):
            st.markdown(f"### {a.icon} {a.name}")
            st.write(a.description)
            if kb_counts:
                st.caption(f"{kb_counts.get(a.key, 0)} knowledge chunks")
    st.markdown("A router reads each question (and recent conversation) and sends it to the best agent. "
                "Each agent retrieves from its own vector store, can call finance tools, and adapts to "
                "your profile's knowledge level, which rises as you explore more topics.")
