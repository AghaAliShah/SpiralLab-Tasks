"""
tests/test_all.py
=================
One script that exercises EVERY feature and prints PASS/FAIL for each:

  main features : search_youtube, transcribe_video, save_transcript, agent loop
  extras        : caching, RAG (ask_knowledge_base), audio-download fallback

Run it:   python tests/test_all.py
"""

import os
import sys
import time

# Make prints UTF-8 safe (Hindi/emoji transcripts crash the Windows console otherwise).
sys.stdout.reconfigure(encoding="utf-8")

# Run from the PROJECT ROOT so cache/ and knowledge_base/ land in the same place
# the real app uses. (tests/ is one level below the root.)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import tools
import agent

results = []


def step(name, fn):
    """Run one check safely and record PASS/FAIL without stopping the whole run.
    A check may return ok=None to mean SKIP (e.g. an external service blocked us);
    a skip is not counted as a failure."""
    try:
        ok, detail = fn()
    except Exception as error:
        ok, detail = False, f"ERROR: {error}"
    label = "SKIP  " if ok is None else ("PASS  " if ok else "FAIL  ")
    print(label + name + (f"   -> {detail}" if detail else ""))
    if ok is not None:
        results.append(ok)


print("=" * 60)
print("Testing MAIN FEATURES")
print("=" * 60)

# Shared state between steps.
state = {}


def t_search():
    v = tools.search_youtube("what is an API in simple terms")
    state["video"] = v
    return ("youtube.com" in v["url"], v["title"])


def t_transcribe():
    t = tools.transcribe_video(state["video"]["url"])
    state["transcript"] = t
    return (len(t) > 100, f"{len(t)} chars")


def t_save():
    path = tools.save_transcript(state["video"]["title"], state["transcript"])
    state["path"] = path
    return (os.path.exists(path), path)


step("search_youtube returns a YouTube url", t_search)
step("transcribe_video returns a transcript", t_transcribe)
step("save_transcript writes a file", t_save)

print("\n" + "=" * 60)
print("Testing EXTRAS")
print("=" * 60)


def t_cache_created():
    cache_file = os.path.join(tools.CACHE_DIR, tools._video_id(state["video"]["url"]) + ".txt")
    state["cache_file"] = cache_file
    return (os.path.exists(cache_file), cache_file)


def t_cache_hit():
    # Second call for the same video must be instant (read from cache) and identical.
    start = time.time()
    again = tools.transcribe_video(state["video"]["url"])
    elapsed = time.time() - start
    same = again == state["transcript"]
    return (same and elapsed < 2, f"same={same}, {elapsed:.2f}s")


def t_rag():
    ans = tools.ask_knowledge_base("What is an API key used for?")
    hit = any(w in ans.lower() for w in ["key", "request", "identif", "spam", "overload"])
    return (hit, ans[:80].replace("\n", " "))


def t_whisper():
    # Transcribe a short video FRESH (no cache) so local Whisper actually runs.
    import os as _os
    short = tools.search_youtube("what is http in 100 seconds fireship")
    # clear any cached copy so we exercise the real download + Whisper path
    cache_file = _os.path.join(tools.CACHE_DIR, tools._video_id(short["url"]) + ".txt")
    if _os.path.exists(cache_file):
        _os.remove(cache_file)
    try:
        text = tools.transcribe_video(short["url"])
    except Exception as error:
        # YouTube sometimes rate-limits downloads (HTTP 429 / "confirm you're not
        # a bot"). That's an external block, not our bug -> skip, don't fail.
        if "429" in str(error) or "bot" in str(error).lower():
            return (None, "skipped: YouTube rate-limited the download")
        raise
    return (len(text) > 50, f"{len(text)} chars")


step("caching: cache file was created", t_cache_created)
step("caching: 2nd call is an instant cache hit", t_cache_hit)
step("RAG: ask_knowledge_base answers from transcript", t_rag)
step("transcription: local Whisper on fresh audio", t_whisper)

print("\n" + "=" * 60)
print("Testing AGENT (end-to-end tool orchestration)")
print("=" * 60)


def t_agent():
    out = agent.run_agent("Using only the knowledge base, what is an API endpoint?")
    return (len(out) > 20, out[:80].replace("\n", " "))


step("agent picks tools and answers", t_agent)

print("\n" + "=" * 60)
passed = sum(results)
print(f"RESULT: {passed}/{len(results)} checks passed")
print("=" * 60)
sys.exit(0 if passed == len(results) else 1)
