# Product Specification: Signal

**Version:** 0.1.0  
**Last Updated:** 2025-03-04  
**Owner:** Hugo Macedo

---

## Executive Summary

Signal is a weekly automated publication that curates AI research papers and translates them into high-quality, plain-language pieces. The entire pipeline — from paper discovery to publication — runs autonomously with no human review step.

Quality is ensured through **citation-grounding** (every claim anchored to paper passages) and **adversarial verification** (a second LLM checks for unsupported claims).

---

## Vision

**For the technically curious who can't read papers.**

AI research moves too fast for most people to follow. Papers are dense, jargon-filled, and assume reader expertise. Yet the ideas in these papers will reshape industries within months.

Signal bridges this gap: rigorous translation without dumbing down.

---

## Target Audience

### Primary: Technically Literate Non-Researchers

- **Profile:** Software engineers, PMs, founders, tech-adjacent business people
- **AI Relationship:** Use AI tools daily, follow AI news, but don't read papers
- **Need:** Understand what's actually happening in AI research, not just headlines
- **Time Budget:** 10-15 minutes per week for this content

### What They Want

| Want | Don't Want |
|------|------------|
| Understand the actual contribution | Hype and speculation |
| Concrete examples and implications | Abstract theorizing |
| Honest about limitations | Cherry-picked results |
| Respects their intelligence | Dumbed-down explanations |

### Success Signal

> "I feel like I actually understand what this paper did, and I can explain it to someone else."

---

## Product Definition

### Format: Weekly Email Newsletter

- **Frequency:** Weekly (Tuesday delivery)
- **Length:** 3-5 pieces per edition, ~800-1200 words each
- **Structure:** Email-first, web archive for searchability

### Each Piece Contains

1. **The Hook:** One surprising thing from this paper (first sentence)
2. **The Problem:** What were they trying to solve?
3. **The Approach:** What did they actually do? (concrete, not abstract)
4. **The Results:** What worked? What didn't?
5. **The Implications:** Why should the reader care?
6. **Citations:** Links to source passages in the paper

### Edition Structure

1. **Lead piece:** Most important/interesting paper of the week
2. **2-3 secondary pieces:** Strong papers with good narrative potential
3. **Quick Takes:** 1-2 paragraph summaries of notable papers that didn't make the cut

---

## Core Pipelines

### 1. Curation Pipeline

**Goal:** Find the 3-5 papers worth writing about this week.

**Data Sources:**
- ArXiv API (cs.AI, cs.LG, cs.CL, stat.ML)
- Semantic Scholar API (citations, references)
- Social monitoring (Twitter/X, Hacker News, Reddit r/MachineLearning)

**Scoring (Two Axes):**

| Axis | Definition | Signals |
|------|------------|---------|
| **Relevance** (1-10) | How important to current AI discourse | Anchor document match, citation velocity, social mentions |
| **Narrative Potential** (1-10) | How compelling a story can we tell | Clear problem/solution, surprising result, concrete examples |

**Process:**
1. Pull new papers from sources (daily)
2. Score each on both axes
3. Generate ranked shortlist (~15-20 papers)
4. Select top 3-5 with diversity (different topics, labs, paper types)

**Human Input:**
- **Relevance Anchor Document:** Weekly-updated list of current discourse topics
- Time commitment: ~30 minutes/week
- This is the ONLY human input in the entire system

### 2. Content Generation Pipeline

**Goal:** Turn a paper into a Signal piece, fully autonomously.

**Stage 1: Citation-Grounded Generation**
- Read full paper (PDF → parsed text)
- Generate piece where every claim is anchored to a specific passage
- Output: Draft with inline citations

**Stage 2: Adversarial Verification**
- Second LLM reads draft + original paper
- Checks each claim against its cited passage
- Flags: unsupported claims, misrepresentations, overstatements
- Output: Verification report (pass/fail + issues)

**Stage 3: Style Consistency**
- Third pass against Style Constitution
- Checks: tone, structure, jargon, hype
- Auto-corrects minor issues, flags major ones

**Stage 4: Publish**
- If verification passes → publish
- If verification fails → drop paper from edition, log issue

### 3. Publishing Pipeline

**Email:**
- Rendered HTML email
- Plain text fallback
- Provider: TBD (Resend, Postmark, SendGrid)

**Web Archive:**
- Static site with all past editions
- Full-text search
- Direct links to original papers

---

## Style Constitution

See [STYLE_CONSTITUTION.md](STYLE_CONSTITUTION.md) for the full locked artifact.

**Core Principles:**
- Quanta Magazine level rigor
- Zero hype, zero speculation
- Concrete > abstract
- Reader is intelligent but not technical
- Every piece needs one surprising thing

---

## Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Accuracy without human review** | Citation-grounding + adversarial verification |
| **Style drift over time** | Version-controlled Style Constitution |
| **Relevance anchor staleness** | Weekly human update (~30 min) |
| **Paper parsing failures** | Multiple PDF parsers, fallback strategies |
| **LLM hallucination** | Strict citation requirements, verification pass |
| **Cost blowup** | Budget alerts, model selection strategy |

---

## Success Metrics

### Phase 1 (Months 1-3)

| Metric | Target |
|--------|--------|
| Email open rate | >45% |
| Adversarial verification pass rate | >90% |
| Reader unsubscribe rate | <2% per month |
| Researcher validation | Researchers share pieces about their field without corrections |

### Phase 2 (Months 4-6)

| Metric | Target |
|--------|--------|
| Subscriber count | 5,000+ |
| Click-through to papers | >15% |
| Reader replies/feedback | >1% of readers |

---

## Open Questions

### Must Resolve Before Building

1. **Model selection:** Which LLMs for each stage? Cost vs. quality tradeoffs.
2. **PDF parsing:** How to reliably extract text/figures from papers?
3. **Failure modes:** What happens when verification fails for all papers in a week?

### Can Resolve Later

1. **Monetization:** Subscription, sponsorship, API access, or free forever?
2. **Format expansion:** Web, podcast/audio, video narration, social threads?
3. **Human override:** Should there be an optional human review step?

---

## Non-Goals (For Now)

- Real-time alerts (we're weekly)
- Paper summarization API (we're a publication)
- Interactive Q&A about papers (we're one-way)
- Coverage of non-AI research (we're focused)

---

## Competitive Landscape

| Competitor | Differentiator |
|------------|----------------|
| **The Batch** (DeepLearning.AI) | More opinionated, human-curated |
| **Import AI** | More industry/policy focused |
| **Papers With Code** | Reference, not narrative |
| **AI Twitter/X** | Noisy, hype-prone |

**Signal's Niche:** Rigor of academic translation + accessibility of journalism + consistency of automation.

---

## Appendix: Example Piece Structure

```markdown
# [Paper Title] — [One-Line Hook]

**Paper:** [Link to ArXiv]  
**Authors:** [Names], [Institution]

[Lead paragraph: The surprising thing. Why this matters.]

## The Problem

[2-3 paragraphs: What were they trying to solve? Why is it hard?]

## What They Did

[3-4 paragraphs: The actual approach. Concrete, not abstract. 
 Includes specific examples where possible.]

## The Results

[2-3 paragraphs: What worked, what didn't. Honest about limitations.
 Includes key numbers with context.]

## Why It Matters

[1-2 paragraphs: Implications for the reader's world.
 Grounded, not speculative.]

---

*Citations: [Inline links to specific paper passages throughout]*
```
