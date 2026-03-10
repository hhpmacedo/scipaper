# Style Constitution

**Version:** 1.1.0
**Status:** LOCKED
**Last Updated:** 2026-03-07

> This document defines the writing style for all Signal publications. It is version-controlled and changes require explicit approval. The generation pipeline checks against this document to ensure consistency.

---

## Core Identity

**Signal writes like Quanta Magazine for AI.** Rigorous, curious, accessible. We explain research without dumbing it down or hyping it up.

---

## The Five Laws

### 1. Zero Hype

**Never** use:

- "Revolutionary", "groundbreaking", "game-changing"
- "This changes everything"
- "The future of X"
- Superlatives without evidence
- Speculation about implications beyond what the paper claims

**Instead:** State what the paper actually shows, with appropriate hedging.

❌ "This revolutionary paper changes everything we know about language models."

✅ "The paper shows that smaller models can match larger ones on reasoning tasks when given more compute at inference time—a result that could shift how practitioners think about the speed-quality tradeoff."

### 2. Concrete Over Abstract

Every abstract concept needs a concrete example within two sentences.

❌ "The model uses attention mechanisms to process sequential data."

✅ "The model processes text word by word, but can 'look back' at earlier words when needed—like how you might re-read the beginning of a sentence to understand a pronoun at the end."

### 3. Respect the Reader

Our reader is **intelligent but not a researcher**. They understand:

- What APIs and ML models are
- Basic programming concepts
- That neural networks learn from data
- Statistical concepts like "training" and "validation"

They may not understand:

- Specific architectures (transformers, attention)
- Mathematical notation
- Academic jargon

**Rule:** If you use a technical term, explain it in parentheses or link to an explanation. If you can't explain it simply, cut it.

### 4. One Surprising Thing

Every piece must have one genuinely surprising finding or insight. This goes in the first sentence.

The surprising thing should be:

- Actually surprising (not just "researchers found X works")
- Grounded in the paper's results
- Stated concretely, not abstractly

❌ "Researchers made progress on reasoning."

✅ "A model trained only on synthetic math problems learned to write working Python code—something the researchers didn't train it to do."

### 5. Honest About Limitations

Every piece must include what the paper _doesn't_ show. Be specific.

**Include:**

- What benchmarks were used and their known limitations
- What conditions were tested vs. not tested
- What the authors themselves note as limitations
- Sample sizes and statistical significance where relevant

---

## Structure

Every piece follows this structure, with word budgets:

### 1. Hook (~20 words, 1 sentence)

The surprising capability or finding. Must answer: what can now be done that couldn't before, or what assumption just got challenged?

**Hook rule:** The first sentence must state a capability or finding — NEVER a method description.

- ❌ "Researchers propose a method to identify which AI model wrote code."
- ✅ "You can now identify which specific AI model wrote a piece of code — with 87% accuracy."

### 2. Signal Block (~60 words, 2-3 sentences) — NEW IN v1.1

Visually separated executive summary. Answers three questions in order:

1. What capability is emerging from this work?
2. How mature is it? (lab proof-of-concept / pattern emerging in production frameworks / actionable today)
3. What decision does it inform for practitioners?

This is not a method summary. It is the practitioner's filter. Executives who only read this block should walk away knowing what moved this week.

### 3. The Problem (~150 words, 2-3 paragraphs)

What were the researchers trying to solve? Why is it hard? Why does it matter?

### 4. What They Did (~250 words, 3-4 paragraphs)

The actual approach, explained concretely. Include:

- The core idea in plain language
- At least one specific example or analogy
- What makes this different from previous approaches
- If the paper has multiple contributions, pick the primary one. Compress the others to 1-2 sentences each.

Every named technique, loss function, or abstraction must be followed within two sentences by a concrete example or analogy of what it does in practice. If you cannot ground it concretely, name the effect instead.

### 5. The Results (~150 words, 2-3 paragraphs)

**Required:** At least one specific performance number with a baseline or comparison that makes it interpretable.

- ✅ "DCAN achieves 87% attribution accuracy across four models, compared to 62% for the best existing method."
- ❌ "reliable attribution performance across diverse settings" (quoting the abstract is not reporting results)

Every limitation must be dual-framed:

- Technical dimension (for builders): what's incomplete about the methodology
- Production timeline dimension (for decision-makers): what this means for applicability
- ❌ "The benchmark covers only four LLMs and four languages."
- ✅ "The benchmark covers only four LLMs and four languages — production codebases with mixed model usage and human edits are a harder problem, likely 2-3 years from reliable tooling."

### 6. Why It Matters (~120 words, 1-2 paragraphs)

Implications for practitioners. Stay grounded — no speculation about "changing the world." Every implication must trace back to something the paper demonstrated.

Include one sentence positioning the work on the maturity spectrum: lab proof-of-concept, pattern emerging in production frameworks, or actionable today.

### Citations

Inline citations throughout: `[§3.2]`, `[Figure 4]`, `[Abstract]`

---

## Length

- Full pieces: 800-1000 words (hard cap: 1000)
- Quick Takes: 1-2 sentences — must include a specific finding or result, not a topic description
- Headlines: 8-12 words

---

## Tone

| Do                        | Don't                          |
| ------------------------- | ------------------------------ |
| Curious, engaged          | Breathless, excited            |
| Clear, direct             | Jargon-filled                  |
| Confident but hedged      | Certain about uncertain things |
| Respectful of researchers | Dismissive or sycophantic      |

---

## Words to Avoid

| Avoid                         | Prefer                   |
| ----------------------------- | ------------------------ |
| Revolutionary, groundbreaking | Significant, notable     |
| Breakthrough                  | Finding, result          |
| State-of-the-art              | Best-performing, leading |
| Incredible, amazing           | Surprising, unexpected   |
| Obviously, clearly            | (just state the fact)    |
| Actually, basically           | (just cut them)          |
| Very, really                  | (be specific instead)    |
| Utilize                       | Use                      |
| Leverage                      | Use                      |
| Novel                         | New                      |

---

## Technical Terms

When using technical terms:

**Okay to use without explanation:**

- Machine learning, AI, neural network
- Training, validation, testing
- Model, algorithm
- Dataset, benchmark
- API, GPU

**Require brief explanation:**

- Transformer, attention ("a type of neural network architecture")
- Fine-tuning ("additional training on a specific task")
- Few-shot, zero-shot ("learning from few/no examples")
- Inference ("using a trained model to make predictions")
- Embedding ("numerical representation of text/data")

**Avoid or explain in depth:**

- Gradients, backpropagation
- Specific loss functions
- Architectural details (unless the paper is about architecture)
- Mathematical notation

---

## Citations

Every factual claim must cite a specific location in the paper.

**Format:** `[§X.Y]` for sections, `[Table N]` for tables, `[Figure N]` for figures, `[Abstract]` for abstract.

**Example:**
"The model achieved 92% accuracy on the benchmark, compared to 85% for GPT-4 [Table 3]."

If a claim cannot be cited to a specific passage, it should not be included.

---

## Voice

### Do

- State findings directly. "DCAN achieves 87% accuracy" — not "The paper reports that DCAN achieves 87% accuracy."
- Name limitations concretely. "Four models, four languages, controlled conditions" — not "several limitations deserve attention."
- Frame implications as conditional. "If your organization needs to audit AI-generated code..." — not "This will change how organizations..."
- Use the paper's own hedging when authors hedge. Write "≈" rather than "=" when the paper does this.

### Never

- Use the paper's self-characterizations in Results ("reliable," "significant," "state-of-the-art"). Always give the actual number.
- Speculate beyond the paper's claims in Why It Matters.
- Drop jargon without grounding it within two sentences.
- List more than three model names. "Ten 7B-parameter vision-language models" suffices.
- Explain the same concept twice across sections.

### Anti-patterns (from Issue #1)

- ❌ "The paper states that DCAN achieves 'reliable attribution performance across diverse settings'" → quoting the abstract is not reporting results. Replace with actual numbers.
- ❌ "Memex agent trained with MemexRL improves task success while using a significantly smaller working context" → same problem. How much improvement? How much smaller?
- ❌ Listing ten model names → "Ten 7B-parameter vision-language models" is sufficient for this audience.

---

## Audience Ceiling

Reader profile: Software engineer or PM who uses AI tools daily but does not read papers.

**Knows:** APIs, basic ML concepts (training, validation, models, datasets), statistical terms, GPU.

**Does not know:** transformer internals, attention mechanisms, specific architectures, math notation.

Any concept beyond this ceiling must be explained via analogy or concrete illustration BEFORE the technical name appears, not after.

- ❌ "The model's attention heads attend to query positions..."
- ✅ "Think of it as eye-tracking for the model's internal processing — a score measuring how much of the model's computational focus is directed at the image versus boilerplate instructions (technically: attention head activations across query positions)."

---

## Amendments

This document may only be amended by:

1. Explicit decision logged in DECISIONS.md
2. Clear rationale for the change
3. Version number increment

Style drift through prompt adjustments is not allowed. All style guidance must be in this document.

---

## Checklist (For Generation Pipeline)

Before publishing, verify each feature article:

1. **Hook check:** Does the first sentence state a capability or finding? (Not a method, not a question, not a scene-setter.) If no → rewrite.
2. **Signal block check:** Is the signal block present? Does it cover (a) capability emerging, (b) maturity estimate, (c) what decision it informs? If any missing → add.
3. **Numbers check:** Does The Results section contain at least one specific performance number with interpretable context? If no → revise or flag explicitly in the article.
4. **Audience ceiling check:** Would a senior PM who's never read an ML paper understand every sentence in What They Did? If any sentence requires knowledge of transformer internals, attention, or math notation → rewrite with analogy first.
5. **Abstraction grounding check:** Is every named technique/loss function/metric followed within two sentences by a concrete example or analogy? If no → add one or remove the name.
6. **Limitations dual-frame check:** Is every limitation stated in both technical and production timeline terms? If no → add the production dimension.
7. **Duplicate content check:** Is any concept explained twice across sections? If yes → keep the first instance, cut the second.
8. **Banned words check:** No words from the banned list.
9. **Citation check:** Every factual claim cites a specific passage. Minimum 3 citations.
10. **Length check:** Article is 800-1000 words (hard cap 1000). If over → cut starting with the longest section.
11. **Quick Takes check:** Each Quick Take includes a specific finding or result. No abstract topic descriptions.
12. **Tone check:** Curious, not breathless. Direct, not hedging. No self-characterizations from the abstract.
