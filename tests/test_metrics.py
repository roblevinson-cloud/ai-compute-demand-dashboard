import pandas as pd

from ai_compute_dashboard.metrics import _base_index, _pct_change


def test_base_index_starts_at_100_for_flat_series():
    s = pd.Series([5.0, 5.0, 5.0], index=["a", "b", "c"])
    out = _base_index(s, 2)
    assert list(out) == [100.0, 100.0, 100.0]


def test_pct_change():
    s = pd.Series([100.0, 110.0])
    assert round(_pct_change(s, 1).iloc[-1], 8) == 10.0
