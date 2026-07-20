# Scoring rubric

Score every summary against `document/source.txt` directly — re-read the source while scoring each one, don't score from memory. For each metric, write down the specific evidence (a quote or claim) that justifies the score, not just the number. "Accuracy: 4/5" with no note is not a score, it's a guess.

## 1. Summary quality (structure & readability) — 1-5
- 5: Coherent prose, logical order, reads like it was written by someone who understood the whole document, not just concatenated sentences from it.
- 3: Understandable but choppy, or has an ordering that doesn't match the source's logical flow.
- 1: Disjointed, redundant, or unclear what point is being made.

## 2. Accuracy — 1-5
- 5: Every claim traces back to something actually stated in the source.
- 3: Mostly accurate, but at least one claim is subtly distorted (e.g. a number, a causal relationship, or an attribution changed).
- 1: Multiple claims contradict or misrepresent the source.
Note: this is the metric most people score sloppily. Check every number, name, and quoted attribution against the source individually.

## 3. Conciseness — 1-5
- 5: Every sentence earns its place; no filler, no restated points, no low-value examples kept at the expense of higher-value ones.
- 3: Includes at least one minor tangent or redundant restatement.
- 1: Padded, repetitive, or spends disproportionate space on a minor detail while dropping a major one.

## 4. Hallucinations — 1-5 (5 = none found, lower = worse)
- 5: Nothing in the summary that isn't in the source.
- 3: One minor unsupported addition (e.g. a plausible-sounding but unstated inference).
- 1: Fabricated facts, numbers, names, or claims not present in the source at all.
List every hallucination found, verbatim, with the score — this list is the evidence a reader will actually trust, more than the number.

## Overall score
Not a plain average — weight accuracy and hallucinations higher, since a fluent, concise summary that misrepresents the source is worse than a clunky one that's faithful. State your weighting if you deviate from a simple average.
