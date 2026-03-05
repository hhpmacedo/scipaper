# Signal Operations Runbook

## Weekly Pipeline

The pipeline runs automatically every Sunday at 18:00 UTC via GitHub Actions.

### Manual Trigger

1. Go to Actions tab in GitHub
2. Select "Weekly Edition" workflow
3. Click "Run workflow"
4. Optionally specify a week override (e.g., `2025-W10`)

### Local Run

```bash
export ANTHROPIC_API_KEY=...
export BUTTONDOWN_API_KEY=...
python -m scipaper --run --week 2025-W10
```

Use `--json-logs` for structured JSON output (used in CI).

## Failure Handling (DEC-004)

| Scenario                     | Pipeline Behavior                              | Human Action                                    |
| ---------------------------- | ---------------------------------------------- | ----------------------------------------------- |
| 1-2 papers fail verification | Dropped, edition proceeds with remaining       | None                                            |
| <3 papers pass               | Quick Takes edition published                  | Review why papers failed                        |
| 0 papers pass                | Pipeline exits with error (code 1), no edition | Review within 24h, manually re-run or skip week |
| >20% weekly failure rate     | Logged as warning                              | Investigate prompt/model issues                 |

## Common Issues

### "No anchor documents found"

Create an anchor file in `data/anchors/<week>.yaml`. See existing files for format.

### "Buttondown API key required"

Set `BUTTONDOWN_API_KEY` environment variable or GitHub Actions secret.

### Pipeline times out (>30 min)

- Check if ArXiv API is slow (retry usually helps)
- Check if LLM API is rate-limited (check Anthropic dashboard)
- Reduce `max_papers` in IngestConfig

### Verification rejects everything

- Check if paper full text was extracted properly
- Review verification prompts for overly strict criteria
- Try a single paper locally to isolate the issue

## Monitoring

- GitHub Actions logs: Actions tab -> Weekly Edition -> latest run
- JSON logs available with `--json-logs` flag
- Pipeline timing logged at end of each stage
- Failure notifications via GitHub Actions error annotations
