# Style Constitution

**Version:** 1.0.0  
**Status:** LOCKED  
**Last Updated:** 2025-03-04

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

Every piece must include what the paper *doesn't* show. Be specific.

**Include:**
- What benchmarks were used and their known limitations
- What conditions were tested vs. not tested
- What the authors themselves note as limitations
- Sample sizes and statistical significance where relevant

---

## Structure

Every piece follows this structure:

### 1. Hook (1 sentence)
The surprising thing. Why should the reader keep reading?

### 2. The Problem (2-3 paragraphs)
What were the researchers trying to solve? Why is it hard? Why does it matter?

### 3. What They Did (3-4 paragraphs)
The actual approach, explained concretely. Include:
- The core idea in plain language
- At least one specific example
- What makes this different from previous approaches

### 4. The Results (2-3 paragraphs)
What worked? What didn't? Include:
- Key numbers with context ("85% accuracy, vs. 70% for the previous best")
- Honest assessment of limitations
- What the authors themselves say about caveats

### 5. Why It Matters (1-2 paragraphs)
Implications for practitioners. Stay grounded—no speculation about "changing the world."

### Citations
Inline citations throughout: `[§3.2]`, `[Figure 4]`, `[Abstract]`

---

## Length

- Full pieces: 800-1200 words
- Quick Takes: 100-200 words
- Headlines: 8-12 words

---

## Tone

| Do | Don't |
|----|-------|
| Curious, engaged | Breathless, excited |
| Clear, direct | Jargon-filled |
| Confident but hedged | Certain about uncertain things |
| Respectful of researchers | Dismissive or sycophantic |

---

## Words to Avoid

| Avoid | Prefer |
|-------|--------|
| Revolutionary, groundbreaking | Significant, notable |
| Breakthrough | Finding, result |
| State-of-the-art | Best-performing, leading |
| Incredible, amazing | Surprising, unexpected |
| Obviously, clearly | (just state the fact) |
| Actually, basically | (just cut them) |
| Very, really | (be specific instead) |
| Utilize | Use |
| Leverage | Use |
| Novel | New |

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

## Amendments

This document may only be amended by:
1. Explicit decision logged in DECISIONS.md
2. Clear rationale for the change
3. Version number increment

Style drift through prompt adjustments is not allowed. All style guidance must be in this document.

---

## Checklist (For Generation Pipeline)

Before publishing, verify:

- [ ] Hook contains one surprising thing
- [ ] No hype words from banned list
- [ ] All technical terms explained or on "okay" list
- [ ] Every factual claim has citation
- [ ] Limitations section is present and specific
- [ ] Length is 800-1200 words
- [ ] Structure follows template exactly
- [ ] Tone is curious, not breathless
