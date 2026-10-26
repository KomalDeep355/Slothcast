# 🦥 Slothcast

**A deadline-risk forecast for your own planned work.**
It tells you the chance tomorrow's plan slips, then shrinks the plan so a bad day still counts for something.

**Live app:** https://slothcast.onrender.com · **Code:** MIT · **Tests:** 40

---

## Table of contents

- [Why Slothcast exists](#why-slothcast-exists)
- [What it does](#what-it-does)
- [Local-first by design](#local-first-by-design)
- [How it works](#how-it-works)
- [Quickstart](#quickstart)
- [Add TabPFN](#add-tabpfn)
- [Add the local planner (Gemma)](#add-the-local-planner-gemma)
- [Using it with your own data](#using-it-with-your-own-data)
- [CLI reference](#cli-reference)
- [Data format](#data-format)
- [Honesty rules built into the code](#honesty-rules-built-into-the-code)
- [Evaluation](#evaluation)
- [Configuration](#configuration)
- [Optional integrations](#optional-integrations)
- [Deployment](#deployment)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Privacy](#privacy)
- [What this project does not show](#what-this-project-does-not-show)
- [License](#license)

---

## Why Slothcast exists

Most productivity tools record what you finished. None of them tell you what you are about to postpone.

Slothcast started from a personal habit of procrastination and a simple question: if I log what I plan to do and what actually happens, can a model learn when my plans are likely to slip, and can that warning arrive early enough to help?

The goal is not to shame anyone. A procrastination forecast works like a weather forecast: it does not stop the rain, but it tells you to carry an umbrella. Here, the umbrella is a smaller, more realistic plan.

## What it does

- **Forecasts the risk** that a planned task slips, from its planned duration, how close its deadline is, and your expected energy.
- **Shrinks the plan** for risky tasks into a smaller, concrete first step, written by a local Gemma model.
- **Learns from your own history** instead of generic averages.
- **Refuses to guess.** If there isn't enough history, it says "Not enough history yet" instead of showing a made-up probability.
- **Compares models honestly.** TabPFN has to beat five simple baselines on your data, and the report says so if it doesn't.
- **Keeps your data on your machine** by default.

## Local-first by design

By default, your behaviour data stays on your machine:

- **TabPFN runs locally.** After the first download of the open weights, it works offline.
- **A local Gemma model (via Ollama) writes the plan.**
- **The LLM is never allowed to produce a probability.** The forecast comes from a tested model. The language model only turns it into words.

The optional hosted habit coach sends only aggregated check-in statistics (never task names) to the provider you configure, and only when you ask for coaching.

## How it works

```
nightly check-in ─┐
GitHub commits ───┼─> labels ─> leakage-free features ─> data-sufficiency gate
backfilled history┘                                         │
                                             TabPFN (local) vs baselines
                                                            │
                         risk label ─> local Gemma plan (guardrailed) ─> briefing / dashboard
```

1. **Capture.** In the evening you log tomorrow's plan. The next day you record whether it happened. Optionally, GitHub commit counts and backfilled milestones add more history.
2. **Label.** Each day gets a label (done or not done) tagged with its source: `verified`, `inferred`, or `synthetic`.
3. **Features.** Features for day *i* are built only from outcomes before day *i*, so the future never leaks into the past.
4. **Gate.** A data-sufficiency check decides whether there is enough history to show a forecast at all.
5. **Model.** TabPFN and five baselines are evaluated on a rolling-origin split, and the forecast is produced.
6. **Plan.** The risk label goes to a local Gemma model, which writes a smaller plan. Its output is checked by guardrails before you see it.
7. **Show.** The result appears in the dashboard and in the briefing.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
make install                # core deps + pytest
make test                   # 40 tests
make sample                 # synthetic demo log (tagged synthetic)
make eval-sample            # chronological evaluation -> results/
make demo                   # dashboard (opens on synthetic data until you have a real log)
```

On Windows PowerShell, activate the environment with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

The dashboard always opens on clearly flagged synthetic data until you have a real log, so a demo number is never mistaken for your own behaviour.

## Add TabPFN

TabPFN is the point of the project: a pretrained model built for small tabular datasets, which is exactly what a personal habit log is.

```bash
make install-tabpfn
```

Then accept Prior Labs' model license for the open weights (see their docs or platform.priorlabs.ai). The first fit downloads the weights. After that, it runs offline.

> **License note:** The TabPFN weights are non-commercial: fine for research, evaluation, and a portfolio, but not for a product. The code in this repo is MIT. The weights are not covered by it.

`SLOTHCAST_TABPFN_MODE=client` uses Prior Labs' hosted API instead. Your rows leave your machine in that mode, so it is **off by default**.

## Add the local planner (Gemma)

Install [Ollama](https://ollama.com), then:

```bash
ollama pull gemma3:4b
```

Or set `SLOTHCAST_GEMMA_MODEL` to any Gemma tag you prefer. If Ollama is not running, Slothcast falls back to a deterministic template plan and says so.

## Using it with your own data

Copy `.env.example` to `.env`. Real logs live in `data/raw/`, which is gitignored.

A typical routine:

1. **Evening:** log tomorrow's plan.
2. **Next day:** record whether it happened.
3. **Anytime:** run an evaluation on your own history, then ask for a forecast.

```bash
slothcast log --task "DSA block" --minutes 120 --deadline-days 3 --energy 3   # evening: plan tomorrow
slothcast done --date 2026-10-22 --done 1                                     # next day: did it happen?
slothcast eval                                                                # compare models on YOUR history
slothcast forecast --task "DSA block" --minutes 120 --deadline-days 3 --energy 3
```

## CLI reference

| Command | What it does |
|---|---|
| `slothcast log` | Log a planned task: `--task`, `--minutes`, `--deadline-days`, `--energy` (1-5) |
| `slothcast done` | Record the outcome for a date: `--date`, `--done 1` or `--done 0` |
| `slothcast ingest-github` | Optional. Pull commit counts for a user: `--user YOUR_NAME`. Can only *infer* a label for a day you left blank |
| `slothcast import-csv <file>` | Backfill old milestones from a CSV. Labels default to `inferred` |
| `slothcast eval` | Compare TabPFN and the baselines on your history |
| `slothcast forecast` | Forecast the risk for a planned task: `--task`, `--minutes`, `--deadline-days`, `--energy` |
| `slothcast set-plan` | Set a plan for the optional Temporal nightly run |

## Data format

`checkins.csv` has these columns:

| Column | Meaning |
|---|---|
| `date` | The day of the plan |
| `planned_task` | What you planned to do |
| `planned_minutes` | Planned duration |
| `days_to_deadline` | How close the deadline is |
| `energy_1_5` | Your expected energy, from 1 to 5 |
| `completed_0_1` | `1` if it happened, `0` if it slipped. **Blank means "not known yet"** |
| `label_source` | `verified` (you recorded it), `inferred` (derived), or `synthetic` (demo data) |

## Honesty rules built into the code

These are enforced in the code and covered by tests, not just stated here.

- **No fake certainty.** Under 15 labelled days (or fewer than 4 of either outcome), it shows "Not enough history yet" instead of a probability. 15-29 days is labelled *preliminary*.
- **No leakage.** Features for day *i* only see outcomes before day *i*. Evaluation is rolling-origin and never shuffled. Both are unit-tested.
- **Baselines included.** Base rate, "same as yesterday", weekday rate, logistic regression, and random forest. TabPFN has to beat them. If it does not win, the report says so.
- **Labels keep their provenance.** Commits can only *infer* a label for a day you left blank, and it is tagged `inferred`. Results are also reported on verified labels alone when there are enough of them.
- **The LLM never writes numbers.** `agent/guardrails.py` rejects any percentage, decimal probability, or odds that the model did not produce, and falls back to the template plan.
- **Synthetic data is always flagged** in the dashboard and in `results.md`.

## Evaluation

Run it on the synthetic demo log, or on your own history:

```bash
make eval-sample     # synthetic demo log
slothcast eval       # your own history
```

The report is written to `results/` as `results.md`. It includes:

- **Brier score** for each model
- **Calibration**, so you can see whether "70%" really means about 70%
- **A learning curve by history length**, showing how much data TabPFN needs before it is worth using
- **A bootstrap interval** for the gain over the base rate
- **Results on verified labels alone**, when there are enough of them

Evaluation is rolling-origin: models are trained on the past and tested on the next day, then the window moves forward. Nothing is shuffled.

## Configuration

Copy `.env.example` to `.env` and set what you need.

| Variable | Purpose |
|---|---|
| `SLOTHCAST_TABPFN_MODE` | Set to `client` to use Prior Labs' hosted TabPFN API. Off by default, since your rows would leave your machine |
| `SLOTHCAST_GEMMA_MODEL` | The Gemma tag Ollama should use (default `gemma3:4b`) |
| `SLOTHCAST_LLM_BASE_URL` | Optional hosted habit coach: base URL of an OpenAI-compatible provider |
| `SLOTHCAST_LLM_API_KEY` | Optional hosted habit coach: API key |
| `SLOTHCAST_LLM_MODEL` | Optional hosted habit coach: model name |
| `SENTRY_DSN` | Optional Sentry tracing |
| `SLOTHCAST_TRACE` | Set to `1` to also write `results/traces.jsonl` |

The hosted habit coach needs all three `SLOTHCAST_LLM_*` settings. Without them, numerical habit forecasts keep working and the coach stays unavailable. Keep provider credentials in the backend environment, and never put them in frontend code.

## Optional integrations

| Piece | Setup |
|---|---|
| **Hosted habit coach** | Set the three `SLOTHCAST_LLM_*` variables. It sends aggregate completion counts, rates, pattern groups, and existing insights only when you request coaching. Task names are not sent |
| **Temporal nightly run** | `pip install -e ".[temporal]"`, `temporal server start-dev`, `slothcast set-plan ...`, then `python -m slothcast.workflows.worker` (add `--run-once` or `--schedule`) |
| **Sentry tracing** | `pip install -e ".[sentry]"` and set `SENTRY_DSN`. Spans carry timings and token counts, never task text. `SLOTHCAST_TRACE=1` also writes `results/traces.jsonl` |

## Deployment

The dashboard is a Streamlit app. The live version runs at **https://slothcast.onrender.com**.

To host it yourself on Render, DigitalOcean, or any host that runs Python:

```bash
streamlit run src/slothcast/app/main.py
```

A few things to keep in mind when hosting:

- **Hosted TabPFN or LLM calls change your privacy story.** If you enable them, say so honestly to your users.
- **Keep API keys in the host's environment variables.** Never commit them.
- **The hosted demo uses flagged synthetic data.** It is not a place to store a real personal log unless you add per-user storage and authentication.
- **First load may be slow** on hosts that put idle apps to sleep.

## Project layout

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

| Module | Responsibility |
|---|---|
| `ingest/` | Brings in check-ins, GitHub commit counts, and backfilled history |
| `labels.py` | Turns raw records into labelled days with provenance |
| `features.py` | Builds features that only use past outcomes |
| `sufficiency.py` | Decides whether there is enough history to show a forecast |
| `models/` | Baselines and the TabPFN wrapper |
| `evaluate/` | Rolling-origin splits, metrics, learning curve, and the report |
| `agent/` | The Gemma planner, its prompts, and the guardrails |
| `workflows/` | Optional Temporal nightly run |
| `observability.py` | Optional Sentry spans and local trace log |
| `app/main.py` | The Streamlit dashboard |

## Testing

```bash
make test
```

The 40 tests cover leakage, labels, sufficiency, guardrails, metrics, ingestion, the pipeline, and the dashboard. Run them after changing features, labels, models, or the planner.

## Privacy

A procrastination log shows when you avoid things, how tired you were, and what you keep putting off. Slothcast treats that as sensitive.

- Real logs live in `data/raw/`, which is gitignored.
- TabPFN and Gemma run locally by default.
- The hosted habit coach is opt-in, sends aggregate statistics only, and never sends task names.
- Sentry spans carry timings and token counts, never task text.
- Hosted TabPFN is off by default because your rows would leave your machine.

## What this project does not show

It does not show that the nudges change behaviour. Showing that needs an A/B period of nudged versus not-nudged weeks, which you can only run after the forecast itself works. A forecast that is accurate about when you slip is a prerequisite for that test, not proof of it.

## License

MIT for the code. The TabPFN weights are covered by Prior Labs' license, which is non-commercial.
