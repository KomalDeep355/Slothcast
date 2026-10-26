"""Central configuration. Override with environment variables or a .env file."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("SLOTHCAST_ROOT", Path.cwd()))


def _load_dotenv(path: Path) -> None:
    """Tiny .env reader (no dependency). Existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

# ---- paths (read at call time via config.X so tests can monkeypatch) ----
DATA_DIR = Path(os.environ.get("SLOTHCAST_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"
OUTBOX_DIR = DATA_DIR / "outbox"
RESULTS_DIR = Path(os.environ.get("SLOTHCAST_RESULTS_DIR", ROOT / "results"))
CHECKINS_PATH = RAW_DIR / "checkins.csv"
COMMITS_PATH = RAW_DIR / "github_commits.csv"
PLAN_PATH = RAW_DIR / "plan.json"
SAMPLE_CHECKINS_PATH = SAMPLE_DIR / "demo_log.csv"

# ---- data sufficiency: below this we refuse to show a probability ----
MIN_ROWS_OK = 30
MIN_ROWS_PRELIM = 15
MIN_PER_CLASS_OK = 8
MIN_PER_CLASS_PRELIM = 4

# ---- evaluation ----
MIN_TRAIN = 20  # first prediction is made after this many labelled days

# ---- risk bands (slip probability) ----
RISK_LOW_MAX = 0.30
RISK_ELEVATED_MAX = 0.55

# ---- local LLM (Ollama) ----
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
GEMMA_MODEL = os.environ.get("SLOTHCAST_GEMMA_MODEL", "gemma3:4b")
LLM_TIMEOUT_S = float(os.environ.get("SLOTHCAST_LLM_TIMEOUT", "60"))

# ---- TabPFN: "local" keeps data on your machine; "client" calls Prior Labs' API ----
TABPFN_MODE = os.environ.get("SLOTHCAST_TABPFN_MODE", "local")

# ---- timezone used to bucket commit timestamps into days ----
TZ = os.environ.get("SLOTHCAST_TZ", "UTC")
