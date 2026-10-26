"""Import past milestones / earlier logs from a CSV so you are not starting from zero.

Expected columns: the same as checkins.csv. `label_source` defaults to `inferred` here
(past records are rarely as trustworthy as same-day check-ins); set it to `verified`
yourself for rows you are certain about (e.g. real submission times you remember exactly).
Existing dates are never overwritten.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .. import config
from . import checkin


def import_csv(src: str | Path, dest: str | Path | None = None, default_source: str = "inferred") -> int:
    dest = Path(dest or config.CHECKINS_PATH)
    raw = pd.read_csv(src)
    if "label_source" not in raw.columns:
        raw["label_source"] = default_source
    raw["label_source"] = raw["label_source"].fillna(default_source)
    missing = [c for c in checkin.COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"{src} is missing columns: {missing}")
    new = checkin._coerce(raw[checkin.COLUMNS])
    checkin._validate(new)
    existing = checkin.load_checkins(dest)
    new = new[~new["date"].isin(existing["date"])].drop_duplicates("date", keep="last")
    frames = [f for f in (existing, new) if not f.empty]
    out = pd.concat(frames, ignore_index=True) if frames else new
    checkin._save(out, dest)
    return len(new)
