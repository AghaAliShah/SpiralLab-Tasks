# LLM Comparison — Document Summarization

## What's here
- `document/source.txt` — the document all three models summarize (Wikipedia, CC BY-SA 4.0; see `source_meta.md`)
- `document/prompt_filled.md` — the prompt with the document already inserted, ready to paste as one block into a chat UI
- `prompt.md` — the raw prompt template (for reference / reuse with a different document)
- `outputs/claude.md` — Claude's summary (already generated, from this session)
- `outputs/gemini.md`, `outputs/gpt.md` — paste the raw Gemini/GPT responses here; note the exact model version in the placeholder comment at the top of each file before you paste
- `rubric.md` — scoring definitions, so the scores in `comparison.md` are justified, not vibes
- `comparison.md` — the comparison table + evidence log + conclusion (fill in after all three outputs are collected)

## Workflow
1. Open Gemini and ChatGPT in the browser.
2. Paste the full contents of `document/prompt_filled.md` into each, unedited — same prompt, same document, no follow-up turns.
3. Paste each raw response into `outputs/gemini.md` and `outputs/gpt.md` respectively.
4. Score all three outputs against `rubric.md`, filling in `comparison.md` — check every claim against `document/source.txt` directly rather than from memory.
5. Write the conclusion yourself, in your own words.

## Optional: automating this instead
`summarize_compare.py` calls Groq/OpenAI/Gemini APIs programmatically with `temperature=0` and logs latency/tokens/cost to `runs.jsonl` — useful if you want a reproducible, scriptable version of this same comparison later (e.g. to re-run against a different document). Not needed for this deliverable since you're doing Gemini/GPT manually.
