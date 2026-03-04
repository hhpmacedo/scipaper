# Technical Decisions Log

This document tracks key technical decisions and their rationale. Each decision includes context, options considered, and the chosen approach.

---

## Open Decisions (Need Resolution)

### DEC-001: LLM Model Selection

**Status:** OPEN  
**Priority:** HIGH  
**Owner:** TBD

**Context:**
The pipeline requires LLM calls at three stages:
1. Narrative potential scoring (curation)
2. Citation-grounded generation
3. Adversarial verification
4. Style consistency check

Each stage has different requirements for quality, cost, and speed.

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| **Claude 3.5 Sonnet for all** | Strong writing, good at verification, consistent | Cost (~$3/piece for 3 passes) |
| **GPT-4o for all** | Strong reasoning, fast | Cost, slightly less nuanced writing |
| **Mixed: Claude for writing, GPT for verification** | Optimized per task | Complexity, potential inconsistency |
| **Open source (Llama 3, Mixtral)** | Low cost, self-hosted | Quality concerns, infrastructure |

**Cost Estimate (3-5 papers/week, 3 passes each):**
- Claude 3.5 Sonnet: ~$10-20/week
- GPT-4o: ~$8-15/week
- Mixed: ~$10-15/week
- Open source: ~$1-2/week (compute only)

**Recommendation:** Start with Claude 3.5 Sonnet for all stages. Quality is critical for launch; optimize later.

**Decision:** TBD

---

### DEC-002: PDF Parsing Strategy

**Status:** OPEN  
**Priority:** HIGH  
**Owner:** TBD

**Context:**
Papers are PDFs. We need to extract:
- Full text with section structure
- Figures and tables (or at least captions)
- Citations and references

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| **PyMuPDF + custom parsing** | Fast, no external deps | Complex papers break, no figure understanding |
| **GROBID** | Academic-focused, structured output | Java dependency, self-hosted |
| **DocAI (Google)** | High quality, handles complex layouts | Cost, API dependency |
| **LlamaParse / Unstructured.io** | Good quality, easy API | Cost, potential quality variance |
| **LLM-based extraction** | Can handle anything | Slow, expensive, may hallucinate structure |

**Recommendation:** 
1. Primary: PyMuPDF for simple extraction
2. Fallback: GROBID for papers that fail PyMuPDF
3. Last resort: LLM extraction for critical papers

**Decision:** TBD

---

### DEC-003: Email Provider Selection

**Status:** OPEN  
**Priority:** MEDIUM  
**Owner:** TBD

**Context:**
Need email delivery for the weekly newsletter.

**Options:**

| Option | Deliverability | API Quality | Cost | Notes |
|--------|----------------|-------------|------|-------|
| **Resend** | Good | Excellent | Free tier generous | Modern, good DX |
| **Postmark** | Excellent | Good | $10/mo for 10k | Deliverability focused |
| **SendGrid** | Good | Okay | Free tier generous | Can get spammy |
| **Buttondown** | Good | Limited | $9/mo | Newsletter-focused, has landing page |
| **ConvertKit** | Good | Okay | Free to 1k | Marketing focused |

**Recommendation:** Start with Buttondown—it's newsletter-focused and includes subscriber management, landing page, and web archive. Can migrate to custom solution later.

**Decision:** TBD

---

### DEC-004: Verification Failure Handling

**Status:** OPEN  
**Priority:** MEDIUM  
**Owner:** TBD

**Context:**
What happens when adversarial verification fails for papers?

**Scenarios:**
1. Single paper fails → Drop from edition
2. Multiple papers fail → Edition is thin
3. All papers fail → No edition this week?

**Options:**

| Option | Pros | Cons |
|--------|------|------|
| **Skip edition** | Maintains quality bar | Inconsistent schedule |
| **Publish with fewer pieces** | Consistent schedule | May seem thin |
| **Human escalation** | Quality check | Defeats autonomous goal |
| **Fallback to "Quick Takes" only** | Something ships | Lower value edition |
| **Curate more papers upfront** | Buffer for failures | More LLM cost |

**Recommendation:** 
1. Curate 8-10 papers instead of 5 to provide buffer
2. If <3 papers pass, publish what passes as "Quick Takes" edition
3. If 0 papers pass, alert human and delay 24 hours for review
4. Track failure rates; if >20% weekly, investigate pipeline issues

**Decision:** TBD

---

## Resolved Decisions

### DEC-000: Project Scope for Phase 1

**Status:** RESOLVED  
**Date:** 2025-03-04

**Decision:** 
Phase 1 is email-only newsletter with web archive. No social, no video, no API.

**Rationale:**
- Email is the core value proposition
- Web archive is trivial to add (static files)
- Other formats can be added once core pipeline is solid

---

## Decision Template

```markdown
### DEC-XXX: [Title]

**Status:** OPEN | RESOLVED | DEPRECATED  
**Priority:** HIGH | MEDIUM | LOW  
**Owner:** [Name or TBD]

**Context:**
[Why this decision needs to be made]

**Options:**
[Table of options considered]

**Recommendation:**
[What we think we should do]

**Decision:**
[Final decision, once made]

**Rationale:**
[Why we chose this option]
```
