"""
AI Support Agent — Streamlit Demo
Deploy free at share.streamlit.io
"""

import os
import sys
import uuid
from pathlib import Path
from datetime import datetime

import streamlit as st

# ── 1. Page config MUST be the very first Streamlit call ──────────────────────
st.set_page_config(
    page_title="AI Support Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help":     "https://github.com/devmohsin/wordpress-ai-support-agent",
        "Report a bug": "https://github.com/devmohsin/wordpress-ai-support-agent/issues",
        "About":        "AI Support Agent by Mohsin — github.com/devmohsin",
    },
)

# ── 2. Backend path ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# ── 3. API key — stored in session_state so it survives reruns ────────────────
#    Priority: Streamlit Cloud secrets → env var → user typed in sidebar
if "api_key" not in st.session_state:
    loaded = ""
    try:                          # Streamlit Cloud secrets
        loaded = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    if not loaded:                # Local env variable
        loaded = os.environ.get("ANTHROPIC_API_KEY", "")
    st.session_state.api_key = loaded

# Always keep os.environ in sync with session_state
if st.session_state.api_key:
    os.environ["ANTHROPIC_API_KEY"] = st.session_state.api_key

# ── 4. Session state defaults ─────────────────────────────────────────────────
for key, default in {
    "messages":          [],
    "session_id":        str(uuid.uuid4()),
    "active_agent_id":   None,
    "active_agent_name": "Support Agent",
    "indexed_agents":    {},
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── 5. Cached backend services ────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_vector_store():
    from streamlit_vector_store import StreamlitVectorStore
    return StreamlitVectorStore(persist_path=str(Path(__file__).parent / "vector_data"))

@st.cache_resource(show_spinner=False)
def load_chat_engine(_vs):          # underscore prefix → Streamlit won't hash it
    from streamlit_chat_engine import StreamlitChatEngine
    return StreamlitChatEngine(_vs)

try:
    vector_store = load_vector_store()
    chat_engine  = load_chat_engine(vector_store)
    _services_ok = True
except Exception as _e:
    _services_ok = False
    _services_error = str(_e)

# ── 6. Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .hero-title {
    font-size: 2.4rem; font-weight: 800;
    background: linear-gradient(135deg, #6C63FF, #FF6B6B);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  div[data-testid="metric-container"] {
    background: white; border: 1px solid #E5E7EB;
    border-radius: 12px; padding: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
  }
  .source-tag {
    display: inline-block; background: rgba(108,99,255,.1);
    color: #6C63FF; padding: 3px 10px; border-radius: 100px;
    font-size: 12px; font-weight: 600; text-decoration: none;
    margin-right: 4px; margin-top: 4px;
  }
  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ AI Support Agent")
    st.caption("by [devmohsin](https://github.com/devmohsin/wordpress-ai-support-agent)")
    st.divider()

    # ── API Key section ───────────────────────────────────────────────────────
    st.markdown("### 🔑 API Key")

    key_input = st.text_input(
        "Anthropic API Key",
        value=st.session_state.api_key,
        type="password",
        placeholder="sk-ant-...",
        help="Get your key at console.anthropic.com",
    )

    # Update session state + env var whenever the field changes
    if key_input != st.session_state.api_key:
        st.session_state.api_key  = key_input
        os.environ["ANTHROPIC_API_KEY"] = key_input

    if st.session_state.api_key:
        st.success("✅ API key is set")
    else:
        st.warning("Enter your key to enable the agent")
        st.caption("[Get a free key →](https://console.anthropic.com)")

    st.divider()

    # ── Index new docs ────────────────────────────────────────────────────────
    st.markdown("### 🚀 Setup Your Agent")

    product_name = st.text_input("Product / Plugin Name", placeholder="e.g. Astra Theme")
    docs_url     = st.text_input("Documentation URL",     placeholder="https://docs.yourplugin.com")
    max_pages    = st.slider("Max pages to crawl", 5, 50, 20, step=5)

    if st.button("🔍 Index Documentation", use_container_width=True, type="primary"):
        if not st.session_state.api_key:
            st.error("Please enter your API key above first.")
        elif not product_name.strip():
            st.error("Please enter a product name.")
        elif not docs_url.strip():
            st.error("Please enter a documentation URL.")
        elif not _services_ok:
            st.error(f"Backend error: {_services_error}")
        else:
            agent_id = product_name.strip().lower().replace(" ", "-")
            bar  = st.progress(0,  text="Starting crawler…")
            try:
                from streamlit_scraper import StreamlitDocScraper
                bar.progress(10, text="Crawling pages…")
                docs = StreamlitDocScraper().scrape(docs_url.strip(), max_pages=max_pages)

                bar.progress(65, text=f"Indexing {len(docs)} pages…")
                vector_store.add_documents(docs, agent_id, product_name.strip())

                bar.progress(100, text="Done!")

                st.session_state.indexed_agents[agent_id] = {
                    "name":       product_name.strip(),
                    "pages":      len(docs),
                    "url":        docs_url.strip(),
                    "indexed_at": datetime.now().strftime("%d %b %Y %H:%M"),
                }
                st.session_state.active_agent_id   = agent_id
                st.session_state.active_agent_name = product_name.strip()
                st.session_state.messages          = []
                st.session_state.session_id        = str(uuid.uuid4())

                st.success(f"✅ {len(docs)} pages indexed! Go to the **Chat** tab.")
                st.balloons()

            except Exception as exc:
                bar.empty()
                st.error(f"Error: {exc}")

    # ── Switch between agents ─────────────────────────────────────────────────
    if st.session_state.indexed_agents:
        st.divider()
        st.markdown("### 🤖 Your Agents")
        for aid, info in st.session_state.indexed_agents.items():
            is_active = st.session_state.active_agent_id == aid
            st.caption(f"{'✅' if is_active else '○'} **{info['name']}** — {info['pages']} pages")
            if not is_active:
                if st.button(f"Switch to {info['name']}", key=f"sw_{aid}", use_container_width=True):
                    st.session_state.active_agent_id   = aid
                    st.session_state.active_agent_name = info["name"]
                    st.session_state.messages          = []
                    st.session_state.session_id        = str(uuid.uuid4())
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN AREA
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="hero-title">AI Support Agent</div>', unsafe_allow_html=True)
st.caption("Trained on your product docs · Answers instantly · Escalates when needed")

# Show service error prominently if backend failed to load
if not _services_ok:
    st.error(f"⚠️ Backend failed to load: {_services_error}")
    st.stop()

st.divider()

tab_chat, tab_embed, tab_about = st.tabs(["💬 Chat", "🔗 Embed Widget", "ℹ️ About"])

# ═══════════════════════════ TAB 1: CHAT ══════════════════════════════════════
with tab_chat:

    # Banner if API key is missing
    if not st.session_state.api_key:
        st.warning("⚠️ **API key required** — enter it in the sidebar to start chatting.")

    # No agent indexed yet
    if not st.session_state.active_agent_id:
        st.info("👈 **Step 1:** Enter your API key in the sidebar.\n\n👈 **Step 2:** Fill in product name + docs URL and click **Index Documentation**.\n\n💬 **Step 3:** Come back here to chat!")

    else:
        # ── Active agent ──────────────────────────────────────────────────────
        info = st.session_state.indexed_agents.get(st.session_state.active_agent_id, {})
        c1, c2, c3 = st.columns(3)
        c1.metric("🤖 Agent",         st.session_state.active_agent_name)
        c2.metric("📄 Pages Indexed", info.get("pages", "—"))
        c3.metric("💬 Messages",      len(st.session_state.messages))
        st.markdown("")

        # Render conversation history
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
                st.markdown(msg["content"])
                if msg["role"] == "assistant":
                    if msg.get("sources"):
                        links = "".join(
                            f'<a class="source-tag" href="{s}" target="_blank">🔗 Source</a>'
                            for s in msg["sources"]
                        )
                        st.markdown(links, unsafe_allow_html=True)
                    if msg.get("escalate"):
                        st.warning("⚠️ This may need a human agent — please contact support directly.")

        # Chat input — always enabled; we handle missing key with a clear message
        user_input = st.chat_input(f"Ask about {st.session_state.active_agent_name}…")

        if user_input:
            if not st.session_state.api_key:
                st.error("Please enter your Anthropic API key in the sidebar first.")
            else:
                with st.chat_message("user", avatar="🧑"):
                    st.markdown(user_input)
                st.session_state.messages.append({"role": "user", "content": user_input})

                with st.chat_message("assistant", avatar="🤖"):
                    with st.spinner("Searching your docs…"):
                        try:
                            # Make sure env var is current before calling Claude
                            os.environ["ANTHROPIC_API_KEY"] = st.session_state.api_key
                            # Reset cached client so it picks up the new key
                            chat_engine._client = None

                            resp = chat_engine.get_response(
                                message=user_input,
                                agent_id=st.session_state.active_agent_id,
                                session_id=st.session_state.session_id,
                                history=st.session_state.messages[:-1],
                                product_name=st.session_state.active_agent_name,
                            )
                            st.markdown(resp["answer"])

                            if resp.get("sources"):
                                links = "".join(
                                    f'<a class="source-tag" href="{s}" target="_blank">🔗 Source</a>'
                                    for s in resp["sources"]
                                )
                                st.markdown(links, unsafe_allow_html=True)

                            if resp.get("escalate"):
                                st.warning("⚠️ This may need a human agent — please contact support directly.")

                            st.session_state.messages.append({
                                "role":    "assistant",
                                "content": resp["answer"],
                                "sources": resp.get("sources", []),
                                "escalate":resp.get("escalate", False),
                            })

                        except Exception as exc:
                            err = f"Error: {exc}"
                            st.error(err)
                            st.session_state.messages.append({"role": "assistant", "content": err})

        # Clear chat button
        if st.session_state.messages:
            if st.button("🗑️ Clear conversation"):
                st.session_state.messages   = []
                st.session_state.session_id = str(uuid.uuid4())
                st.rerun()


# ═══════════════════════════ TAB 2: EMBED WIDGET ══════════════════════════════
with tab_embed:
    st.markdown("### 🔗 Embed the Chat Widget on Your WordPress Site")
    st.caption("The full FastAPI version adds a floating chat bubble to any website with one script tag.")

    if st.session_state.active_agent_id:
        server_url = st.text_input(
            "Your deployed server URL",
            value="https://your-app.up.railway.app",
        )
        snippet = (
            f"<!-- Paste before </body> in your WordPress theme -->\n"
            f"<script>\n"
            f"  window.AISupportConfig = {{\n"
            f'    agentId:   "{st.session_state.active_agent_id}",\n'
            f'    agentName: "{st.session_state.active_agent_name} Support",\n'
            f'    apiBase:   "{server_url}"\n'
            f"  }};\n"
            f"</script>\n"
            f'<script src="{server_url}/js/widget.js"></script>'
        )
        st.code(snippet, language="html")
        st.success("✅ Use the **Insert Headers and Footers** WordPress plugin to paste this in your site footer.")
    else:
        st.info("Index your docs first (sidebar) to generate your embed snippet.")


# ═══════════════════════════ TAB 3: ABOUT ═════════════════════════════════════
with tab_about:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### What this does")
        st.markdown("""
- 🔍 **Crawls** your documentation site automatically
- 🧠 **Indexes** content with TF-IDF (no external DB needed)
- 💬 **Answers** questions using only your product's docs (Claude AI + RAG)
- ⚠️ **Flags** billing/refund/angry-user conversations for human review
- 🔗 **Embeds** on any WordPress site with one script tag
        """)
    with col2:
        st.markdown("### Earning model")
        st.markdown("""
| Plan | Monthly Price |
|---|---|
| Starter (1 product) | $199/mo |
| Growth (5 products) | $499/mo |
| Agency (unlimited)  | $999/mo |

> This Streamlit app is your **free demo tool** to show clients.
> The FastAPI version is what paying clients get.
        """)
    st.divider()
    st.markdown("Built by **Mohsin** · [github.com/devmohsin](https://github.com/devmohsin/wordpress-ai-support-agent)")
