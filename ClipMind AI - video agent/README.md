# ClipMind AI — Video Search, Transcription & RAG Agent

An AI agent that, given a plain-English goal, **searches YouTube, transcribes the
video, saves the transcript, and answers questions about it** — deciding the steps
on its own with LLM function-calling.

## Architecture

```
                ┌───────────────────────────────────────────────┐
   You ──goal──►│         AGENT  (OpenRouter LLM brain)          │
                │   loop: think → pick a tool → use result → …   │
                └───────────────┬───────────────────────────────┘
                                │ chooses which tool to call
        ┌───────────────────────┼────────────────────────────┐
        ▼                       ▼                            ▼
 search_youtube        transcribe_and_save            ask_knowledge_base
   (yt-dlp)          (yt-dlp + local Whisper)          (RAG / OpenRouter)
        │                       │                            ▲
        │                   ┌───┴────┐                       │
        │                   │ cache  │   knowledge_base/ ─────┘
        │                   └────────┘      (.txt files)
   YouTube search        (skip repeats)
```

The agent is **not a fixed script**. You give it a **goal + tools**; it chooses
which tool to run and when. That decision loop lives in `agent.py`.

## Providers
- **Brain (agent + RAG):** OpenRouter (OpenAI-compatible). One `chat()` helper
  with **429 retry + backoff**. Swap the model in one line (`CHAT_MODEL`).
- **Transcription:** local **faster-whisper** — runs on your machine, so no API
  key and no rate limits. Model size is set by `WHISPER_SIZE` (`tiny` by default).

## Files
- `tools.py` — the tools: `search_youtube`, `transcribe_and_save` (with **caching**),
  `save_transcript`, `ask_knowledge_base` (**RAG**).
- `agent.py` — the brain: describes the tools to the LLM and runs the agent loop.
- `streamlit_app.py` — **ClipMind AI** UI for deployment (Streamlit): sidebar chat
  **history** + **New chat**, cream theme, loading spinner. This is the deploy entry point.
- `app.py` — the same UI as a local Flask app (optional alternative to Streamlit).
- `tests/test_all.py` — tests every feature (PASS / FAIL / SKIP report).
- `knowledge_base/` — saved transcripts (the RAG store).
- `cache/` — cached transcripts so we never re-transcribe the same video.
- Deploy files: `requirements.txt`, `packages.txt` (ffmpeg), `.streamlit/config.toml`
  (theme), `.streamlit/secrets.toml.example`, `.gitignore`.

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env          # then paste your OpenRouter key into .env
```
Get a free OpenRouter key: https://openrouter.ai/keys
(Transcription also needs `ffmpeg` on your PATH.)

## Run locally
```bash
streamlit run streamlit_app.py   # ClipMind AI UI at http://localhost:8501
python agent.py                  # or run the agent in the terminal
python tests/test_all.py         # full test suite
```

## Deploy to Streamlit Community Cloud (free)
1. Push this folder to a **GitHub** repo.
2. Go to **https://share.streamlit.io** → **New app**, pick your repo and
   `streamlit_app.py` as the main file.
3. In the app's **Settings → Secrets**, add:
   ```toml
   OPENROUTER_API_KEY = "sk-or-v1-your_key_here"
   ```
4. Deploy. `packages.txt` installs ffmpeg and `requirements.txt` installs the rest.

**Heads-up on the cloud:** YouTube often blocks downloads from datacenter IPs, so
**Find & transcribe** may fail on Streamlit Cloud even though it works locally.
**Ask saved videos** (RAG over the shipped transcripts) works anywhere. For a live
transcription demo, either run locally or add YouTube cookies to yt-dlp.

## Interview cheat-sheet (memorize these)

**"Why is this an agent and not just a script?"**
A script runs steps you hard-coded. Here I only give the model a *goal* plus a set
of *tools*. The model itself decides which tool to call and in what order, reads
each result, and picks the next move. That decision loop is the agent.

**"How does the model call your Python functions?" (function calling)**
The model never sees my code — only text *descriptions* of each tool. When it wants
one, it replies with the tool name + arguments; my loop runs the real function and
sends the result back. Repeat until it returns a final text answer.

**"What is RAG and why use it?"**
Retrieval-Augmented Generation. Instead of trusting the model's memory, I *retrieve*
my saved transcripts, paste them in as context, and make the model answer only from
them. Keeps answers accurate and stops it making things up.

**"How does transcription work?"**
yt-dlp downloads the video's audio as mp3, then a local Whisper model turns speech
into text — no external transcription API, so no keys or rate limits.

**"What did you add to make it production-ready?"**
- **Caching** — skip re-transcribing a video we've already done (saves time + compute).
- **Retry with backoff** — on a rate limit (HTTP 429) we wait and retry instead of crashing.
- **Provider-swappable** — the brain is one `chat()` function; changing model/provider is trivial.
- **Secrets in `.env`** — the API key is never hard-coded.

## Tech
Streamlit · yt-dlp · faster-whisper (local) · OpenRouter (function calling) · Python
