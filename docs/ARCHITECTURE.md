# Technical Architecture

**Version:** 0.1.0  
**Last Updated:** 2025-03-04

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SIGNAL PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│   │   INGEST    │───▶│   CURATE    │───▶│  GENERATE   │───▶│   PUBLISH   │ │
│   └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│   │  Paper DB   │    │  Shortlist  │    │   Edition   │    │  Email/Web  │ │
│   └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘ │
│                                                                              │
│   ◄──────────────────────── Runs Weekly ────────────────────────────────►   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Stages

### Stage 1: Ingest

**Responsibility:** Collect papers from all sources, normalize metadata, store locally.

**Runs:** Daily (or on-demand)

```
┌─────────────────────────────────────────────────────────────────┐
│                         INGEST PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│   │  ArXiv    │  │ Semantic  │  │ Twitter/X │  │  HN/Reddit│   │
│   │   API     │  │  Scholar  │  │   API     │  │   APIs    │   │
│   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘   │
│         │              │              │              │          │
│         └──────────────┴──────────────┴──────────────┘          │
│                              │                                   │
│                              ▼                                   │
│                    ┌─────────────────┐                          │
│                    │   Normalizer    │                          │
│                    │  (dedupe, enrich)│                         │
│                    └────────┬────────┘                          │
│                             │                                    │
│                             ▼                                    │
│                    ┌─────────────────┐                          │
│                    │    Paper DB     │                          │
│                    │  (SQLite/JSON)  │                          │
│                    └─────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Data Sources:**

| Source | Data | Rate Limit | Notes |
|--------|------|------------|-------|
| ArXiv API | Papers (cs.AI, cs.LG, cs.CL, stat.ML) | None | Primary source |
| Semantic Scholar | Citations, references, impact | 100/sec | Enrichment |
| Twitter/X | Mentions, engagement | Varies | Social signal |
| Hacker News | Comments, points | None | Social signal |
| Reddit | r/MachineLearning posts | 60/min | Social signal |

**Paper Record Schema:**

```python
@dataclass
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    authors: List[Author]
    categories: List[str]
    published_date: datetime
    pdf_url: str
    
    # Enrichment
    semantic_scholar_id: Optional[str]
    citation_count: int
    reference_count: int
    
    # Social signals
    twitter_mentions: int
    hn_points: int
    reddit_score: int
    
    # Processing state
    ingested_at: datetime
    pdf_parsed: bool
    full_text: Optional[str]
```

---

### Stage 2: Curate

**Responsibility:** Score papers, generate ranked shortlist, select edition papers.

**Runs:** Weekly (before generation)

```
┌─────────────────────────────────────────────────────────────────┐
│                        CURATE PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐           ┌─────────────────┐             │
│   │   Paper DB      │           │ Relevance Anchor│             │
│   │ (this week's)   │           │   Document      │             │
│   └────────┬────────┘           └────────┬────────┘             │
│            │                             │                       │
│            └──────────────┬──────────────┘                       │
│                           │                                      │
│                           ▼                                      │
│              ┌─────────────────────────┐                        │
│              │     Relevance Scorer    │                        │
│              │   (semantic similarity) │                        │
│              └────────────┬────────────┘                        │
│                           │                                      │
│                           ▼                                      │
│              ┌─────────────────────────┐                        │
│              │  Narrative Potential    │                        │
│              │   Scorer (LLM-based)    │                        │
│              └────────────┬────────────┘                        │
│                           │                                      │
│                           ▼                                      │
│              ┌─────────────────────────┐                        │
│              │       Ranker            │                        │
│              │  (composite scoring)    │                        │
│              └────────────┬────────────┘                        │
│                           │                                      │
│                           ▼                                      │
│              ┌─────────────────────────┐                        │
│              │   Diversity Selector    │                        │
│              │   (3-5 papers out)      │                        │
│              └─────────────────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Relevance Anchor Document:**

```yaml
# anchors/2025-W10.yaml
week: 2025-W10
updated_by: hugo
updated_at: 2025-03-03T10:00:00Z

hot_topics:
  - "reasoning models and test-time compute"
  - "multimodal understanding beyond CLIP"
  - "efficient fine-tuning methods"
  - "AI safety and alignment"
  - "code generation benchmarks"

declining_topics:
  - "basic prompt engineering"
  - "GPT wrappers"

boost_keywords:
  - "o1", "o3", "claude", "gemini"
  - "long context", "RAG improvements"
  - "agent", "tool use"

institutions_of_interest:
  - "Anthropic", "OpenAI", "DeepMind", "Meta AI"
  - "Stanford", "MIT", "Berkeley"
```

**Scoring Functions:**

```python
def relevance_score(paper: Paper, anchor: AnchorDocument) -> float:
    """
    1-10 score based on:
    - Semantic similarity to hot_topics
    - Keyword matches
    - Institution signals
    - Citation velocity (recent citations / days since publication)
    - Social signal strength
    """
    
def narrative_potential_score(paper: Paper) -> float:
    """
    1-10 score based on LLM assessment of:
    - Is there a clear problem/solution structure?
    - Is there a surprising or counterintuitive result?
    - Are there concrete examples or demos?
    - Can this be explained without heavy math?
    - Is there a "so what" for practitioners?
    """
```

---

### Stage 3: Generate

**Responsibility:** Produce publication-ready pieces for selected papers.

**Runs:** Weekly (after curation)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GENERATE PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                                                            │
│  │ Paper PDF   │                                                            │
│  └──────┬──────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      PDF PARSER                                      │   │
│  │  (PyMuPDF → GROBID → LLM extraction as fallback)                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 STAGE 1: CITATION-GROUNDED GENERATION                │   │
│  │                                                                       │   │
│  │  System Prompt:                                                      │   │
│  │  - You are writing for Signal publication                            │   │
│  │  - Every factual claim MUST cite a specific passage                  │   │
│  │  - Use format: "claim [§3.2]" or "claim [Abstract]"                  │   │
│  │  - Follow Style Constitution exactly                                 │   │
│  │                                                                       │   │
│  │  Input: Full paper text + Style Constitution                         │   │
│  │  Output: Draft with inline citations                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 STAGE 2: ADVERSARIAL VERIFICATION                    │   │
│  │                                                                       │   │
│  │  System Prompt:                                                      │   │
│  │  - You are a fact-checker for Signal                                 │   │
│  │  - For each citation, verify the claim matches the passage           │   │
│  │  - Flag: unsupported, overstated, misrepresented, missing context   │   │
│  │                                                                       │   │
│  │  Input: Draft + Original paper                                       │   │
│  │  Output: Verification report                                          │   │
│  │                                                                       │   │
│  │  If >2 major issues → REJECT paper                                   │   │
│  │  If 1-2 issues → AUTO-FIX and re-verify (max 2 attempts)            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 STAGE 3: STYLE CONSISTENCY                           │   │
│  │                                                                       │   │
│  │  Checks against Style Constitution:                                  │   │
│  │  - Tone (no hype, no speculation)                                    │   │
│  │  - Structure (hook → problem → approach → results → implications)   │   │
│  │  - Jargon (technical terms explained or avoided)                    │   │
│  │  - Length (800-1200 words)                                           │   │
│  │                                                                       │   │
│  │  Auto-corrects minor issues                                          │   │
│  │  Flags major style violations for manual review                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      EDITION ASSEMBLY                                │   │
│  │                                                                       │   │
│  │  - Order pieces by importance (lead first)                          │   │
│  │  - Generate Quick Takes for runners-up                               │   │
│  │  - Add edition metadata (date, issue number)                        │   │
│  │  - Render to email HTML + plain text + web page                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Verification Report Schema:**

```python
@dataclass
class VerificationReport:
    paper_id: str
    status: Literal["pass", "fail", "needs_revision"]
    
    claims_checked: int
    claims_verified: int
    claims_failed: int
    
    issues: List[VerificationIssue]
    
@dataclass
class VerificationIssue:
    severity: Literal["minor", "major", "critical"]
    claim_text: str
    cited_passage: str
    issue_type: Literal["unsupported", "overstated", "misrepresented", "missing_context"]
    explanation: str
    suggested_fix: Optional[str]
```

---

### Stage 4: Publish

**Responsibility:** Deliver edition to subscribers and web archive.

```
┌─────────────────────────────────────────────────────────────────┐
│                       PUBLISH PIPELINE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐                                           │
│   │  Edition JSON   │                                           │
│   └────────┬────────┘                                           │
│            │                                                     │
│            ├──────────────────┬──────────────────┐              │
│            ▼                  ▼                  ▼              │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│   │ Email Render │   │  Web Render  │   │    RSS/JSON  │       │
│   │  (HTML+text) │   │   (Static)   │   │     Feed     │       │
│   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘       │
│          │                  │                  │                │
│          ▼                  ▼                  ▼                │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│   │   Resend/    │   │   Vercel/    │   │   Static     │       │
│   │   Postmark   │   │   Cloudflare │   │    Host      │       │
│   └──────────────┘   └──────────────┘   └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Stores

| Store | Technology | Purpose |
|-------|------------|---------|
| Paper DB | SQLite | Paper metadata, scores, processing state |
| Paper PDFs | Local filesystem / S3 | Cached paper downloads |
| Paper Full Text | SQLite / JSON | Parsed paper content |
| Editions | JSON files | Generated edition content |
| Subscriber List | Email provider (Resend/Buttondown) | Email delivery |
| Web Archive | Static files (S3/Vercel) | Published editions |

---

## External Services

| Service | Purpose | Required? |
|---------|---------|-----------|
| ArXiv API | Paper discovery | Yes |
| Semantic Scholar API | Citation data, enrichment | Yes |
| Twitter/X API | Social signals | Nice-to-have |
| OpenAI / Anthropic API | LLM for scoring, generation, verification | Yes |
| Resend / Postmark / SendGrid | Email delivery | Yes |
| Vercel / Cloudflare Pages | Web hosting | Yes |

---

## Deployment Architecture

**Phase 1: Simple (MVP)**

```
┌─────────────────────────────────────────┐
│           GitHub Actions                │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Weekly Cron Job                │   │
│  │  - Run curate pipeline          │   │
│  │  - Run generate pipeline        │   │
│  │  - Run publish pipeline         │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

**Phase 2: Robust**

```
┌─────────────────────────────────────────────────────────────────┐
│                       Railway / Fly.io                          │
│                                                                  │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐               │
│  │  Ingest   │    │  Curate   │    │  Generate │               │
│  │  (daily)  │    │  (weekly) │    │  (weekly) │               │
│  └─────┬─────┘    └─────┬─────┘    └─────┬─────┘               │
│        │                │                │                      │
│        └────────────────┼────────────────┘                      │
│                         ▼                                        │
│                  ┌─────────────┐                                │
│                  │  Postgres   │                                │
│                  │  (Paper DB) │                                │
│                  └─────────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Paper PDF fails to download | Retry 3x, then skip paper |
| PDF parsing fails | Try fallback parsers, then skip |
| Verification fails for a paper | Drop from edition, log issue |
| All papers fail verification | Alert, delay edition, escalate to human |
| Email delivery fails | Retry with backoff, alert on persistent failure |
| Rate limit hit | Backoff and retry, spread requests |

---

## Monitoring & Observability

**Metrics to Track:**

- Papers ingested per day/week
- Curation scores distribution
- Verification pass/fail rate
- Generation time per piece
- Email delivery rate
- Open rate, click rate

**Alerts:**

- Verification pass rate < 80% → Alert
- No papers ingested in 48h → Alert
- Email delivery rate < 95% → Alert
- Pipeline failure → Alert

---

## Security Considerations

- API keys stored in environment variables / secrets manager
- No PII in paper processing
- Subscriber emails stored only in email provider
- PDF downloads from trusted sources only (ArXiv)
