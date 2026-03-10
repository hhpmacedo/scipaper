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

### DEC-006: Dual-Depth Article Architecture (Style Constitution v1.1)

**Status:** RESOLVED
**Date:** 2026-03-07

**Decision:** Upgrade the article format, writing prompt, scoring, and QA pipeline to serve both builders and executives without creating separate content versions.

**Changes implemented:**

1. **Article structure:** Added Signal Block (2-3 sentence executive off-ramp between hook and body). Added Issue Summary at top of each edition (one line per piece from signal_block). Updated hook rule: capability/finding only, never a method description.

2. **Writing prompt (GENERATION_SYSTEM_PROMPT):** Rewrote with hard rules: require specific performance number in Results; enforce audience ceiling (no transformer/attention internals without analogy-first explanation); ground every abstraction within two sentences; cap at 1000 words with section budgets; dual-frame every limitation (technical + production timeline). Added voice rules and anti-patterns from Issue #1.

3. **Paper scoring (NARRATIVE_POTENTIAL_PROMPT):** Replaced 5-criterion rubric with 4-criterion rubric weighted by impact: surprise factor (30%), concreteness (25%), practitioner relevance (25%), results reportability (20%). Papers with vague results sections now penalized.

4. **Style checker (verify/style.py):** Added `check_hook_form` (rejects method-description hooks), `check_numbers_in_results` (requires specific metric in Results), `check_signal_block` (requires signal block). Lowered word cap from 1200 to 1000.

5. **Quick Takes (edition.py):** Upgraded from abstract-first-sentence fallback to LLM-generated one-liners using Haiku. Prompt requires specific finding, not topic description.

6. **Style Constitution:** Bumped to v1.1.0. Added Signal Block spec, hook rule, numbers rule, dual-frame limitations rule, audience ceiling, voice rules + anti-patterns, updated section budgets, upgraded checklist to 12 items.

**Rationale:** Issue #1 evaluation revealed consistent quality gaps: hooks that describe methods rather than findings, Results sections without numbers, jargon above the audience ceiling, abstractions not grounded, Quick Takes that describe topics rather than findings. These are systemic — they trace back to implicit standards in the original prompt. Making them explicit and machine-checkable ensures they hold across issues without human review.

The dual-depth architecture (builder path + executive path through the same article) requires no separate content — just a Signal Block and a restructured hook. The cost is ~60 additional words per article.

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
