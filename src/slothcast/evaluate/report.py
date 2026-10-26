"""Run the chronological evaluation and write results/ (metrics.json, results.md, plots, predictions.csv)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .. import config  # noqa: E402
from ..features import build_features  # noqa: E402
from ..models.baselines import build_registry  # noqa: E402
from ..observability import span  # noqa: E402
from ..sufficiency import assess  # noqa: E402
from .learning_curve import brier_by_train_size  # noqa: E402
from .metrics import bootstrap_brier_gain, reliability_table, summarize  # noqa: E402
from .splits import rolling_origin  # noqa: E402


def collect_predictions(labeled, X, registry, min_train=config.MIN_TRAIN, step=1):
    y = labeled["y_slip"].to_numpy()
    rows, failed = [], {}
    for name, factory in registry.items():
        with span("eval.model", model=name, n_rows=len(y)):
            try:
                model_rows = []
                for tr, te in rolling_origin(len(y), min_train, step):
                    m = factory()
                    m.fit(X.iloc[tr], y[tr])
                    p = np.asarray(m.predict_proba(X.iloc[te]), float)
                    model_rows += [(name, int(j), len(tr), float(pj)) for j, pj in zip(te, p)]
                rows += model_rows
            except Exception as exc:
                if name != "tabpfn":  # only the optional model may fail softly
                    raise
                failed[name] = f"{type(exc).__name__}: {exc}"
    preds = pd.DataFrame(rows, columns=["model", "idx", "n_train", "p_slip"])
    if preds.empty:
        return preds.assign(y=[], date=[], label_source=[]), failed
    preds["y"] = y[preds["idx"].to_numpy()]
    preds["date"] = labeled["date"].iloc[preds["idx"].to_numpy()].to_numpy()
    preds["label_source"] = labeled["label_source"].iloc[preds["idx"].to_numpy()].to_numpy()
    return preds, failed


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(float(o)) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def _plots(preds, out_dir: Path):
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    for model, g in preds.groupby("model"):
        t = reliability_table(g["y"], g["p_slip"])
        if len(t):
            ax.plot(t["mean_pred"], t["frac_slip"], marker="o", label=model)
    ax.set_xlabel("predicted slip probability")
    ax.set_ylabel("observed slip frequency")
    ax.set_title("Calibration (out-of-sample)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "calibration.png", dpi=140)
    plt.close(fig)

    curve = brier_by_train_size(preds)
    fig, ax = plt.subplots(figsize=(6, 4))
    for model, g in curve.groupby("model"):
        ax.plot(g["train_days"], g["brier"], marker="o", label=model)
    ax.set_xlabel("days of history used for training")
    ax.set_ylabel("Brier score (lower is better)")
    ax.set_title("Learning curve")
    if len(curve):
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "learning_curve.png", dpi=140)
    plt.close(fig)
    return curve


def run_report(
    labeled: pd.DataFrame,
    commits: pd.DataFrame | None = None,
    out_dir: str | Path | None = None,
    use_tabpfn: bool = True,
    min_train: int = config.MIN_TRAIN,
    step: int = 1,
    only: list[str] | None = None,
) -> dict:
    out_dir = Path(out_dir or config.RESULTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    suff = assess(labeled)
    X = build_features(labeled, commits)
    registry, notes = build_registry(use_tabpfn=use_tabpfn, only=only)
    registry = {"base_rate": registry.get("base_rate") or build_registry(False, ["base_rate"])[0]["base_rate"], **registry}
    preds, failed = collect_predictions(labeled, X, registry, min_train, step)
    notes.update(failed)

    result: dict = {"n_rows": len(labeled), "sufficiency": suff.to_dict(), "skipped_or_failed": notes,
                    "min_train": min_train, "step": step, "models": {}}
    if preds.empty:
        result["error"] = f"Need more than {min_train} labelled days to evaluate (have {len(labeled)})."
        (out_dir / "metrics.json").write_text(json.dumps(_clean(result), indent=2))
        (out_dir / "results.md").write_text(f"# Results\n\n{result['error']}\n")
        return result

    base = preds[preds["model"] == "base_rate"].sort_values("idx")
    for model, g in preds.groupby("model"):
        g = g.sort_values("idx")
        entry = summarize(g["y"], g["p_slip"])
        if model != "base_rate":
            entry["brier_skill_vs_base"] = 1 - entry["brier"] / summarize(base["y"], base["p_slip"])["brier"]
            entry["gain_vs_base"] = bootstrap_brier_gain(g["y"].to_numpy(), g["p_slip"].to_numpy(), base["p_slip"].to_numpy())
        ver = g[g["label_source"] == "verified"]
        entry["verified_only"] = summarize(ver["y"], ver["p_slip"]) if len(ver) >= 10 else None
        result["models"][model] = entry

    curve = _plots(preds, out_dir)
    preds.to_csv(out_dir / "predictions.csv", index=False)
    curve.to_csv(out_dir / "learning_curve.csv", index=False)
    (out_dir / "metrics.json").write_text(json.dumps(_clean(result), indent=2))
    (out_dir / "results.md").write_text(
    _markdown(result, suff),
    encoding="utf-8",
)
    return result


def _fmt(v, nd=3):
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{nd}f}"


def _markdown(result: dict, suff) -> str:
    lines = ["# Results", "",
             f"Chronological evaluation (rolling origin, first prediction after {result['min_train']} labelled days). "
             "Every prediction uses only data from before that day.", "",
             f"Data: {suff.message}  Sources: {suff.n_verified} verified, {suff.n_inferred} inferred, {suff.n_synthetic} synthetic.", ""]
    if suff.n_synthetic:
        lines += ["> **Synthetic data present.** These numbers describe the demo generator, not a real person.", ""]
    lines += ["| model | test days | Brier ↓ | skill vs base rate | log loss ↓ | accuracy | AUC | ECE ↓ |",
              "|---|---|---|---|---|---|---|---|"]
    for name, m in sorted(result["models"].items(), key=lambda kv: kv[1]["brier"]):
        lines.append(f"| {name} | {m['n']} | {_fmt(m['brier'])} | {_fmt(m.get('brier_skill_vs_base'))} | "
                     f"{_fmt(m['log_loss'])} | {_fmt(m['accuracy'])} | {_fmt(m['auc'])} | {_fmt(m['ece'])} |")
    lines += ["", "Brier: mean squared error of the probability (lower is better). Skill > 0 means better than always "
              "predicting your base slip rate. ECE: average gap between predicted and observed frequency.", "",
              "## Does anything beat the base rate?", ""]
    for name, m in result["models"].items():
        g = m.get("gain_vs_base")
        if g:
            lo, hi = g["ci90"]
            verdict = "interval excludes 0" if lo > 0 else "interval includes 0 -> not distinguishable from the base rate"
            lines.append(f"- **{name}**: Brier gain {_fmt(g['mean'], 4)} (90% bootstrap interval {_fmt(lo, 4)} to {_fmt(hi, 4)}; {verdict}).")
    lines += ["", "Bootstrap resamples days independently, so it ignores serial correlation and is optimistic.", ""]
    if result["skipped_or_failed"]:
        lines += ["## Skipped / failed models", ""] + [f"- {k}: {v}" for k, v in result["skipped_or_failed"].items()] + [""]
    lines += ["![calibration](calibration.png)", "", "![learning curve](learning_curve.png)", ""]
    return "\n".join(lines)
