"""
streamlit_app.py  -  ClipMind AI (Streamlit version, for deployment)
====================================================================
This is the entry point Streamlit Community Cloud runs.

Local:   streamlit run streamlit_app.py
Cloud:   push to GitHub, then https://share.streamlit.io -> New app ->
         pick this file, and add OPENROUTER_API_KEY in the app's Secrets.

Chat history + "New chat" live in st.session_state (per browser session),
mirroring the Claude-style sidebar.
"""

import os
import streamlit as st

# --- make the API key available to tools.py BEFORE we import it ---------------
# On Streamlit Cloud the key is stored in "Secrets" (st.secrets). Locally it can
# come from a .env file. We copy it into the environment so tools.py finds it.
try:
    if "OPENROUTER_API_KEY" in st.secrets:
        os.environ["OPENROUTER_API_KEY"] = st.secrets["OPENROUTER_API_KEY"]
except Exception:
    pass  # no secrets file locally -> tools.py falls back to .env

import tools
import agent

st.set_page_config(page_title="ClipMind AI", layout="wide")

# --- a little cream styling on top of the theme in .streamlit/config.toml -----
st.markdown("""
<style>
  .block-container{max-width:820px}
  [data-testid="stSidebar"]{background:#f3ecdf}
  .brand{font-size:20px;font-weight:700;letter-spacing:-.01em;margin-bottom:0}
  .brandtag{color:#8c8477;font-size:11px;font-weight:700;letter-spacing:.14em}
</style>
""", unsafe_allow_html=True)

# --- session state ------------------------------------------------------------
if "chats" not in st.session_state:
    st.session_state.chats = []      # list of {id, title, messages:[{role,text}]}
if "current" not in st.session_state:
    st.session_state.current = None  # id of the open chat


def get_current():
    return next((c for c in st.session_state.chats if c["id"] == st.session_state.current), None)


# --- sidebar: brand + New chat + history --------------------------------------
with st.sidebar:
    st.markdown('<p class="brand">ClipMind AI</p><p class="brandtag">VIDEO AGENT</p>',
                unsafe_allow_html=True)
    st.write("")
    if st.button("New chat", use_container_width=True):
        st.session_state.current = None
        st.rerun()

    st.caption("HISTORY")
    if not st.session_state.chats:
        st.caption("No chats yet.")
    for chat in st.session_state.chats:
        if st.button(chat["title"], key="h_" + chat["id"], use_container_width=True):
            st.session_state.current = chat["id"]
            st.rerun()

# --- main: mode + transcript --------------------------------------------------
mode = st.radio("Mode", ["Find & transcribe", "Ask saved videos"], horizontal=True)

current = get_current()
if current is None or not current["messages"]:
    st.title("ClipMind AI")
    st.write("Search a video, transcribe it, and ask questions about what it said.")

if current:
    for m in current["messages"]:
        st.chat_message("user" if m["role"] == "user" else "assistant").write(m["text"])

placeholder = ("Find and transcribe a video about how HTTP works"
               if mode == "Find & transcribe" else "What is an API key used for?")
prompt = st.chat_input(placeholder)

if prompt:
    # start a new chat lazily on the first message
    if current is None:
        current = {"id": str(len(st.session_state.chats)) + "_" + prompt[:8],
                   "title": prompt[:38], "messages": []}
        st.session_state.chats.insert(0, current)
        st.session_state.current = current["id"]

    current["messages"].append({"role": "user", "text": prompt})

    with st.spinner("Working... this can take a moment"):
        try:
            if mode == "Find & transcribe":
                result = agent.run_agent(prompt)
            else:
                result = tools.ask_knowledge_base(prompt)
        except Exception as error:
            result = f"Something went wrong: {error}"

    current["messages"].append({"role": "assistant", "text": result})
    st.rerun()
