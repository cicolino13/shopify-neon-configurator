"""Load historical OHLCV candles from a CSV file for backtesting.

Expected columns: time, open, high, low, close, volume (the same layout MT5's
"Export" function produces). `time` must be parseable by pandas.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_csv_candles(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"time", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").set_index("time")
    return df
