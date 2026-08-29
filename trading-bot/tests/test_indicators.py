import numpy as np
import pandas as pd
import pytest

from src.indicators import add_atr, atr, bollinger, ema, rsi, sma

from tests.helpers import make_candles


def test_ema_tracks_a_flat_series():
    assert ema(pd.Series([100.0] * 20), 5).iloc[-1] == pytest.approx(100.0)


def test_sma_of_a_flat_series_is_the_level():
    assert sma(pd.Series([100.0] * 20), 5).iloc[-1] == pytest.approx(100.0)


def test_rsi_is_bounded_between_0_and_100():
    result = rsi(make_candles(n=200)["close"], 14)
    assert (result >= 0).all()
    assert (result <= 100).all()


def test_rsi_is_high_for_a_strict_uptrend():
    assert rsi(pd.Series(np.arange(1, 51, dtype=float)), 14).iloc[-1] > 90


def test_rsi_is_low_for_a_strict_downtrend():
    assert rsi(pd.Series(np.arange(50, 0, -1, dtype=float)), 14).iloc[-1] < 10


def test_rsi_is_neutral_for_a_flat_series():
    assert rsi(pd.Series([100.0] * 30), 14).iloc[-1] == pytest.approx(50.0)


def test_atr_is_non_negative():
    assert (atr(make_candles(n=200), 14).dropna() >= 0).all()


def test_atr_of_constant_range_equals_that_range():
    n = 60
    close = np.full(n, 100.0)
    df = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 1.0, "close": close})
    assert atr(df, 14).iloc[-1] == pytest.approx(2.0, rel=1e-3)


def test_bollinger_bands_bracket_the_middle_band():
    mid, upper, lower = bollinger(make_candles(n=200)["close"], 20, 2.0)
    valid = mid.notna()
    assert (upper[valid] >= mid[valid]).all()
    assert (lower[valid] <= mid[valid]).all()


def test_bollinger_bands_collapse_onto_a_flat_series():
    mid, upper, lower = bollinger(pd.Series([100.0] * 40), 20, 2.0)
    assert upper.iloc[-1] == pytest.approx(100.0)
    assert lower.iloc[-1] == pytest.approx(100.0)


def test_add_atr_attaches_the_column_without_changing_length():
    df = make_candles(n=200)
    out = add_atr(df, 14)

    assert "atr" in out.columns
    assert len(out) == len(df)
    assert "atr" not in df.columns  # original frame untouched
