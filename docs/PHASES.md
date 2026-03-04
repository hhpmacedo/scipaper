# Development Phases

This document breaks down Signal into buildable phases with clear milestones.

---

## Phase 0: Foundation (Week 1)
**Goal:** Basic infrastructure and manual proof-of-concept

### Deliverables
- [ ] Project structure and dependencies set up
- [ ] ArXiv API integration (fetch papers)
- [ ] Basic PDF parsing (PyMuPDF)
- [ ] Manual test: Download 5 papers, parse to text

### Technical Tasks
1. Set up Python environment with dependencies
2. Implement `ArxivSource.fetch()` 
3. Implement basic `parse_paper_pdf()` with PyMuPDF
4. Create simple CLI: `python -m signal.curate --fetch`
5. Write tests for ArXiv API and PDF parsing

### Success Criteria
- Can fetch this week's papers from ArXiv (cs.AI, cs.LG, cs.CL, stat.ML)
- Can extract text from >80% of papers
- All tests pass

### Estimated Effort
- 3-4 days development
- 1 day testing and fixes

---

## Phase 1: Curation MVP (Week 2)
**Goal:** Automated paper scoring and selection

### Deliverables
- [ ] Relevance scoring (embeddings + anchor document)
- [ ] Narrative potential scoring (LLM-based)
- [ ] Paper selection with diversity
- [ ] First anchor document created

### Technical Tasks
1. Implement `score_relevance()` with sentence-transformers
2. Implement `score_narrative_potential()` with Claude/GPT
3. Implement `select_edition_papers()` with diversity constraints
4. Create anchor document format and first week's anchor
5. Build curation CLI: `python -m signal.curate --score --select`

### Dependencies
- Phase 0 complete
- LLM API key (Anthropic or OpenAI)

### Success Criteria
- Given 100+ papers, can rank and select 5 with diversity
- Relevance scores correlate with human judgment (spot check)
- Narrative potential scores make sense (spot check)

### Estimated Effort
- 4-5 days development
- 2 days tuning and validation

---

## Phase 2: Generation MVP (Week 3-4)
**Goal:** Citation-grounded content generation

### Deliverables
- [ ] Full paper text extraction (improved parsing)
- [ ] Citation-grounded generation prompt
- [ ] Basic piece generation
- [ ] First manually-verified pieces

### Technical Tasks
1. Improve PDF parsing (add GROBID fallback)
2. Implement `generate_piece()` with citation grounding
3. Implement `extract_citations()` and `validate_citations()`
4. Build generation CLI: `python -m signal.generate --paper <arxiv_id>`
5. Generate 3 pieces and manually verify quality

### Dependencies
- Phase 1 complete
- Style Constitution finalized

### Success Criteria
- Generated pieces follow Style Constitution
- >80% of citations are valid references
- Manual review: "Would I publish this?" answer is "yes, with minor edits"

### Estimated Effort
- 5-6 days development
- 3-4 days iteration on prompts

---

## Phase 3: Verification MVP (Week 5)
**Goal:** Adversarial verification pipeline

### Deliverables
- [ ] Verification checker implementation
- [ ] Auto-fix for minor issues
- [ ] Full pipeline: curate → generate → verify
- [ ] Verification metrics tracking

### Technical Tasks
1. Implement `verify_piece()` with verification prompts
2. Implement `attempt_auto_fix()` for minor issues
3. Build verification CLI: `python -m signal.verify --piece <id>`
4. Track verification pass rates
5. Tune thresholds (what counts as pass/fail?)

### Dependencies
- Phase 2 complete

### Success Criteria
- Verification catches planted errors (test with intentional mistakes)
- Pass rate >85% for well-generated pieces
- Auto-fix resolves >50% of minor issues

### Estimated Effort
- 4-5 days development
- 2 days tuning

---

## Phase 4: Publishing MVP (Week 6)
**Goal:** End-to-end edition publishing

### Deliverables
- [ ] Edition assembly (ordering, formatting)
- [ ] Email rendering (HTML + plain text)
- [ ] Web archive static pages
- [ ] First test edition sent

### Technical Tasks
1. Implement `assemble_edition()` 
2. Create email templates (Jinja2)
3. Integrate email provider (Resend/Buttondown)
4. Create static site generator for archive
5. Build publish CLI: `python -m signal.publish --edition <week>`

### Dependencies
- Phase 3 complete
- Email provider account
- Domain for web archive

### Success Criteria
- Can generate complete edition from curation → publish
- Email renders correctly in major clients
- Web archive is searchable

### Estimated Effort
- 4-5 days development
- 1-2 days testing across email clients

---

## Phase 5: Automation & Monitoring (Week 7)
**Goal:** Fully automated weekly runs

### Deliverables
- [ ] GitHub Actions workflow for weekly run
- [ ] Monitoring and alerting
- [ ] Error handling and recovery
- [ ] First automated edition

### Technical Tasks
1. Create GitHub Actions workflow
2. Add structured logging throughout
3. Set up alerts (email/Slack) for failures
4. Implement retry logic for transient failures
5. Create ops runbook

### Dependencies
- Phase 4 complete
- GitHub Actions secrets configured

### Success Criteria
- Weekly run executes without intervention
- Failures alert within 15 minutes
- Can manually retry/resume failed runs

### Estimated Effort
- 3-4 days development
- 1 week of monitoring the first few runs

---

## Phase 6: Polish & Launch (Week 8)
**Goal:** Ready for public subscribers

### Deliverables
- [ ] Landing page with signup
- [ ] Welcome email sequence
- [ ] First public edition
- [ ] Basic analytics

### Technical Tasks
1. Create landing page (simple, hosted on same domain)
2. Implement subscriber signup flow
3. Create welcome email
4. Add open rate / click tracking
5. Write launch announcement

### Dependencies
- Phase 5 complete
- At least 2 successful automated runs

### Success Criteria
- Signup flow works
- Can track basic metrics
- First 10 subscribers onboarded

### Estimated Effort
- 3-4 days development
- Ongoing iteration

---

## Future Phases (Post-Launch)

### Phase 7: Social Signals
- Twitter/X API integration
- Hacker News monitoring
- Reddit r/MachineLearning

### Phase 8: Scale & Optimize
- Cost optimization (model selection per task)
- Caching and efficiency
- Parallel processing

### Phase 9: Format Expansion
- Audio narration (TTS)
- Social thread generation
- RSS/JSON feed

### Phase 10: Monetization
- Paid tier exploration
- Sponsor integration
- API access

---

## Risk Mitigation by Phase

| Phase | Key Risk | Mitigation |
|-------|----------|------------|
| 0 | PDF parsing failures | Multiple parsers, fallback chain |
| 1 | Bad relevance scoring | Human validation, anchor tuning |
| 2 | Hallucinated content | Citation grounding, strict prompts |
| 3 | Verification misses errors | Test with planted errors, human spot checks |
| 4 | Email deliverability | Use reputable provider, warm up domain |
| 5 | Silent failures | Aggressive alerting, daily checks initially |
| 6 | No subscribers | Pre-launch list building, soft launch |

---

## Rough Timeline

```
Week 1:  [Phase 0 - Foundation]
Week 2:  [Phase 1 - Curation]
Week 3:  [Phase 2 - Generation    ]
Week 4:  [Phase 2 continued       ]
Week 5:  [Phase 3 - Verification]
Week 6:  [Phase 4 - Publishing]
Week 7:  [Phase 5 - Automation]
Week 8:  [Phase 6 - Launch]
         ↓
         First public edition
```

**Total time to first public edition: ~8 weeks**

This assumes:
- One person working ~half-time
- No major blockers
- LLM APIs work as expected
- PDF parsing doesn't require extensive custom work
