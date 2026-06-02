"""
AI Support Agent — Streamlit Demo
Deploy free at share.streamlit.io

Reuses the same backend modules (scraper, vector_store, chat_engine)
as the full FastAPI version. Perfect for demos and client pitching.
"""

import os
import sys
import asyncio
import uuid
import concurrent.futures
from pathlib import Path
from datetime import datetime

import streamlit as st

# ── Make backend modules importable ───────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# ── Load API key: Streamlit secrets → env var → user input ────────────────────
try:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass  # Will fall back to env var or ask the user below

# ── Page config (must be first Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title="AI Support Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help":    "https://github.com/devmohsin/wordpress-ai-support-agent",
        "Report a bug":"https://github.com/devmohsin/wordpress-ai-support-agent/issues",
        "About":       "AI Support Agent by Mohsin — github.com/devmohsin",
    },
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Gradient title */
  .hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6C63FF, #FF6B6B);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.2;
    margin-bottom: 4px;
  }
  /* Metric cards */
  div[data-testid="metric-container"] {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
  }
  /* Source pill tags */
  .source-tag {
    display: inline-block;
    background: rgba(108,99,255,.1);
    color: #6C63FF;
    padding: 3px 10px;
    border-radius: 100px;
    font-size: 12px;
    font-weight: 600;
    text-decoration: none;
    margin-right: 4px;
    margin-top: 4px;
  }
  /* Code snippet box */
  .embed-snippet {
    background: #1E1E2E;
    color: #A6ACCD;
    border-radius: 10px;
    padding: 18px;
    font-family: 'Fira Code', monospace;
    font-size: 13px;
    overflow-x: auto;
    white-space: pre;
  }
  /* Step cards on welcome screen */
  .step-card {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 24px;
    height: 100%;
    text-align: center;
  }
  .step-num {
    background: linear-gradient(135deg, #6C63FF, #4B44CC);
    color: white;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    font-weight: 700;
    font-size: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 12px;
  }
  /* Hide default footer */
  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Session state defaults ─────────────────────────────────────────────────────
_defaults = {
    "messages":           [],
    "session_id":         str(uuid.uuid4()),
    "active_agent_id":    None,
    "active_agent_name":  "Support Agent",
    "indexed_agents":     {},   # agent_id → {name, pages, url, indexed_at}
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Cached backend singletons (survive Streamlit reruns) ──────────────────────
@st.cache_resource(show_spinner=False)
def _load_services():
    from vector_store import VectorStore
    from chat_engine  import ChatEngine
    db_path = str(Path(__file__).parent / "chroma_db")
    vs = VectorStore(persist_path=db_path)
    return vs, ChatEngine(vs)

vector_store, chat_engine = _load_services()


# ── Async helper: run coroutines safely from Streamlit's sync context ──────────
def run_async(coro):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, coro).result()


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ AI Support Agent")
    st.caption("by [devmohsin](https://github.com/devmohsin/wordpress-ai-support-agent)")
    st.divider()

    # ── API key input (if not already set via secrets / env) ─────────────────
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.markdown("#### 🔑 API Key Required")
        key_input = st.text_input(
            "Anthropic API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Get your key at console.anthropic.com",
        )
        if key_input:
            os.environ["ANTHROPIC_API_KEY"] = key_input
            st.success("Key saved for this session!")
        st.caption("[Get a free API key →](https://console.anthropic.com)")
        st.divider()

    # ── Index new docs ────────────────────────────────────────────────────────
    st.markdown("### 🚀 Setup Your Agent")

    with st.form("setup_form", clear_on_submit=False):
        product_name = st.text_input(
            "Product / Plugin Name",
            placeholder="e.g. Astra Theme",
        )
        docs_url = st.text_input(
            "Documentation URL",
            placeholder="https://docs.yourplugin.com",
        )
        max_pages = st.slider("Max pages to crawl", min_value=5, max_value=50, value=20, step=5)
        go = st.form_submit_button("🔍 Index Documentation", use_container_width=True, type="primary")

    if go:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            st.error("Please enter your API key first.")
        elif not product_name or not docs_url:
            st.warning("Please fill in both fields.")
        else:
            agent_id = product_name.lower().strip().replace(" ", "-")

            progress = st.progress(0, text="Starting crawler…")
            try:
                from scraper import DocScraper
                scraper = DocScraper()

                progress.progress(15, text=f"Crawling {docs_url} …")
                docs = run_async(scraper.scrape(docs_url, max_pages=max_pages))

                progress.progress(60, text=f"Indexing {len(docs)} pages…")
                vector_store.add_documents(docs, agent_id, product_name)

                progress.progress(100, text="Done!")

                st.session_state.indexed_agents[agent_id] = {
                    "name":       product_name,
                    "pages":      len(docs),
                    "url":        docs_url,
                    "indexed_at": datetime.now().strftime("%d %b %Y %H:%M"),
                }
                st.session_state.active_agent_id   = agent_id
                st.session_state.active_agent_name = product_name
                st.session_state.messages          = []   # fresh chat for new agent
                st.session_state.session_id        = str(uuid.uuid4())

                st.success(f"✅ {len(docs)} pages indexed! Switch to the Chat tab.")

            except Exception as exc:
                progress.empty()
                st.error(f"Something went wrong: {exc}")

    # ── Switch between indexed agents ─────────────────────────────────────────
    if st.session_state.indexed_agents:
        st.divider()
        st.markdown("### 🤖 Indexed Agents")
        for aid, info in st.session_state.indexed_agents.items():
            is_active = st.session_state.active_agent_id == aid
            label = f"{'✅' if is_active else '○'} {info['name']}"
            cols = st.columns([3, 1])
            cols[0].caption(f"**{label}**\n\n{info['pages']} pages · {info['indexed_at']}")
            if cols[1].button("Use", key=f"switch_{aid}", use_container_width=True):
                st.session_state.active_agent_id   = aid
                st.session_state.active_agent_name = info["name"]
                st.session_state.messages          = []
                st.session_state.session_id        = str(uuid.uuid4())
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN AREA
# ─────────────────────────────────────────────────────────────────────────────

# Hero header
st.markdown('<div class="hero-title">AI Support Agent</div>', unsafe_allow_html=True)
st.caption("Trained on your product docs · Answers instantly · Escalates when needed")
st.divider()

# Three tabs
tab_chat, tab_embed, tab_about = st.tabs(["💬 Chat", "🔗 Embed Widget", "ℹ️ About"])


# ═══════════════════════════ TAB 1: CHAT ══════════════════════════════════════
with tab_chat:

    # ── No agent indexed yet ─────────────────────────────────────────────────
    if not st.session_state.active_agent_id:
        st.markdown("#### 👈 Set up your agent in the sidebar to start chatting")
        st.markdown("")

        c1, c2, c3 = st.columns(3)
        for col, num, icon, title, desc in [
            (c1, "1", "🔗", "Paste your docs URL",
             "Enter your product name and documentation URL in the sidebar."),
            (c2, "2", "🧠", "Agent indexes in 2 min",
             "Crawls all pages and builds a searchable knowledge base automatically."),
            (c3, "3", "💬", "Chat with your product",
             "Ask any question — the agent answers only from your product's documentation."),
        ]:
            with col:
                st.markdown(f"""
                <div class="step-card">
                  <div class="step-num">{num}</div>
                  <h4>{icon} {title}</h4>
                  <p style="color:#6B7280;font-size:14px">{desc}</p>
                </div>""", unsafe_allow_html=True)

    # ── Active agent — chat interface ─────────────────────────────────────────
    else:
        agent_info = st.session_state.indexed_agents.get(st.session_state.active_agent_id, {})

        # Stats strip
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🤖 Agent",          st.session_state.active_agent_name)
        m2.metric("📄 Pages Indexed",  agent_info.get("pages", "—"))
        m3.metric("💬 Messages",       len(st.session_state.messages))
        m4.metric("📅 Indexed",        agent_info.get("indexed_at", "—"))

        st.markdown("")

        # Render existing conversation history
        for msg in st.session_state.messages:
            avatar = "🧑" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

                if msg["role"] == "assistant":
                    if msg.get("sources"):
                        links = "".join(
                            f'<a class="source-tag" href="{s}" target="_blank">🔗 Source</a>'
                            for s in msg["sources"]
                        )
                        st.markdown(links, unsafe_allow_html=True)
                    if msg.get("escalate"):
                        st.warning("⚠️ This topic may need a human agent — please contact support directly.")

        # Chat input
        user_input = st.chat_input(
            f"Ask about {st.session_state.active_agent_name}…",
            disabled=not os.environ.get("ANTHROPIC_API_KEY"),
        )

        if user_input:
            # Show user bubble immediately
            with st.chat_message("user", avatar="🧑"):
                st.markdown(user_input)
            st.session_state.messages.append({"role": "user", "content": user_input})

            # Stream / generate response
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Searching your docs…"):
                    try:
                        response = run_async(chat_engine.get_response(
                            message=user_input,
                            agent_id=st.session_state.active_agent_id,
                            session_id=st.session_state.session_id,
                            history=st.session_state.messages[:-1],
                            product_name=st.session_state.active_agent_name,
                        ))

                        st.markdown(response["answer"])

                        if response.get("sources"):
                            links = "".join(
                                f'<a class="source-tag" href="{s}" target="_blank">🔗 Source</a>'
                                for s in response["sources"]
                            )
                            st.markdown(links, unsafe_allow_html=True)

                        if response.get("escalate"):
                            st.warning("⚠️ This topic may need a human agent — please contact support directly.")

                        st.session_state.messages.append({
                            "role":    "assistant",
                            "content": response["answer"],
                            "sources": response.get("sources", []),
                            "escalate":response.get("escalate", False),
                        })

                    except Exception as exc:
                        err = "I'm having trouble connecting right now. Please check your API key and try again."
                        st.error(err)
                        st.session_state.messages.append({"role": "assistant", "content": err})

        # Clear chat
        if st.session_state.messages:
            st.markdown("")
            if st.button("🗑️ Clear conversation"):
                st.session_state.messages    = []
                st.session_state.session_id  = str(uuid.uuid4())
                st.rerun()


# ═══════════════════════════ TAB 2: EMBED WIDGET ══════════════════════════════
with tab_embed:
    st.markdown("### 🔗 Embed the Chat Widget on Your WordPress Site")
    st.caption("The full FastAPI version adds a floating chat bubble to any website with one script tag.")

    if st.session_state.active_agent_id:
        server_url = st.text_input(
            "Your deployed server URL",
            value="https://your-app.up.railway.app",
            help="The URL of your deployed FastAPI backend",
        )
        agent_id   = st.session_state.active_agent_id
        pname      = st.session_state.active_agent_name

        snippet = (
            f"<!-- Paste before </body> in your WordPress theme (footer.php) -->\n"
            f"<script>\n"
            f"  window.AISupportConfig = {{\n"
            f'    agentId:   "{agent_id}",\n'
            f'    agentName: "{pname} Support",\n'
            f'    apiBase:   "{server_url}"\n'
            f"  }};\n"
            f"</script>\n"
            f'<script src="{server_url}/js/widget.js"></script>'
        )

        st.code(snippet, language="html")
        st.success("✅ Paste this into WordPress → Appearance → Theme Editor → footer.php, or use the **Insert Headers and Footers** plugin.")

    else:
        st.info("👈 Index your docs first (sidebar) to generate your embed snippet.")

    st.divider()
    st.markdown("**Prefer a WordPress plugin?** Use [Insert Headers and Footers](https://wordpress.org/plugins/insert-headers-and-footers/) — paste the snippet in the Footer section. No coding needed.")


# ═══════════════════════════ TAB 3: ABOUT ═════════════════════════════════════
with tab_about:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### What this agent does")
        st.markdown("""
- 🔍 **Crawls** your documentation website automatically
- 🧠 **Indexes** content as vector embeddings using ChromaDB
- 💬 **Answers** user questions using only your product docs (Claude AI + RAG)
- ⚠️ **Flags** billing, refund & angry-user conversations for human review
- 🔗 **Embeds** on any WordPress or SaaS site with one `<script>` tag
- 📊 **Dashboard** shows all conversations, stats, and escalations
        """)

    with col2:
        st.markdown("### Tech stack")
        st.table({
            "Layer":    ["AI Model",     "Vector DB", "Scraper",             "Demo UI",   "Production API"],
            "Tech":     ["Claude (Anthropic)", "ChromaDB", "aiohttp + BeautifulSoup", "Streamlit", "FastAPI"],
        })

    st.divider()

    st.markdown("""
    ### Earning with this agent
    | Model | Price | Notes |
    |---|---|---|
    | Starter client | \$199/mo | 1 product, 50 pages |
    | Growth client  | \$499/mo | 5 products, 200 pages each |
    | Agency / reseller | \$999/mo | Unlimited, white-label |

    > 📌 **This Streamlit app** is your free demo tool — show clients a live working agent
    > before they sign up. The full FastAPI version is what you deploy for paying clients.
    """)

    st.divider()
    st.markdown("Built by **Mohsin** · [github.com/devmohsin](https://github.com/devmohsin/wordpress-ai-support-agent)")
