"""Shared synthetic candle data for the test suite."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ohlc(close, rng, start_price, index):
    high = close + np.abs(rng.normal(0.5, 0.2, len(close)))
    low = close - np.abs(rng.normal(0.5, 0.2, len(close)))
    open_ = np.roll(close, 1)
    open_[0] = start_price
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def make_choppy_candles(n=2000, seed=7, cycle=120, freq="1min", start="2024-01-01"):
    """Noise-dominated prices with a weak cyclical component.

    `make_candles` has one long trend per quarter of the series, so any slice
    of it can contain almost no crossovers -- fine for a single backtest,
    useless for walk-forward folds or for exercising loss limits.

    The cyclical amplitude here is deliberately kept well below the noise: a
    clean sine wave is *perfectly* tradeable by a crossover strategy (it
    produces a 100% win rate, which no real market ever will) and would make
    tests pass for reasons that say nothing about the code.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    drift = 0.0002 * np.sin(2 * np.pi * t / cycle)
    noise = rng.normal(0, 0.002, n)
    close = 2000 * np.cumprod(1 + drift + noise)

    index = pd.Index(pd.date_range(start, periods=n, freq=freq), name="time")
    return _ohlc(close, rng, 2000.0, index)


def make_candles(n=500, seed=1, freq="1min", start="2024-01-01"):
    """Alternating up/down trends so crossover strategies actually fire."""
    rng = np.random.default_rng(seed)
    segment = n // 4
    drift = np.concatenate(
        [
            np.full(segment, 0.001),
            np.full(segment, -0.001),
            np.full(segment, 0.001),
            np.full(n - 3 * segment, -0.001),
        ]
    )
    noise = rng.normal(0, 0.0005, n)
    close = 2000 * np.cumprod(1 + drift + noise)
    high = close + np.abs(rng.normal(0.5, 0.2, n))
    low = close - np.abs(rng.normal(0.5, 0.2, n))
    open_ = np.roll(close, 1)
    open_[0] = 2000.0

    index = pd.Index(pd.date_range(start, periods=n, freq=freq), name="time")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)
