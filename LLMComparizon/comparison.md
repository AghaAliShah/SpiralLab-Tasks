# LLM Summarization Comparison

**Document:** [Retrieval-augmented generation](https://en.wikipedia.org/wiki/Retrieval-augmented_generation) (Wikipedia, CC BY-SA 4.0) — see `document/source_meta.md`
**Prompt:** identical for every model, see `prompt.md`
**Scoring rubric:** `rubric.md`

## Results

| Model | Version | Summary Quality | Accuracy | Conciseness | Hallucinations | Overall |
|---|---|---|---|---|---|---|
| Claude | Haiku | 5 | 4 | 4 | 5 | 4.5 |
| Gemini | Flash 3.5 | 4 | 5 | 4 | 5 | 4.5 |
| GPT | 5.5 | 4 | 5 | 5 | 5 | 4.75 |

## Evidence log

### Claude (Haiku)
- Says RAG works by "eliminating the need to retrain models with new information." That's stronger than what the article says — the article is explicit that RAG "reduces the need for frequent model retraining, [but] it does not remove it entirely." This is the one real accuracy slip across all three summaries, and it's easy to miss on a skim because the sentence sounds perfectly natural.
- Reads the cleanest of the three: three tight paragraphs (what RAG is, how it works, where it breaks down), in the same order the article uses.
- Drops the Applications section and every named example (no Retro, no SPLADE, no Google Bard case) — reasonable given the word limit, but it means this summary leans more on general claims than specific detail.

### Gemini (Flash 3.5)
- No factual errors found — correctly says RAG "reduces computational and financial costs," not "eliminates" them.
- The only one of the three to name a specific technique from the Improvements section by name ("model redesigns like Retro"), instead of just gesturing at "redesigned language models."
- Still skips the Applications section entirely, same as Claude.

### GPT (5.5)
- No factual errors found either.
- The only summary of the three that mentions the Applications section at all (calls out healthcare specifically, plus the article's note about evaluation/reliability challenges there).
- Manages to reference nearly every sub-technique from the Improvements section — encoding, retriever optimization, reranking, hybrid search, chunking, redesigned models — inside the same ~180-word budget the other two used for less coverage. The tradeoff is that its second paragraph is doing a lot at once (process + applications + challenges back to back), so it reads slightly denser than Claude's.

## Conclusion

Honestly, all three did fine here — nobody invented a fact, a name, or a number, and all three stayed inside the 150–200 word range without padding it out. The real differences only show up once you go line by line against the source, not on a first read.

Claude's version reads the best. Three clean paragraphs, easy to follow, nothing clunky. But it's also the only one with an actual accuracy problem — it says RAG eliminates the need for retraining, and the article directly contradicts that. It's a small phrase, but it's a wrong claim, and you'd walk away from that summary believing something the source doesn't say.

Gemini is the safe middle option: accurate, reasonably complete, and it's the only one that bothered to name "Retro" specifically instead of being vague about "model redesigns."

GPT gave the most complete picture for the word count it used — it's the only one of the three that even mentions the article's Applications section (healthcare), and it touches nearly every improvement technique the article lists without going over the limit. It reads a little denser than Claude's because it's packing in more, but nothing in it is wrong.

If I had to pick one for this document, it's GPT — it got the most accurate mileage out of the same word budget. Claude wins on pure writing quality, but a summary that reads a little better while stating something false is worse than one that's slightly denser but true. That's really the main lesson here: fluency and accuracy don't move together, and the only way to catch the gap is to actually check the summary against the source, sentence by sentence, instead of trusting how confident and well-written it sounds.
