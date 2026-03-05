# Technical Decisions Log

This document tracks key technical decisions and their rationale. Each decision includes context, options considered, and the chosen approach.

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

### DEC-001: LLM Model Selection

**Status:** RESOLVED
**Date:** 2026-03-05

**Decision:** Claude Sonnet for all pipeline stages (scoring, generation, verification, style checking). Optimize per-stage model selection later once baseline quality is established.

**Rationale:** Quality is critical for launch. Using a single model reduces complexity and keeps behavior consistent across stages. Cost (~$10-20/week) is acceptable at current scale.

---

### DEC-002: PDF Parsing Strategy

**Status:** RESOLVED
**Date:** 2026-03-05

**Decision:** Fallback chain: PyMuPDF (primary) → GROBID (fallback) → LLM extraction (last resort).

**Rationale:** PyMuPDF handles most papers with no external dependencies. GROBID provides academic-specific structured output for complex papers. LLM extraction is the safety net for critical papers that both fail on.

---

### DEC-003: Email Provider Selection

**Status:** RESOLVED
**Date:** 2026-03-05

**Decision:** Buttondown as the email/newsletter provider.

**Rationale:** Newsletter-focused platform that includes subscriber management, landing page, and web archive out of the box. Reduces scope of publishing and launch phases. $9/mo is acceptable. Can migrate to a custom solution later if needed.

---

### DEC-004: Verification Failure Handling

**Status:** RESOLVED
**Date:** 2026-03-05

**Decision:**

1. Curate 8-10 papers (not 5) to provide a buffer for verification failures
2. If <3 papers pass verification, publish what passes as a "Quick Takes" edition
3. If 0 papers pass, alert human and delay 24 hours for manual review
4. Track failure rates weekly; if >20% fail, investigate pipeline issues

**Rationale:** Over-curating provides a natural buffer without requiring human intervention in the common case. The Quick Takes fallback ensures something ships every week. Human escalation is reserved for the rare total-failure scenario.

---

### DEC-005: Email Content Strategy

**Status:** RESOLVED
**Date:** 2026-03-05

**Decision:** Hybrid approach — lead piece in full, secondary pieces as preview (hook + first paragraph) with "Read more" link to web archive. Quick Takes remain as-is (already short).

**Rationale:** Full-content emails risk Gmail clipping (~102KB limit) and are 3,000-6,000 words. Hybrid gives immediate value (lead piece rewards the open), drives traffic to the web archive (SEO, analytics, future monetization), and keeps the email digestible. Matches patterns used by successful newsletters.

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
