"""
tools.py
========
These are the "hands" of the agent - the actions it is allowed to perform.

  search_youtube        -> find a YouTube video            (yt-dlp, no key needed)
  transcribe_and_save   -> download audio + transcribe     (local faster-whisper)
  ask_knowledge_base    -> answer from saved transcripts   (OpenRouter LLM, RAG)

The "brain" (RAG answers + the agent loop) runs on OpenRouter (an OpenAI-
compatible API). Transcription runs LOCALLY with faster-whisper, so it needs no
API key and has no rate limits.

Each tool is just a normal Python function. agent.py is the brain that DECIDES
when to call them.
"""

import os
import re
import time
import hashlib
import yt_dlp
from dotenv import load_dotenv

# Load keys from the .env file. We NEVER hard-code keys in the source.
load_dotenv()

# Folder where we cache transcripts we've already made.
CACHE_DIR = "cache"

# The chat model (must support "tool calling" for the agent). Change here if you
# want a different OpenRouter model.
CHAT_MODEL = "meta-llama/llama-3.3-70b-instruct"

# Local Whisper model size. "tiny" is fastest / lightest (good for low-RAM PCs);
# "base" or "small" are more accurate but slower.
WHISPER_SIZE = "tiny"


# ---------------------------------------------------------------------------
# The brain: OpenRouter chat client (created lazily so import works keyless)
# ---------------------------------------------------------------------------
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        from openai import OpenAI  # OpenRouter speaks the OpenAI API
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is missing. Add it to your .env file "
                "(get a free key at https://openrouter.ai/keys)."
            )
        _llm = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    return _llm


def chat(messages, tools=None, tool_choice="auto"):
    """
    Call the chat model, RETRYING if we hit a rate limit (HTTP 429).

    Every text / agent call goes through this one function, so the whole project
    shares the same retry safety net. Returns the raw message object (which may
    contain tool calls when we pass `tools`).
    """
    kwargs = {"model": CHAT_MODEL, "messages": messages, "temperature": 0}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    for attempt in range(4):
        try:
            response = _get_llm().chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as error:
            if "429" in str(error) and attempt < 3:
                wait = 8 * (attempt + 1)  # back off: 8s, 16s, 24s
                print(f"[retry] rate-limited (429); waiting {wait}s then retrying...")
                time.sleep(wait)
                continue
            raise


# ---------------------------------------------------------------------------
# Transcription: local faster-whisper (loaded once, reused)
# ---------------------------------------------------------------------------
_whisper = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        # int8 on CPU keeps memory low; the model downloads once on first use.
        _whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    return _whisper


def _video_id(url: str) -> str:
    """Pull the YouTube video id out of a URL so we can use it as a cache key.
    Falls back to a short hash if the URL isn't a standard YouTube link."""
    match = re.search(r"(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else hashlib.md5(url.encode()).hexdigest()[:11]


# ---------------------------------------------------------------------------
# TOOL 1: Search YouTube with yt-dlp
# ---------------------------------------------------------------------------
def search_youtube(query: str) -> dict:
    """
    Search YouTube for the given text and return the FIRST matching video.

    "ytsearch1:<query>" tells yt-dlp to search and give back 1 result. We set
    skip_download / extract_flat so it only fetches the video INFO (title, id),
    not the video file - fast and light.

    Returns a small dict: {"title": ..., "url": ...}
    """
    options = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch",
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch1:{query}", download=False)

    entry = info["entries"][0]
    url = f"https://www.youtube.com/watch?v={entry['id']}"
    return {"title": entry.get("title", "Unknown title"), "url": url}


# ---------------------------------------------------------------------------
# TOOL 2: Transcribe locally with faster-whisper (and save to the knowledge base)
# ---------------------------------------------------------------------------
def transcribe_video(url: str) -> str:
    """
    Turn a YouTube video into text using a LOCAL Whisper model, and save it.

    Steps:
      1. CACHE   : if we've transcribed this video before, return the saved copy.
      2. DOWNLOAD: yt-dlp grabs the audio and (via ffmpeg) saves it as mp3.
      3. WHISPER : faster-whisper transcribes the mp3 on your own machine.
      4. SAVE    : store the transcript in the knowledge base (for RAG) + cache.

    Running Whisper locally means no API key and no rate limits for transcription.
    Returns the full transcript as a plain string.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, _video_id(url) + ".txt")

    # 1. CACHE CHECK
    if os.path.exists(cache_path):
        print("[cache] hit - reusing saved transcript")
        with open(cache_path, encoding="utf-8") as f:
            return f.read()

    # 2. DOWNLOAD the audio (and grab the title so we can name the saved file).
    audio_path, title = _download_audio(url)

    # 3. TRANSCRIBE locally.
    try:
        segments, _info = _get_whisper().transcribe(audio_path)
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass

    # 4. SAVE to the knowledge base (for RAG) and to the cache (to skip repeats).
    save_transcript(title, transcript)
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(transcript)
    return transcript


def transcribe_and_save(url: str) -> str:
    """
    Agent-facing tool: transcribe a video, save it, and return a SHORT status.

    Why not just return the transcript? A transcript can be thousands of words;
    handing all of that back to the language model would be slow and wasteful.
    We save it and return a tiny confirmation; the agent can later call
    `ask_knowledge_base` to actually use the content.
    """
    transcript = transcribe_video(url)  # this also saves to the knowledge base
    words = len(transcript.split())
    preview = transcript[:200].replace("\n", " ")
    return (f"Done. Transcribed and saved to the knowledge base "
            f"({words} words). Preview: {preview}...")


def _download_audio(url: str):
    """Download the best audio track with yt-dlp. Returns (mp3_path, video_title)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    out_base = os.path.join(CACHE_DIR, _video_id(url))

    options = {
        "quiet": True,
        "format": "bestaudio/best",
        "outtmpl": out_base + ".%(ext)s",
        # ffmpeg converts whatever we get into an mp3 that Whisper accepts.
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    return out_base + ".mp3", info.get("title", "video")


# ---------------------------------------------------------------------------
# KNOWLEDGE BASE: save the transcript to a file
# ---------------------------------------------------------------------------
def save_transcript(title: str, transcript: str) -> str:
    """
    Save the transcript into the knowledge_base/ folder as a .txt file.
    This is our tiny "knowledge base" - the place the agent remembers things.

    Returns the file path it saved to.
    """
    os.makedirs("knowledge_base", exist_ok=True)

    # Turn the video title into a safe filename (letters, numbers, - and _ only).
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    safe_name = safe_name.strip().replace(" ", "_")[:60] or "transcript"
    path = os.path.join("knowledge_base", f"{safe_name}.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write(transcript)

    return path


# ---------------------------------------------------------------------------
# TOOL 3: Answer a question using the saved transcripts (RAG-lite)
# ---------------------------------------------------------------------------
def ask_knowledge_base(question: str) -> str:
    """
    Answer a question using ONLY the transcripts we have already saved.

    This is a simple version of "RAG" (Retrieval-Augmented Generation):
      1. RETRIEVE : read the text stored in knowledge_base/.
      2. AUGMENT  : paste that text in front of the question as context.
      3. GENERATE : let the LLM answer using that context.

    The model does NOT invent an answer from memory - it answers from OUR data.
    That is the whole point of RAG: ground the AI in your own documents so it
    stays accurate and doesn't make things up.

    (We load ALL transcripts here because our knowledge base is tiny. For a big
     one you'd use embeddings + vector search to fetch only the relevant chunks.)
    """
    if not os.path.isdir("knowledge_base"):
        return "The knowledge base is empty. Transcribe a video first."

    # 1. RETRIEVE: gather every saved transcript into one big context string.
    context_parts = []
    for file_name in os.listdir("knowledge_base"):
        if file_name.endswith(".txt"):
            with open(os.path.join("knowledge_base", file_name), encoding="utf-8") as f:
                context_parts.append(f"--- From '{file_name}' ---\n{f.read()}")

    if not context_parts:
        return "The knowledge base is empty. Transcribe a video first."

    context = "\n\n".join(context_parts)

    # 2. AUGMENT + 3. GENERATE: force the model to answer only from our context.
    messages = [
        {"role": "system", "content":
            "You answer ONLY from the transcripts the user provides. "
            "If the answer is not in them, say you don't know."},
        {"role": "user", "content": f"TRANSCRIPTS:\n{context}\n\nQUESTION: {question}"},
    ]
    message = chat(messages)
    return message.content


# ---------------------------------------------------------------------------
# Quick manual test:  python tools.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    video = search_youtube("what is an API in simple terms")
    print("Found video:", video)

    status = transcribe_and_save(video["url"])
    print("\n" + status)

    answer = ask_knowledge_base("What is an API in one sentence?")
    print("\nRAG answer:", answer)
