# Slothcast

A deadline-risk forecast for your own planned work. It tells you the chance tomorrow's plan slips, then shrinks the plan so a bad day still counts for something.

**Local-first.** By default, your behaviour data stays on your machine: TabPFN runs locally and a local Gemma (via Ollama) writes the plan. The optional hosted habit coach sends only aggregated check-in statistics (not task names) to the provider you configure. The LLM is never allowed to produce a probability.

```
nightly check-in ─┐
GitHub commits ───┼─> labels ─> leakage-free features ─> data-sufficiency gate
backfilled history┘                                         │
                                             TabPFN (local) vs baselines
                                                            │
                         risk label ─> local Gemma plan (guardrailed) ─> briefing / dashboard
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
make install                # core deps + pytest
make test                   # 40 tests
make sample                 # synthetic demo log (tagged synthetic)
make eval-sample            # chronological evaluation -> results/
make demo                   # dashboard (opens on synthetic data until you have a real log)
```

### Add TabPFN (the point of the project)

```bash
make install-tabpfn
```
Then accept Prior Labs' model license for the open weights (see their docs / platform.priorlabs.ai); the first fit downloads the weights, after that it runs offline. The weights are non-commercial: fine for research, evaluation and a portfolio, not for a product. Code in this repo is MIT; the weights are not covered by it.

`SLOTHCAST_TABPFN_MODE=client` uses Prior Labs' hosted API instead. Your rows leave your machine then, so it is off by default.

### Add the local planner

Install [Ollama](https://ollama.com), then `ollama pull gemma3:4b` (or set `SLOTHCAST_GEMMA_MODEL` to any Gemma tag you prefer). If Ollama is not running, Slothcast falls back to a deterministic template plan and says so.

### Optional hosted habit coach

Copy `.env.example` to `.env` and set `SLOTHCAST_LLM_BASE_URL`, `SLOTHCAST_LLM_API_KEY`, and `SLOTHCAST_LLM_MODEL` for an OpenAI-compatible provider. The coach sends aggregate completion counts, rates, pattern groups, and existing insights only when you request coaching. Task names are not sent. Without all three settings, numerical habit forecasts continue to work and the coach remains unavailable. Keep provider credentials in the backend environment; never put them in frontend code.

## Your data

Copy `.env.example` to `.env`. Real logs live in `data/raw/` (gitignored).

```bash
slothcast log --task "DSA block" --minutes 120 --deadline-days 3 --energy 3   # evening: plan tomorrow
slothcast done --date 2026-10-22 --done 1                                     # next day: did it happen?
slothcast ingest-github --user YOUR_NAME                                      # optional commit counts
slothcast import-csv old_milestones.csv                                       # backfill (defaults to "inferred")
slothcast eval                                                                # compare models on YOUR history
slothcast forecast --task "DSA block" --minutes 120 --deadline-days 3 --energy 3
```

`checkins.csv` columns: `date, planned_task, planned_minutes, days_to_deadline, energy_1_5, completed_0_1, label_source`
(`label_source`: `verified` you recorded it, `inferred` derived, `synthetic` demo data). Blank `completed_0_1` means "not known yet".

## Honesty rules built into the code

- **No fake certainty.** Under 15 labelled days (or fewer than 4 of either outcome) it shows "Not enough history yet" instead of a probability. 15-29 days is labelled preliminary.
- **No leakage.** Features for day *i* only see outcomes before day *i*. Evaluation is rolling-origin, never shuffled. Both are unit-tested.
- **Baselines included.** Base rate, "same as yesterday", weekday rate, logistic regression, random forest. TabPFN has to beat them. `results.md` reports Brier score, calibration, a learning curve by history length, and a bootstrap interval for the gain over the base rate. If TabPFN does not win, the report says so.
- **Labels keep their provenance.** Commits can only *infer* a label for a day you left blank, and it is tagged `inferred`. Results are also reported on verified labels alone when there are enough.
- **The LLM never writes numbers.** `agent/guardrails.py` rejects any percentage, decimal probability or odds that the model did not produce, and falls back to the template.
- **Synthetic data is always flagged** in the dashboard and in `results.md`.

What this project does not show: that the nudges change behaviour. That needs an A/B period (nudged vs not-nudged weeks), which you can only run after the forecast works.

## Layout

```
src/slothcast/
  ingest/        checkin.py github.py backfill.py
  labels.py features.py sufficiency.py demo_data.py
  models/        baselines.py tabpfn_model.py common.py
  evaluate/      splits.py metrics.py learning_curve.py report.py
  agent/         planner.py prompts.py guardrails.py
  workflows/     Temporal: activities.py workflow.py worker.py   (optional)
  observability.py   Sentry spans / local trace log               (optional)
  pipeline.py cli.py app/main.py
tests/           leakage, labels, sufficiency, guardrails, metrics, ingest, pipeline, dashboard
docs/            post_outline.md
```

## Optional integrations

| Piece | Setup |
|---|---|
| Temporal nightly run | `pip install -e ".[temporal]"`, `temporal server start-dev`, `slothcast set-plan ...`, then `python -m slothcast.workflows.worker` (+ `--run-once` or `--schedule`) |
| Sentry tracing | `pip install -e ".[sentry]"`, set `SENTRY_DSN`. Spans carry timings and token counts, never task text. `SLOTHCAST_TRACE=1` also writes `results/traces.jsonl` |
| Dashboard hosting | `streamlit run src/slothcast/app/main.py` on Render / DigitalOcean / any host. Hosted TabPFN or LLM calls change your privacy story, so describe that honestly |

## License

MIT for the code. TabPFN weights: Prior Labs' license.
