#!/usr/bin/env python3
"""Generate a small synthetic M1 XAUUSD-like OHLCV CSV for testing the
backtest engine end-to-end. This is NOT real market data -- it's a seeded
random walk with gold-like volatility, meant only to exercise the code.
Replace with real historical data (e.g. exported from your MT5 terminal)
before drawing any conclusions about a strategy.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def generate(n_bars: int = 5000, start_price: float = 2000.0, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    # ~0.05% per-minute std dev, roughly in line with gold's intraday volatility
    returns = rng.normal(loc=0.0, scale=0.0005, size=n_bars)
    close = start_price * np.cumprod(1 + returns)

    open_ = np.roll(close, 1)
    open_[0] = start_price

    intrabar_range = np.abs(rng.normal(loc=0.0003, scale=0.0002, size=n_bars)) * close
    high = np.maximum(open_, close) + intrabar_range
    low = np.minimum(open_, close) - intrabar_range
    volume = rng.integers(10, 200, size=n_bars)

    time = pd.date_range("2024-01-02 00:00", periods=n_bars, freq="1min")

    return pd.DataFrame(
        {"time": time, "open": open_, "high": high, "low": low, "close": close, "volume": volume}
    )


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent.parent / "data_samples" / "xauusd_m1_sample.csv"
    df = generate()
    df.to_csv(out_path, index=False)
    print(f"wrote {len(df)} rows to {out_path}")
