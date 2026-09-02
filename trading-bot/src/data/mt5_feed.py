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

        if not mt5.initialize(**self._credentials()):
            raise RuntimeError(
                f"MT5 initialize() failed: {mt5.last_error()}. "
                "Check that the MetaTrader 5 terminal is running and logged in, "
                "and that MT5_LOGIN / MT5_PASSWORD / MT5_SERVER match that account "
                "if you set them."
            )

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"could not select symbol {symbol!r} in MT5 Market Watch: "
                f"{mt5.last_error()}. Brokers name gold differently (XAUUSD, "
                "GOLD, XAUUSD.r, ...) -- use the exact name your terminal shows."
            )

    @staticmethod
    def _credentials() -> dict:
        """Credentials from the environment, omitting anything unset.

        Passing login/password/server as None would be rejected; leaving them
        out entirely makes MT5 attach to whatever account the running terminal
        is already logged into, which is the common case.
        """
        credentials: dict = {}

        login = os.environ.get("MT5_LOGIN", "").strip()
        if login:
            try:
                credentials["login"] = int(login)
            except ValueError as exc:
                raise RuntimeError(f"MT5_LOGIN must be the numeric account number, got {login!r}") from exc

        for name, key in (("MT5_PASSWORD", "password"), ("MT5_SERVER", "server")):
            value = os.environ.get(name, "").strip()
            if value:
                credentials[key] = value

        return credentials

    def get_candles(self, count: int) -> pd.DataFrame:
        rates = self._mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, count)
        if rates is None:
            raise RuntimeError(f"MT5 copy_rates_from_pos failed: {self._mt5.last_error()}")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        df = df.set_index("time")[["open", "high", "low", "close", "volume"]]
        return df

    def describe_symbol(self) -> dict:
        """Read the broker's live contract specification for this symbol.

        This is where the numbers your config *should* contain come from: the
        real spread rather than a guessed one, and the contract size needed to
        turn the risk manager's abstract units into lots. Broker
        specifications differ, so never assume -- read them.
        """
        info = self._mt5.symbol_info(self.symbol)
        if info is None:
            raise RuntimeError(f"MT5 symbol_info failed: {self._mt5.last_error()}")

        tick = self._mt5.symbol_info_tick(self.symbol)
        if tick is None:
            raise RuntimeError(f"MT5 symbol_info_tick failed: {self._mt5.last_error()}")

        return {
            "symbol": self.symbol,
            "description": info.description,
            "bid": tick.bid,
            "ask": tick.ask,
            "spread_price": tick.ask - tick.bid,
            "spread_points": info.spread,
            "point": info.point,
            "digits": info.digits,
            "contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
            "trade_mode": info.trade_mode,
        }

    def account_summary(self) -> dict:
        """Account details, used to confirm a *demo* account is connected."""
        account = self._mt5.account_info()
        if account is None:
            raise RuntimeError(f"MT5 account_info failed: {self._mt5.last_error()}")

        # trade_mode 0 = demo, 1 = contest, 2 = real
        modes = {0: "DEMO", 1: "CONTEST", 2: "REAL"}
        return {
            "login": account.login,
            "server": account.server,
            "currency": account.currency,
            "balance": account.balance,
            "leverage": account.leverage,
            "trade_mode": modes.get(account.trade_mode, f"unknown({account.trade_mode})"),
        }

    def shutdown(self) -> None:
        self._mt5.shutdown()
