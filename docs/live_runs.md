# Live LLM run log

CLAUDE.md: "Live LLM runs are manual only, operator-initiated, and
logged in `docs/live_runs.md` with date, purpose, prompt version, model
ID, and approximate token count." Never run in CI; never required for
the offline test suite to pass.

## Log

_No live run has been logged yet._ The Evidence Extraction Agent
(GLASSWING_SPEC.md section 3, Week 4) was built and tested entirely
against synthetic, hand-authored fixtures
(tests/fixtures/evidence_extraction/, see that directory's NOTES.md) —
this sandboxed build session had no `ANTHROPIC_API_KEY` configured, so no
genuine live call was possible here.

**Before relying on this agent for a real engagement:** run a manual
live extraction against `prompts/extraction/v1.md`, record it below, and
compare its actual output shape against the synthetic fixtures currently
committed — replace them with genuine recorded output if they diverge.

### Entry template

```
- Date:
- Purpose:
- Prompt version: prompts/extraction/v1.md
- Model ID:
- Approx. token count (in/out):
- Source document:
- Notes:
```
