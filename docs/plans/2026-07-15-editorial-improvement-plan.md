# Editorial Improvement Plan — Signal

**Date:** 2026-07-15
**Author:** Editorial diagnosis (reader-lens review of #16–#18) + Hugo's product decisions
**Status:** DRAFT — awaiting Hugo's review before Phase 1 spec
**Scope:** How Signal curates and writes, judged by the experience of a typical reader

---

## 1. Method

Read the latest three editions cover to cover as a **typical reader** would — a PM/engineer who uses AI daily, can't read papers, gives Signal 10–15 min on a Tuesday:

- **#18 / 2026-W29** — *Routing AI Agents Through Multiple Models…* (5 features + 5 Quick Takes, 4,568 words)
- **#17 / 2026-W28** — *Even GPT-5 Fails Most Tasks…* (4 features + 5 Quick Takes)
- **#16 / 2026-W27** — *LLM Recommenders Can't Fix What They Never See* (4 features + 5 Quick Takes)

Then traced every reader complaint to the specific pipeline lever that causes it, so each fix is concrete and stays within the **fully-autonomous** constraint.

> Note: the archive page reports "1 pieces" for #16/#17 — that's a display bug in `archive.html`'s piece counter, not an editorial problem. Both issues have 4 features. (Filed as a minor Phase 1 cleanup.)

---

## 2. Diagnosis (reader lens)

### What's genuinely working — protect these
- **Rigor & citation-grounding.** Every claim cites a passage; every piece names what the paper *doesn't* show; numbers always carry a baseline. This is the hardest thing to get right, and Signal nails it.
- **Zero hype.** The Style Constitution is being enforced. It reads like it respects the reader.
- **Layered reading affordance.** The `What they did / Key result / Why it matters` mini-block lets a reader bail early or go deep.
- **Strong hooks.** They state a finding, not a method.

### Where it falls short — and the root cause in code

| # | Reader experience | Root cause (lever) |
|---|---|---|
| D1 | **"A stack of summaries, not an edition."** No throughline, no POV connecting the week. "This week in Signal" is disconnected bullets. | No throughline generator exists. The top bullets are just the pieces' signal-blocks concatenated in `edition.py`. |
| D2 | **Topic monoculture.** ~13 features across 3 issues are almost all LLM agents / RAG / MoE-LoRA internals / tool-use plumbing. No robotics, vision, speech, bio, theory, policy. | `PaperCategory` ingests only `cs.AI, cs.LG, cs.CL, stat.ML` (`curate/models.py`). Nothing else can *ever* surface. Selection's diversity check uses arXiv categories as the topic proxy (`select.py`) — but since everything is already cs.AI/cs.LG, `max_same_topic=2` barely bites. |
| D3 | **Audience slips upward.** "Why It Matters" addresses *"teams building MoE fine-tuning pipelines / MCP servers"* — not the spec's PM/founder. The top-of-issue bullets are the *densest* text in the issue. | Generation prompts default to a builder-infra register; no explicit decision-maker layer is enforced. Top bullets are un-rewritten signal-blocks. |
| D4 | **Template fatigue + self-repetition.** The hook appears **verbatim twice** (hook + figure caption). The same number is restated in hook → "Key result" bullet → Results section. Violates the Constitution's own "no duplicate content" law. | `writer.py` renders the hook as the hero-figure caption; no cross-field dedup pass. |
| D5 | **The "1–2 years from production" tic.** Nearly every limitations section ends with an invented maturity timeline. Reads as filler by piece 3. | `writer.py` prompt *mandates* a "production timeline" on every limitation and a maturity-spectrum sentence in every "Why It Matters." The tic is required, not emergent. |
| D6 | **No relevance signal.** Raw July-2026 preprints (`2607.xxxxx`), zero citations, one of thousands that week. Nothing says *why this paper vs. the 500 others*. A couple of picks feel arbitrary. | Relevance scoring leans on citation-velocity/social signals that are ~0 for days-old preprints; no signal is surfaced to the reader. |
| D7 | **Too long for the promise.** #18 ≈ 4,568 words ≈ 20–25 min vs. the 10–15 min promise; structural layering adds words without adding scannability. | No enforced per-edition length budget; layered structure multiplies restated content (see D4). |

---

## 3. What "great" looks like (for this audience)

A reader should get, in **≤12 minutes**:
1. **A one-paragraph editorial take** on the week with a genuine throughline — the *most* accessible text in the issue, not the densest.
2. **3–5 genuinely varied features** that clearly *matter*, each answering "what can I now do/believe that I couldn't before" and "what does this mean for someone like me."
3. **Relevance signals I can trust** — a credible "why this paper, now."
4. **Less internal repetition, tighter prose**, explicit dual-layer (builder + decision-maker).
5. **Recurring threads that build week over week**, so it feels like an ongoing story, not a nightly cron job.

Reference standard: **The Batch's editorial voice + Quanta's rigor + Import AI's "why it matters to the world."** Signal is ~70% there on rigor, ~20% on curation-as-storytelling.

---

## 4. Decisions locked (Hugo, 2026-07-15)

| Decision | Choice |
|---|---|
| **Scope** | Broaden deliberately — curation spans the field, not just LLM-eng internals. |
| **Reader** | Both, explicitly layered — serve a builder *and* a decision-maker in each piece, done well. |
| **Autonomy** | Keep fully autonomous — every change lives in prompts / Style Constitution / pipeline. No new human step. |
| **Success** | Grow subscribers/engagement — a newsletter people forward, subscribe to, open weekly. |
| **Ambition** | Approach 3 (heaviest) — includes a curation rebuild for real relevance. |
| **Freshness** | Rolling coverage window — a paper can be picked up to ~3–4 weeks after posting, once signal accrues. |
| **Signals** | Full stack — free/community (HF Papers, Papers with Code, alphaXiv, GitHub stars, Reddit), deeper Semantic Scholar, curated lab/author prestige list, **and** paid X/Twitter. |

---

## 5. Cross-cutting design principle: degradable autonomy

The pipeline runs as an autonomous weekly cron. Adding five new external sources (some paid, some interactively-authenticated, some scraped) multiplies failure modes. **Non-negotiable rule for every new source:**

> If a source is unavailable (auth expired, rate-limited, down, absent in headless run), the edition **still ships** using the remaining signals. No single new dependency can block a publish. Each source contributes a *bounded* signal that defaults to neutral (0 weight) on failure, logged but non-fatal.

X/Twitter (paid, highest maintenance) ships **last, behind a feature flag**, only after the free signals prove out.

---

## 6. The plan — three sequenced sub-projects

Decomposed because these are three independent subsystems; sequenced by **reader-impact ÷ effort**. Each phase is independently shippable and independently improves the product. Everything Hugo chose is included — this is sequencing, not scope-cutting.

### Phase 1 — Editorial & writing quality *(ship first)*
**Why first:** highest reader-impact ÷ effort. These are what a reader actually *experiences*, they're cheap, high-certainty, and fully autonomous by construction. A reader cannot perceive how a paper was selected — they perceive the prose.

**Changes (all in prompts + Style Constitution + renderers):**
- **Kill the mandated tics (D5).** Amend `STYLE_CONSTITUTION.md` §Structure and `writer.py`: a production-timeline is included **only when the paper itself supports one**; drop the compulsory "lab proof-of-concept" maturity sentence — allow it, don't mandate it.
- **De-duplicate (D4).** Stop rendering the hook as the hero-figure caption (`writer.py`/`web.py`/`email.py`); write a real caption or none. Add a "state each key number once" rule to the Constitution's dedup law and the style checker (`verify/style.py`).
- **Make dual-layer real (D3).** Rewrite the "Why It Matters" spec so it explicitly serves a **builder** *and* a **non-builder decision-maker** in distinct sentences — not "teams building MoE pipelines" every time.
- **Enforce length (D7).** Per-edition word budget (target ≈ 2,500–3,000 words / ~12 min); add a length gate to the style pass.
- Fix the `archive.html` piece-counter bug.

**Reader-visible outcome:** the very next edition reads tighter, less repetitive, less formulaic, and speaks to the actual reader. **Done-when:** a generated edition passes updated style checks and a blind read shows no verbatim hook/caption/number repetition and no reflexive "1–2 years" filler.

### Phase 2 — Breadth + the editorial layer *(second)*
**Why second:** fixes the two structural reader complaints (monoculture D2, no-POV D1); needs new selection logic + one new generation stage.

**Changes:**
- **Expand the field (D2).** Add categories to `PaperCategory`/ingest: robotics (`cs.RO`), vision (`cs.CV`), speech/audio (`eess.AS`), HCI (`cs.HC`), policy/economics (`cs.CY`), applications (`q-bio`, etc.). Tune `max_papers`/query accordingly.
- **Cross-domain diversity rule (D2).** Strengthen `select.py`: every edition must span **≥3 distinct fields**; map arXiv categories to human-readable "areas" so the constraint actually bites.
- **Editor's Note throughline (D1) — new autonomous stage.** An edition-level LLM pass reads the selected pieces and writes a genuine 60–100-word connective intro with a POV ("what these say together this week"), replacing the dense concatenated bullets. It becomes the *most* accessible text in the issue. Lives in `edition.py`.

**Reader-visible outcome:** issues feel varied and open with a point of view. **Done-when:** editions reliably span ≥3 areas and lead with a throughline a human editor would recognize as one.

### Phase 3 — Relevance engine *(last)*
**Why last:** heaviest, most maintenance, least reader-visible per unit effort — but it's what makes "why this paper" credible and is the ambition Hugo signed up for.

**Changes:**
- **Rolling coverage window.** Maintain a backlog with per-paper state; a paper is eligible for ~3–4 weeks and can be picked once signal accrues. Requires backlog persistence in `data/` + selection changes.
- **Signal stack (each degradable per §5):**
  - *Free/community:* Hugging Face Papers trending, Papers with Code, alphaXiv, GitHub repo stars (of the paper's linked repo), Reddit r/MachineLearning.
  - *Deeper Semantic Scholar:* early citation velocity, influential-citation count, author h-index, reference-graph position.
  - *Curated lab/author prestige list:* a maintained weight list (needs periodic upkeep — accepted).
  - *Paid X/Twitter:* discourse velocity, **behind a flag, wired last.**
- **Surface relevance to the reader.** A short, grounded "why this, now" line per piece (traction/discourse/lab signal), so the reader sees the evidence of curation.
- Rebalance `ScoringConfig` weights now that fast-moving signals are meaningful under a rolling window.

**Reader-visible outcome:** picks feel *chosen*, not scraped; each carries a credible reason it's worth the reader's time. **Done-when:** ≥1 relevance signal per pick is non-trivial and the "why this, now" line is grounded, with the edition still shipping when any source is down.

---

## 7. Sequencing rationale (the proof)

Phase 1, shipped alone, visibly improves the next edition a reader opens — no dependency on Phases 2–3. That's the test that the sequencing is right. Phase 2 needs nothing from Phase 3. Phase 3 is additive. Each phase is a standalone spec → plan → implementation cycle; Phase 1 gets its detailed spec next.

---

## 8. How we'll know it's working (growth)

Tie to the growth goal without adding human steps:
- **Open/forward proxy:** subject-line quality (already `generate_edition_subject`) + a forwardable one-line takeaway per edition.
- **Engagement:** if analytics exist, watch open rate, click-through to papers, and unsubscribe rate across the phase rollouts.
- **Qualitative:** a monthly blind read against the "what great looks like" checklist (§3).

---

## 9. Risks & open items
- **Autonomy vs. new dependencies** — mitigated by §5 (degradable sources). Must be honored in every Phase 3 PR.
- **Prestige list subjectivity/upkeep** — accepted by Hugo; keep it small and version-controlled.
- **Rolling window vs. "weekly feels current"** — monitor that editions don't skew toward stale-but-popular; the diversity + freshness balance may need tuning.
- **Breadth vs. audience ceiling** — new fields (robotics, bio) must still clear the Style Constitution's audience ceiling; the writer prompt may need per-field grounding examples.
- Each phase's amendments to the LOCKED Style Constitution require a `DECISIONS.md` entry + version bump, per its amendment rule.
