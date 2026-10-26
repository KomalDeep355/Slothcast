"""Gate: refuse to show a probability when there is not enough history."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from . import config


@dataclass
class Sufficiency:
    level: str  # "ok" | "preliminary" | "insufficient"
    n_rows: int
    n_slips: int
    n_done: int
    n_verified: int
    n_inferred: int
    n_synthetic: int
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def assess(labeled: pd.DataFrame) -> Sufficiency:
    n = len(labeled)
    slips = int(labeled["y_slip"].sum()) if n else 0
    done = n - slips
    minority = min(slips, done)
    src = labeled["label_source"] if n else pd.Series(dtype=str)
    counts = {k: int((src == k).sum()) for k in ("verified", "inferred", "synthetic")}

    if n < config.MIN_ROWS_PRELIM or minority < config.MIN_PER_CLASS_PRELIM:
        level = "insufficient"
        msg = (
            f"Not enough history yet: {n} labelled days ({slips} slipped, {done} done). "
            f"Need at least {config.MIN_ROWS_PRELIM} days with {config.MIN_PER_CLASS_PRELIM}+ of each outcome."
        )
    elif n < config.MIN_ROWS_OK or minority < config.MIN_PER_CLASS_OK:
        level = "preliminary"
        msg = (
            f"Preliminary: {n} labelled days ({slips} slipped, {done} done). "
            f"Treat the number as a rough estimate; {config.MIN_ROWS_OK}+ days with "
            f"{config.MIN_PER_CLASS_OK}+ of each outcome is where it becomes meaningful."
        )
    else:
        level = "ok"
        msg = f"{n} labelled days ({slips} slipped, {done} done)."
    return Sufficiency(level, n, slips, done, counts["verified"], counts["inferred"], counts["synthetic"], msg)
