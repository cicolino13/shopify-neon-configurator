"""Live price feed from a running MetaTrader 5 terminal.

This module only reads market data (candles) -- it never places, modifies or
closes orders. It requires the `MetaTrader5` Python package and a running
MT5 terminal, which is Windows-only (or Wine). It is imported lazily by the
live engine so the rest of the project (backtesting, tests) works fine on
any platform without it installed.
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

_TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "H1": "TIMEFRAME_H1",
}


class Mt5Feed:
    def __init__(self, symbol: str, timeframe: str) -> None:
        try:
            import MetaTrader5 as mt5  # noqa: N814
        except ImportError as exc:
            raise RuntimeError(
                "The MetaTrader5 package is required for live paper-trading "
                "but is not installed (it only works on Windows/Wine). "
                "Install it with `pip install MetaTrader5` on a Windows host "
                "with the MT5 terminal running, or use the backtest engine "
                "instead."
            ) from exc

        self._mt5 = mt5
        self.symbol = symbol
        if timeframe not in _TIMEFRAME_MAP:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        self.timeframe = getattr(mt5, _TIMEFRAME_MAP[timeframe])

        login = os.environ.get("MT5_LOGIN")
        password = os.environ.get("MT5_PASSWORD")
        server = os.environ.get("MT5_SERVER")

        if not mt5.initialize(login=int(login) if login else None, password=password, server=server):
            raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"could not select symbol {symbol!r} in MT5 Market Watch")

    def get_candles(self, count: int) -> pd.DataFrame:
        rates = self._mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, count)
        if rates is None:
            raise RuntimeError(f"MT5 copy_rates_from_pos failed: {self._mt5.last_error()}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        df = df.set_index("time")[["open", "high", "low", "close", "volume"]]
        return df

    def shutdown(self) -> None:
        self._mt5.shutdown()
