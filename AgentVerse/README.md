# Personality Chatbot (Streamlit + Groq)

A chat app with selectable Groq models and five restricted-scope "personalities"
(Math Teacher, Doctor, Travel Guide, Chef, Tech Support). Each personality only
answers questions in its lane, and off-topic questions get redirected to the
right one with a single click. Built entirely with Streamlit for the UI and the
Groq Cloud API for inference.

## Features

- **Personality-scoped answers** — each persona has its own system prompt and
  refuses out-of-scope questions.
- **"Wrong desk" redirects** — when a persona declines a question, it also
  tells the app which persona *would* answer it; the UI shows a "Switch to X"
  button that re-asks the same question under the right persona automatically.
- **Per-persona memory** — each personality keeps its own conversation history
  independently, viewable and clearable from a sidebar panel (per-persona or
  all at once).
- **Smart Prompt Enhancer** — optional toggle that runs a fast pre-pass model
  to clean up typos/grammar before the message is sent, showing the user
  exactly what was changed.
- **Live stats** — response latency and word count shown under every reply.
- **Streaming responses** with a lightweight "thinking" indicator while the
  first token is in flight.
- **Custom design system** — no third-party CSS framework; hand-rolled theme
  (single light palette, no emoji) with SVG icons per persona used both as
  inline badges and as base64-encoded chat avatars.

## Tech Stack

- **Streamlit** — UI framework, chat components, session state
- **Groq Cloud API** (`groq` Python SDK) — LLM inference, streaming completions
- **python-dotenv** — local `.env` loading

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Get a Groq API key from https://console.groq.com/keys
3. Create a `.env` file (copy `.env.example`) and set:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

## Run locally

```
streamlit run app.py
```

## Deploy to Streamlit Cloud

1. Push this project to a GitHub repository (do **not** commit `.env`).
2. Go to https://share.streamlit.io, connect the repo, and set `app.py` as the
   entry point.
3. In the app's "Settings → Secrets", paste:
   ```
   GROQ_API_KEY = "your_groq_api_key_here"
   ```
4. Deploy and share the public URL.

---

## Architecture & Design Decisions

This section is written to double as interview prep — it explains *why*
things are built the way they are, not just what the code does.

### 1. How personality enforcement actually works

There's no classifier or keyword filter deciding whether a question is
"in scope." It's pure prompt engineering: each persona's `system_prompt`
(in `PERSONALITIES`) tells the model what it's allowed to answer, and
`build_system_prompt()` appends a shared instruction telling the model to
politely decline anything else.

The interesting part is the **redirect feature**. To know which persona
*should* answer an off-topic question, the model itself is asked to emit a
machine-readable signal alongside its human-readable refusal — a hidden
marker like `<!--SUGGEST:Chef-->` on its own line. `extract_suggestion()`
regex-matches that marker, strips it out before the text is ever shown to
the user, and returns the persona name separately so the UI can render a
button for it. `visible_prefix()` also strips anything after `<!--` during
*live streaming*, so the raw tag never flashes on screen while tokens are
still arriving.

This is essentially a cheap substitute for structured output / tool calling
— done with a plain regex instead of Groq's JSON mode or function calling.
Trade-off: simpler to implement and model-agnostic, but less robust than a
schema-constrained response (the model could technically get the tag format
wrong, though in practice it's reliable with clear formatting instructions).

### 2. State model: one conversation per persona

`st.session_state.chats` is `dict[persona_name, list[message]]` — each
persona has its own independent history, rather than one global chat that
gets wiped on switch. Each message is a dict carrying more than just
`role`/`content`: assistant messages also store `stats` (latency/word count),
`suggestion` (the redirect target, if any), and `trigger_query` (the exact
text that produced this reply, needed to resend it under a different
persona). This ad-hoc dict schema is fine at this scale; a larger app would
likely promote it to a dataclass or TypedDict.

### 3. Streaming responses

`client.chat.completions.create(..., stream=True)` returns an iterator of
chunks. Each chunk's `delta.content` is appended to a running string and
pushed into a `st.empty()` placeholder, so the UI updates token-by-token
instead of waiting for the full response — the standard pattern for
reducing *perceived* latency (time-to-first-token matters more to users than
total generation time).

### 4. A real bug worth knowing how to explain: Streamlit's widget/session_state ordering rule

Streamlit reruns the **entire script top-to-bottom** on every interaction.
A widget bound to a `session_state` key (via `key=...`) cannot have that key
reassigned by code *after* the widget has already been instantiated in the
same run — Streamlit raises a `StreamlitAPIException` if you try.

The bug: the "Switch to X" button lives in the message-rendering loop, which
runs *after* the sidebar's `personality_select` selectbox is created. The
first version of this button did `st.session_state.personality_select =
suggestion` directly inside its `if st.button(...)` block — which threw an
exception every single click, silently, because the click itself worked
fine and only the *state write* failed.

The fix uses a level of indirection: the button only sets
`st.session_state.pending_resend = {...}` and calls `st.rerun()`. On the
**next** script run, *before* the sidebar selectbox is instantiated, a short
block at the top of the script checks for `pending_resend` and applies it to
`personality_select` then. This "stash an intent, apply it on the next
natural checkpoint" pattern shows up constantly in immediate-mode/reactive
UI frameworks — it's conceptually the same reason you can't read updated
state synchronously right after calling `setState` in React.

### 5. A second real bug: environment variable caching in a long-running process

`load_dotenv()` does **not** overwrite variables that already exist in
`os.environ` by default. Since `streamlit run` keeps one Python process
alive across many reruns, the *first* time it read `.env` it cached the key
into the process environment — regenerating the key in `.env` afterward had
zero effect on the running process, and only looked like the app was still
using the old key. Fixed with `load_dotenv(override=True)`. This is a good
example of the difference between "config that's read once at process
startup" vs. "config that's re-read every request" — a distinction that
matters a lot for anything long-running (dev servers, workers, daemons).

### 6. Custom avatars without HTML support in `st.chat_message`

`st.chat_message(avatar=...)` only accepts an emoji, a local image path, or
a URL — it does *not* accept raw HTML/SVG. To get a persona-specific icon as
the assistant's avatar (instead of Streamlit's default face/robot icons),
`avatar_data_uri()` builds a small standalone SVG string (a colored circle
plus the persona's icon shape) and base64-encodes it into a
`data:image/svg+xml;base64,...` URI at runtime, computed once per persona
into `ASSISTANT_AVATARS`. This is a generally useful technique for embedding
small vector assets anywhere that only accepts a URL/path — no file I/O, no
external request, no extra assets to ship.

One subtlety: the same icon markup (`ICON_PATHS`) is reused for both the
inline badges (which rely on CSS `currentColor`, inherited from the page)
and the avatar images (which have *no* CSS cascade to inherit from, since
they're standalone SVG documents). The avatar builder explicitly sets an SVG
`color` attribute on a wrapping `<g>` so `fill="currentColor"` inside still
resolves correctly even with no surrounding stylesheet.

### 7. Theming: hand-written CSS, not a component library

Streamlit doesn't expose a first-class CSS/theming API beyond a basic
`config.toml` (and that doesn't support runtime switching or fine-grained
control). `inject_css()` injects a `<style>` block via
`st.markdown(unsafe_allow_html=True)`, targeting Streamlit's internal
`data-testid` attributes (e.g. `[data-testid="stChatMessage"]`) — those are
more stable across Streamlit versions than its auto-generated CSS class
names. This is the standard way to meaningfully theme a Streamlit app, with
the trade-off that it's coupled to Streamlit's internal DOM structure and
can break on a version upgrade.

### 8. Prompt enhancement as a two-model pipeline

When enabled, the Smart Prompt Enhancer makes a **separate, non-streaming**
call to `llama-3.1-8b-instant` (a small/fast/cheap model) purely to fix
grammar/clarity, before the user's *actual* question goes to whichever model
they picked for the main conversation. This is a small example of model
routing / task decomposition: use a cheap model for a cheap subtask (rewrite
a sentence) and reserve the larger model for the task that actually needs
its reasoning. The UI always shows the original text alongside the enhanced
one for transparency — the user should never wonder what was actually sent.

### 9. Security

- `GROQ_API_KEY` is never hardcoded. Locally it comes from `.env`
  (gitignored); on Streamlit Cloud it comes from `st.secrets`. The app falls
  back to a password-style sidebar input if neither is set.
- `.env.example` and `.streamlit/secrets.toml.example` exist as templates
  only — real secrets never get committed.

---

## Likely Interview Questions & Short Answers

**"Walk me through the architecture."**
Streamlit script that reruns top-to-bottom on every interaction; Groq's
OpenAI-compatible chat completions API for inference; `st.session_state`
holds a dict of per-persona conversation histories plus UI state (selected
model/persona, pending actions). No backend/database — it's a single
stateful Python process per user session.

**"How do you keep the chatbot on-topic?"**
System-prompt scoping per persona, plus a shared instruction appended at
request time (`build_system_prompt`) that tells the model exactly how to
decline and how to signal a better-fit persona via a hidden marker that gets
parsed out before display.

**"How does streaming work?"**
Groq's SDK returns a chunk iterator when `stream=True`; each `delta.content`
is appended and re-rendered into a `st.empty()` placeholder, so the user
sees tokens arrive live instead of waiting for the full completion.

**"Tell me about a bug you had to debug."**
Two good ones to have ready — pick whichever fits the question:
1. A button click was silently failing because it tried to mutate a
   widget-bound `session_state` key *after* that widget had already
   rendered in the same script run, which Streamlit disallows. Fixed by
   deferring the actual state mutation to the top of the *next* run.
2. `.env` key rotation appeared to do nothing because `load_dotenv()`
   doesn't override already-set environment variables in a long-running
   process — fixed with `load_dotenv(override=True)`.

**"How would you make the off-topic detection more robust?"**
Swap the regex-parsed hidden-comment convention for Groq's native structured
output / JSON mode (or tool calling) so the "should redirect / target
persona" decision is schema-constrained instead of relying on the model
following a formatting convention.

**"How would you scale this beyond a demo?"**
Move conversation state out of in-process `session_state` into a real store
(Redis/Postgres) keyed by user/session so it survives process restarts and
works across multiple server instances; add auth; rate-limit per user; move
the API key server-side only (already true here) with per-user quotas.

**"Why Streamlit instead of a JS frontend?"**
Fastest path from idea to a working, deployable chat UI in pure Python —
appropriate for this project's scope. The trade-off is exactly what shows up
in this codebase: theming requires CSS injection hacks against internal DOM
attributes, and the framework's rerun-the-whole-script model requires
understanding its state-timing rules (see the widget bug above) rather than
a more typical component-local state model.

## Notes

- Chat history persists per personality for the session (not wiped on
  switch); use the sidebar "Memory" panel or "Clear conversation" to reset it.
- If no API key is found in `.env`/Streamlit secrets, the sidebar shows a
  password-style input to paste one in for the session.
