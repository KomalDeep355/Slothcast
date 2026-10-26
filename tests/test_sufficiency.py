import pandas as pd

from slothcast.sufficiency import assess


def _lab(slips, done, src="verified"):
    return pd.DataFrame({"y_slip": [1] * slips + [0] * done, "label_source": [src] * (slips + done)})


def test_insufficient_when_too_few_rows():
    assert assess(_lab(5, 5)).level == "insufficient"


def test_insufficient_when_one_class_is_nearly_absent():
    assert assess(_lab(30, 2)).level == "insufficient"


def test_preliminary_band():
    assert assess(_lab(10, 10)).level == "preliminary"


def test_ok_and_source_counts():
    s = assess(_lab(15, 20, "synthetic"))
    assert s.level == "ok" and s.n_synthetic == 35 and s.n_verified == 0
