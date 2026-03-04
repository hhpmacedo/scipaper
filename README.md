# Signal — AI Research for the Curious

> Automated weekly publication that curates AI research papers and translates them into high-quality plain-language pieces for technically literate non-researchers.

## What This Is

Signal is a **fully autonomous content pipeline** that:
1. **Curates** the most relevant + narratively compelling AI research papers
2. **Translates** them into rigorous but accessible prose
3. **Publishes** weekly via email (with web archive)

No human review step. Quality enforced through citation-grounding and adversarial verification.

## For Whom

Developers, PMs, and business folks who *use* AI but can't read papers. They want to understand what's happening — not just what to think about it.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Add your API keys: OPENAI_API_KEY, SEMANTIC_SCHOLAR_KEY, etc.

# Run curation pipeline
python -m signal.curate

# Generate this week's edition
python -m signal.generate

# Publish
python -m signal.publish
```

## Project Structure

```
scipaper/
├── docs/                    # Project documentation
│   ├── PRODUCT_SPEC.md     # Full product specification
│   ├── ARCHITECTURE.md     # Technical architecture
│   ├── STYLE_CONSTITUTION.md # Locked writing guidelines
│   └── DECISIONS.md        # Key technical decisions log
├── signal/                  # Main Python package
│   ├── curate/             # Curation pipeline
│   ├── generate/           # Content generation pipeline
│   ├── verify/             # Adversarial verification
│   ├── publish/            # Publishing (email, web)
│   └── config/             # Configuration management
├── templates/              # Email and web templates
├── data/                   # Local data store
│   ├── papers/            # Cached paper metadata
│   ├── editions/          # Generated editions
│   └── anchors/           # Relevance anchor documents
├── tests/                  # Test suite
└── scripts/               # Utility scripts
```

## Documentation

- [Product Spec](docs/PRODUCT_SPEC.md) — Vision, audience, success metrics
- [Architecture](docs/ARCHITECTURE.md) — Technical design and pipelines
- [Style Constitution](docs/STYLE_CONSTITUTION.md) — Writing guidelines (version-controlled)
- [Decisions](docs/DECISIONS.md) — Key technical decisions and rationale

## License

MIT
