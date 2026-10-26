import pandas as pd
import pytest

from slothcast.demo_data import make_demo_checkins
from slothcast.labels import build_labels


@pytest.fixture
def demo_checkins():
    return make_demo_checkins(days=70, seed=3, end="2026-10-01")


@pytest.fixture
def labeled(demo_checkins):
    df, _ = build_labels(demo_checkins)
    return df
