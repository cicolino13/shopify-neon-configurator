import numpy as np
import pandas as pd

from src.indicators import add_indicators, atr, ema, rsi


def _sample_df(n=100):
    rng = np.random.default_rng(0)
    close = 2000 + np.cumsum(rng.normal(0, 1, n))
    high = close + 1
    low = close - 1
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close})


def test_ema_tracks_a_flat_series():
    series = pd.Series([100.0] * 20)
    result = ema(series, 5)
    assert np.isclose(result.iloc[-1], 100.0)


def test_rsi_is_bounded_between_0_and_100():
    df = _sample_df()
    result = rsi(df["close"], 14)
    assert (result >= 0).all()
    assert (result <= 100).all()


def test_rsi_is_high_for_a_strict_uptrend():
    series = pd.Series(np.arange(1, 51, dtype=float))
    result = rsi(series, 14)
    assert result.iloc[-1] > 90


def test_atr_is_non_negative():
    df = _sample_df()
    result = atr(df, 14)
    assert (result.dropna() >= 0).all()


def test_add_indicators_adds_expected_columns():
    df = _sample_df()
    out = add_indicators(df, ema_fast=9, ema_slow=21, rsi_period=14, atr_period=14)
    for col in ("ema_fast", "ema_slow", "rsi", "atr"):
        assert col in out.columns
    assert len(out) == len(df)
