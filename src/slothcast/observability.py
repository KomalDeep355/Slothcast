"""Optional tracing. Works with no setup (no-op); real Sentry spans if SENTRY_DSN is set.

Privacy: spans carry counts, durations, model names and token counts. Never task text or raw rows.
Set SLOTHCAST_TRACE=1 to also append every span to results/traces.jsonl (handy for write-ups).
"""
from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager

from . import config

_ENABLED = False


def init_sentry() -> bool:
    global _ENABLED
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        return False
    sentry_sdk.init(dsn=dsn, traces_sample_rate=1.0, send_default_pii=False)
    _ENABLED = True
    return True


class _Span:
    def __init__(self, attrs: dict):
        self.attrs = attrs

    def set(self, key: str, value) -> None:
        self.attrs[key] = value


@contextmanager
def span(name: str, **attrs):
    s = _Span(dict(attrs))
    t0 = time.perf_counter()
    cm = sp = None
    if _ENABLED:
        try:
            import sentry_sdk

            cm = sentry_sdk.start_span(op="slothcast", name=name)
            sp = cm.__enter__()
        except Exception:
            cm = sp = None
    exc_info = (None, None, None)
    try:
        yield s
    except BaseException:
        exc_info = sys.exc_info()
        raise
    finally:
        s.attrs["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if cm is not None:
            try:
                for k, v in s.attrs.items():
                    sp.set_data(k, v)
                cm.__exit__(*exc_info)
            except Exception:
                pass
        if os.environ.get("SLOTHCAST_TRACE") == "1":
            config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            with open(config.RESULTS_DIR / "traces.jsonl", "a") as fh:
                fh.write(json.dumps({"span": name, **s.attrs}, default=str) + "\n")
