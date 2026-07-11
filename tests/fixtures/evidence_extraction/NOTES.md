# Evidence extraction test fixtures — provenance note

**These are synthetic test fixtures, not recorded live model output.**

This sandboxed build session had no `ANTHROPIC_API_KEY` configured, so a
genuine manual live run (as CLAUDE.md and GLASSWING_SPEC.md section 3
Week 4 both require for fixture generation) was not possible here. The
`.response.json` files in this directory were hand-authored to be
schema-valid, plausible responses to the corresponding `.md` source
texts — they exercise the parse-and-validate code path exactly as a real
response would, but they are not evidence that the real
`prompts/extraction/v1.md` prompt against the real model actually
produces output like this.

**Before this agent backs a real engagement:** run a manual, logged live
extraction (`GLASSWING_OFFLINE` unset, real `ANTHROPIC_API_KEY`, per
CLAUDE.md's "Live LLM runs are manual only, operator-initiated, and
logged in docs/live_runs.md") against these same `.md` sources (or real
ones), record the actual response, and either confirm it matches the
shape these synthetic fixtures assume or replace them with the genuine
recorded output. See docs/live_runs.md for the logging template and
current status (no live run logged yet).

## Files

- `model_card_lending.md` — synthetic model card source text (a fictional
  lending pre-approval assistant).
- `model_card_lending.response.json` — synthetic well-formed, high-confidence
  extraction response for the happy-path test.
- `low_confidence.response.json` — synthetic well-formed response with
  confidence/completeness below the 0.75 threshold, for the human-review
  routing test.
- `malformed.response.json` — deliberately invalid (fails
  ExtractedEvidence's schema), for the human-review routing test's other
  branch.
