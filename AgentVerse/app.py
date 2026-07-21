import os
import re
import time
import random
import base64
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv(override=True)

st.set_page_config(page_title="AgentVerse", layout="centered")

BRAND_LOGO = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="6" cy="7" r="2"/><circle cx="18" cy="7" r="2"/><circle cx="12" cy="17" r="2"/>'
    '<line x1="7.5" y1="8.5" x2="10.5" y2="15.5"/>'
    '<line x1="16.5" y1="8.5" x2="13.5" y2="15.5"/>'
    '<line x1="8" y1="7" x2="16" y2="7"/>'
    "</svg>"
)

# Context window sizes (tokens) as published in Groq's model docs. Used to
# show how much of a model's context budget the current conversation has
# used, alongside the token usage Groq returns with every completion.
CONTEXT_WINDOWS = {
    "llama-3.3-70b-versatile": 128_000,
    "llama-3.1-8b-instant": 128_000,
    "openai/gpt-oss-120b": 131_072,
    "openai/gpt-oss-20b": 131_072,
}


def estimate_tokens(text: str) -> int:
    """Fallback heuristic (~4 chars/token) if the API doesn't return usage."""
    return max(1, round(len(text) / 4))

# ---------------------------------------------------------------------------
# Icons: minimal line-icon shapes (no emoji), viewBox 0 0 24 24. Stored as
# inner markup only so they can be wrapped for either inline badges (which
# use currentColor via CSS) or standalone avatar images (which need an
# explicit color, since data-URI SVGs have no CSS cascade to inherit from).
# ---------------------------------------------------------------------------
ICON_PATHS = {
    "Math Teacher": (
        '<line x1="5" y1="19" x2="5" y2="13"/>'
        '<line x1="12" y1="19" x2="12" y2="8"/>'
        '<line x1="19" y1="19" x2="19" y2="4"/>'
    ),
    "Doctor": (
        '<rect x="4" y="4" width="16" height="16" rx="4"/>'
        '<line x1="12" y1="8.5" x2="12" y2="15.5"/>'
        '<line x1="8.5" y1="12" x2="15.5" y2="12"/>'
    ),
    "Travel Guide": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<polygon points="12,7 14,12 12,17 10,12" fill="currentColor" stroke="none"/>'
    ),
    "Chef": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<circle cx="12" cy="12" r="4.25"/>'
    ),
    "Tech Support": (
        '<rect x="3" y="4" width="18" height="16" rx="3"/>'
        '<polyline points="7.5 9.5 10.5 12 7.5 14.5"/>'
        '<line x1="12" y1="14.5" x2="16" y2="14.5"/>'
    ),
}

USER_ICON_PATH = (
    '<circle cx="12" cy="8" r="3.5"/>'
    '<path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6"/>'
)


def render_icon(name: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        f'stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS[name]}</svg>'
    )


def avatar_data_uri(inner: str, bg: str, fg: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">'
        f'<circle cx="20" cy="20" r="20" fill="{bg}"/>'
        f'<g transform="translate(8,8)" color="{fg}" stroke="{fg}" stroke-width="1.9" '
        f'fill="none" stroke-linecap="round" stroke-linejoin="round">{inner}</g>'
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"

# ---------------------------------------------------------------------------
# Personalities: each has a system prompt that strictly scopes its answers.
# ---------------------------------------------------------------------------
PERSONALITIES = {
    "Math Teacher": {
        "description": "Get help with math problems, concepts, and homework.",
        "system_prompt": (
            "You are a friendly, patient Math Teacher. You ONLY answer questions about "
            "mathematics: arithmetic, algebra, geometry, calculus, statistics, math "
            "concepts, math homework help, and related problem solving."
        ),
    },
    "Doctor": {
        "description": "Ask about symptoms, health, and general medical guidance.",
        "system_prompt": (
            "You are a knowledgeable Doctor persona. You ONLY answer questions about "
            "health, symptoms, medicine, wellness, and medical concepts, and you always "
            "include a brief reminder that you are an AI and not a substitute for a real "
            "medical professional for serious or urgent concerns."
        ),
    },
    "Travel Guide": {
        "description": "Get destination tips, itineraries, and travel advice.",
        "system_prompt": (
            "You are an enthusiastic Travel Guide. You ONLY answer questions about "
            "destinations, itineraries, travel tips, packing, visas, local culture, and "
            "trip planning."
        ),
    },
    "Chef": {
        "description": "Ask about recipes, techniques, and cooking tips.",
        "system_prompt": (
            "You are a passionate Chef. You ONLY answer questions about cooking, "
            "recipes, ingredients, techniques, and kitchen tips."
        ),
    },
    "Tech Support": {
        "description": "Get help troubleshooting devices, software, and tech issues.",
        "system_prompt": (
            "You are a helpful Tech Support agent. You ONLY answer questions about "
            "devices, software, apps, networking, and troubleshooting technical issues."
        ),
    },
}

MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

THINKING_PHRASES = [
    "Thinking", "Working on it", "Considering your question",
    "Putting thoughts together", "Drafting a reply", "Looking into it",
]

SUGGEST_TAG_RE = re.compile(r"<!--\s*SUGGEST:\s*(.*?)\s*-->", re.IGNORECASE | re.DOTALL)

ENHANCER_SYSTEM_PROMPT = (
    "Rewrite the user's message to fix spelling, grammar, and clarity while strictly "
    "preserving its original meaning, intent, and language. Do not answer the question, "
    "do not add new content, do not add quotes. Return ONLY the rewritten message."
)


def build_system_prompt(name: str) -> str:
    others = ", ".join(p for p in PERSONALITIES if p != name)
    return (
        PERSONALITIES[name]["system_prompt"]
        + " If the user asks about anything outside this scope, politely decline in 1-2 "
          "sentences, invite them to ask an on-topic question instead, and do NOT answer "
          "the off-topic question in any way. Then, on a new line, append exactly one "
          f"hidden marker (it will be stripped before the user sees it): if one of these "
          f"other personas — {others} — clearly fits the question better, write "
          "<!--SUGGEST:ExactPersonaName--> using the exact name from that list; otherwise "
          "write <!--SUGGEST:None-->. Only include this marker when declining an "
          "off-topic question — never include it when you answer in-scope."
    )


def extract_suggestion(text: str):
    match = SUGGEST_TAG_RE.search(text)
    if not match:
        return text.strip(), None
    cleaned = SUGGEST_TAG_RE.sub("", text).strip()
    name = match.group(1).strip()
    if name not in PERSONALITIES:
        return cleaned, None
    return cleaned, name


def visible_prefix(text: str) -> str:
    return text.split("<!--")[0]


def icon_badge(name: str, box: int = 20, icon_size: int = 12) -> str:
    return (
        f'<span class="icon-badge" style="width:{box}px;height:{box}px;">'
        f'<span style="width:{icon_size}px;height:{icon_size}px;display:inline-flex">'
        f"{render_icon(name)}</span></span>"
    )


def render_context_bar(used: int, capacity: int) -> str:
    pct = min(100.0, round(used / capacity * 100, 1))
    return (
        '<div class="composer-footer"><div class="context-bar-label">'
        f"<span>Context window</span><span>{used:,} / {capacity:,} tokens ({pct}%)</span>"
        f'</div><div class="context-bar-track">'
        f'<div class="context-bar-fill" style="width:{pct}%;"></div></div></div>'
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
st.session_state.setdefault("chats", {name: [] for name in PERSONALITIES})
st.session_state.setdefault("personality_select", list(PERSONALITIES)[0])
st.session_state.setdefault("model_select", MODELS[0])
st.session_state.setdefault("enhance_enabled", False)
st.session_state.setdefault("pending_resend", None)

# Apply a personality switch requested by a "Switch to X" button click.
# This MUST happen before the personality selectbox widget below is
# instantiated, since Streamlit forbids writing to a widget's session_state
# key after that widget has been created in the same script run.
if st.session_state.pending_resend:
    st.session_state.personality_select = st.session_state.pending_resend["personality"]

# ---------------------------------------------------------------------------
# Theme (single light palette)
# ---------------------------------------------------------------------------
THEME = dict(
    bg="#fafafa", surface="#ffffff", border="#e4e4e7", text="#18181b",
    muted="#71717a", accent="#4f46e5", accent_hover="#4338ca",
    accent_soft="#eef2ff", accent_border="#c7d2fe", accent_text="#3730a3",
)

USER_AVATAR = avatar_data_uri(USER_ICON_PATH, bg="#e4e4e7", fg="#52525b")
ASSISTANT_AVATARS = {
    name: avatar_data_uri(ICON_PATHS[name], bg=THEME["accent_soft"], fg=THEME["accent"])
    for name in PERSONALITIES
}


def inject_css():
    v = THEME
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', -apple-system, sans-serif; }}

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
            background: {v['bg']}; color: {v['text']};
        }}

        .block-container {{ padding-top: 4.5rem; padding-bottom: 3rem; max-width: 760px; }}

        [data-testid="stSidebar"] {{
            background: {v['surface']}; border-right: 1px solid {v['border']};
        }}

        /* Brand bar */
        .brand-bar {{ display: flex; align-items: center; gap: 10px; margin-bottom: 22px; }}
        .brand-bar .brand-logo {{
            width: 30px; height: 30px; border-radius: 9px; background: {v['accent']};
            color: #ffffff; display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        }}
        .brand-bar .brand-logo svg {{ width: 16px; height: 16px; }}
        .brand-bar .brand-name {{
            font-family: 'Inter', sans-serif; font-weight: 700; font-size: 1.15rem;
            letter-spacing: -0.02em;
            background: linear-gradient(90deg, {v['accent']}, #9333ea);
            -webkit-background-clip: text; background-clip: text; color: transparent;
        }}

        /* Header */
        .app-header {{
            display: flex; align-items: center; gap: 14px;
            padding-bottom: 18px; margin-bottom: 20px; border-bottom: 1px solid {v['border']};
        }}
        .app-header .badge-icon {{
            width: 44px; height: 44px; border-radius: 12px;
            background: {v['accent_soft']}; color: {v['accent']};
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }}
        .app-header .badge-icon svg {{ width: 22px; height: 22px; }}
        .app-header h1 {{
            font-size: 1.3rem; font-weight: 650; margin: 0; color: {v['text']};
            letter-spacing: -0.01em;
        }}
        .app-header p {{ margin: 2px 0 0 0; font-size: 0.85rem; color: {v['muted']}; }}
        .model-tag {{
            display: inline-block; font-size: 0.72rem; color: {v['muted']};
            background: {v['bg']}; border: 1px solid {v['border']};
            padding: 2px 10px; border-radius: 999px; margin-top: 10px; font-weight: 500;
        }}

        /* Composer footer: context-window usage + input hint */
        .composer-footer {{ margin: 14px 0 4px 0; }}
        .context-bar-label {{
            display: flex; justify-content: space-between; font-size: 0.72rem;
            color: {v['muted']}; margin-bottom: 4px;
        }}
        .context-bar-track {{
            height: 5px; border-radius: 999px; background: {v['border']}; overflow: hidden;
        }}
        .context-bar-fill {{
            height: 100%; border-radius: 999px; background: {v['accent']};
        }}
        .composer-hint {{
            font-size: 0.75rem; color: {v['muted']}; text-align: center; margin-top: 8px;
        }}

        /* Icon badges (used in header + suggestion callouts) */
        .icon-badge {{
            display: inline-flex; align-items: center; justify-content: center;
            border-radius: 7px; background: {v['accent_soft']}; color: {v['accent']};
            flex-shrink: 0;
        }}
        .icon-badge svg {{ width: 100%; height: 100%; }}

        /* Chat messages */
        [data-testid="stChatMessage"] {{
            border-radius: 14px; padding: 6px 6px; margin-bottom: 10px; border: none;
        }}
        [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {{
            background: {v['accent_soft']}; border: 1px solid {v['accent_border']};
        }}
        [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) {{
            background: {v['surface']}; border: 1px solid {v['border']};
        }}

        [data-testid="stChatInputTextArea"] {{
            background: {v['surface']}; color: {v['text']}; border-radius: 14px;
        }}
        [data-testid="stChatInput"] {{ border-radius: 14px; }}
        button[data-testid="stChatInputSubmitButton"] {{
            background: {v['accent']} !important; border-color: {v['accent']} !important;
        }}
        button[data-testid="stChatInputSubmitButton"]:hover {{
            background: {v['accent_hover']} !important;
        }}

        .stButton > button {{
            border-radius: 10px; font-weight: 500; border: 1px solid {v['border']};
            color: {v['text']}; background: {v['surface']}; transition: all .15s ease;
        }}
        .stButton > button:hover {{
            border-color: {v['accent']}; color: {v['accent']}; background: {v['accent_soft']};
        }}

        .suggest-box {{
            background: {v['accent_soft']}; border: 1px solid {v['accent_border']};
            border-radius: 10px; padding: 10px 12px; margin: 4px 0 10px 0;
        }}
        .suggest-box-row {{
            display: flex; align-items: center; gap: 10px;
            font-size: 0.85rem; color: {v['accent_text']};
        }}

        .thinking-dots {{
            display: inline-flex; align-items: center; gap: 6px;
            color: {v['muted']}; font-size: 0.9rem;
        }}
        .thinking-dots .dot {{
            width: 5px; height: 5px; border-radius: 50%; background: {v['muted']};
            animation: dot-pulse 1.2s infinite ease-in-out;
        }}
        .thinking-dots .dot:nth-child(2) {{ animation-delay: .15s; }}
        .thinking-dots .dot:nth-child(3) {{ animation-delay: .3s; }}
        @keyframes dot-pulse {{
            0%, 80%, 100% {{ opacity: .25; transform: scale(.8); }}
            40% {{ opacity: 1; transform: scale(1); }}
        }}

        *:focus-visible {{ outline: 2px solid {v['accent']}; outline-offset: 2px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("Settings")

api_key = os.getenv("GROQ_API_KEY", "") or st.secrets.get("GROQ_API_KEY", "")
if not api_key:
    st.sidebar.warning("No GROQ_API_KEY found in environment (.env).")
    api_key = st.sidebar.text_input("Groq API Key", type="password")

selected_model = st.sidebar.selectbox("AI Model", MODELS, key="model_select")

selected_personality = st.sidebar.selectbox(
    "Chatbot Personality",
    list(PERSONALITIES.keys()),
    key="personality_select",
)

st.sidebar.toggle(
    "Smart Prompt Enhancer",
    key="enhance_enabled",
    help="Fixes typos/grammar and clarifies your message before sending it.",
)

if st.sidebar.button("Clear conversation"):
    st.session_state.chats[selected_personality] = []
    st.rerun()

with st.sidebar.expander("Memory", expanded=False):
    view_choice = st.selectbox(
        "View memory for",
        list(PERSONALITIES.keys()),
        key="memory_view_select",
    )
    view_msgs = st.session_state.chats[view_choice]
    st.caption(f"{len(view_msgs)} message(s) stored")
    if view_msgs:
        for m in view_msgs:
            st.markdown(f"**{m['role'].title()}:** {m['content']}")
    else:
        st.caption("No messages yet.")
    c1, c2 = st.columns(2)
    if c1.button("Clear this", key="clear_this_memory"):
        st.session_state.chats[view_choice] = []
        st.rerun()
    if c2.button("Clear all", key="clear_all_memory"):
        st.session_state.chats = {n: [] for n in PERSONALITIES}
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Powered by Groq Cloud API")

# ---------------------------------------------------------------------------
# Main chat UI
# ---------------------------------------------------------------------------
st.markdown(
    f'<div class="brand-bar"><div class="brand-logo">{BRAND_LOGO}</div>'
    '<span class="brand-name">AgentVerse</span></div>',
    unsafe_allow_html=True,
)

info = PERSONALITIES[selected_personality]
st.markdown(
    f"""
    <div class="app-header">
        <div class="badge-icon">{render_icon(selected_personality)}</div>
        <div>
            <h1>{selected_personality}</h1>
            <p>{info['description']}</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
context_window = CONTEXT_WINDOWS.get(selected_model, 128_000)
st.markdown(
    f'<span class="model-tag">{selected_model} · {context_window // 1000}K context</span>',
    unsafe_allow_html=True,
)

messages = st.session_state.chats[selected_personality]

for idx, message in enumerate(messages):
    avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATARS[selected_personality]
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("stats"):
            s = message["stats"]
            st.caption(f"{s['latency']:.1f}s · {s['words']} words · {s['tokens']} tokens")
        if message["role"] == "assistant" and message.get("suggestion"):
            suggestion = message["suggestion"]
            st.markdown(
                f'<div class="suggest-box"><div class="suggest-box-row">'
                f'{icon_badge(suggestion)}<span>This looks like a <b>{suggestion}</b> '
                f"question.</span></div></div>",
                unsafe_allow_html=True,
            )
            if st.button(f"Switch to {suggestion}", key=f"switch_{selected_personality}_{idx}"):
                st.session_state.pending_resend = {
                    "personality": suggestion,
                    "query": message["trigger_query"],
                }
                st.rerun()

# Pull in a resend triggered by a "switch persona" button click, if any.
incoming_query = None
pending = st.session_state.pending_resend
if pending and pending["personality"] == selected_personality:
    incoming_query = pending["query"]
    st.session_state.pending_resend = None

# Context used so far (before this turn) — needed as a base for the token
# estimate fallback below. The footer itself renders further down, AFTER a
# new exchange (if any) has completed, so it reflects up-to-date totals
# instead of the pre-turn value. st.chat_input always docks to the bottom
# of the viewport regardless of where it's called in the script, so calling
# it here and rendering the footer later doesn't affect its position.
context_used = messages[-1]["stats"]["total_tokens"] if messages and messages[-1].get("stats") else 0

user_input = st.chat_input(f"Message {selected_personality}...")
final_query = incoming_query or user_input

if final_query:
    if not api_key:
        st.error("Please provide a Groq API key in the sidebar or a .env file (GROQ_API_KEY=...).")
        st.stop()

    client = Groq(api_key=api_key)
    original_query = final_query
    display_query = original_query
    enhanced_note = None

    if incoming_query is None and st.session_state.enhance_enabled:
        try:
            enhance_resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": ENHANCER_SYSTEM_PROMPT},
                    {"role": "user", "content": original_query},
                ],
                temperature=0.3,
                max_tokens=300,
                stream=False,
            )
            enhanced = enhance_resp.choices[0].message.content.strip()
            if enhanced and enhanced.lower() != original_query.strip().lower():
                display_query = enhanced
                enhanced_note = original_query
        except Exception:
            pass

    messages.append({"role": "user", "content": display_query})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(display_query)
        if enhanced_note:
            st.caption(f"Adjusted for clarity — originally: “{enhanced_note}”")

    api_messages = [
        {"role": "system", "content": build_system_prompt(selected_personality)}
    ] + [{"role": m["role"], "content": m["content"]} for m in messages]

    with st.chat_message("assistant", avatar=ASSISTANT_AVATARS[selected_personality]):
        placeholder = st.empty()
        placeholder.markdown(
            f'<span class="thinking-dots">{random.choice(THINKING_PHRASES)}'
            f'<span class="dot"></span><span class="dot"></span><span class="dot"></span>'
            f"</span>",
            unsafe_allow_html=True,
        )
        full_response = ""
        usage_info = None
        start = time.perf_counter()
        try:
            stream = client.chat.completions.create(
                model=selected_model,
                messages=api_messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        full_response += delta
                        placeholder.markdown(visible_prefix(full_response) + "▌")
                if chunk.usage:
                    usage_info = chunk.usage
            cleaned_response, suggestion = extract_suggestion(full_response)
            placeholder.markdown(cleaned_response)
        except Exception as e:
            cleaned_response = f"Error calling Groq API: {e}"
            suggestion = None
            placeholder.markdown(cleaned_response)
        elapsed = time.perf_counter() - start
        word_count = len(cleaned_response.split())
        # Prefer Groq's actual token usage; fall back to a rough estimate
        # (e.g. if the call errored before any usage chunk arrived).
        if usage_info:
            completion_tokens = usage_info.completion_tokens
            total_tokens = usage_info.total_tokens
        else:
            completion_tokens = estimate_tokens(cleaned_response)
            total_tokens = context_used + estimate_tokens(display_query) + completion_tokens
        st.caption(f"{elapsed:.1f}s · {word_count} words · {completion_tokens} tokens")
        if suggestion:
            st.markdown(
                f'<div class="suggest-box"><div class="suggest-box-row">'
                f'{icon_badge(suggestion)}<span>This looks like a <b>{suggestion}</b> '
                f"question.</span></div></div>",
                unsafe_allow_html=True,
            )
            if st.button(f"Switch to {suggestion}", key=f"switch_new_{len(messages)}"):
                st.session_state.pending_resend = {
                    "personality": suggestion,
                    "query": display_query,
                }
                st.rerun()

    messages.append(
        {
            "role": "assistant",
            "content": cleaned_response,
            "stats": {
                "latency": elapsed,
                "words": word_count,
                "tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "suggestion": suggestion,
            "trigger_query": display_query,
        }
    )

# Composer footer: how much of the model's context window this conversation
# has used, plus a quick hint on the input's keyboard shortcuts. Rendered
# last so it reflects the exchange that (maybe) just happened above.
footer_used = messages[-1]["stats"]["total_tokens"] if messages and messages[-1].get("stats") else 0
st.markdown(render_context_bar(footer_used, context_window), unsafe_allow_html=True)
st.markdown(
    '<div class="composer-hint">Press Enter to send · Shift + Enter for a new line</div>',
    unsafe_allow_html=True,
)
