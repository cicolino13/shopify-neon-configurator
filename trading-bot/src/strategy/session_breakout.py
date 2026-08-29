"""Opening-range breakout around a session open.

Gold's most reliable bursts of volatility cluster around the London and New
York opens. This strategy measures the high/low of the first
`range_minutes` after the session opens, then trades a break of that range
during the rest of the trading window.

Times are interpreted in the timezone of the candle index, which for MT5
data is the broker's server time -- **not** necessarily UTC. Check what your
broker's server time actually is and set `session_start` accordingly, or the
range will be measured over the wrong bars.

Session opens (UTC, outside daylight-saving shifts):
  * London   -- 08:00
  * New York -- 13:30

Because the entry condition is a *crossing* (previous close on one side of
the level, current close on the other), each level naturally fires at most
once per session; `risk.max_trades_per_day` bounds the rest.
"""
from __future__ import annotations

import pandas as pd

from .base import Signal, Strategy


def _minutes_of_day(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(index.hour * 60 + index.minute, index=index)


def _parse_hhmm(value: str) -> int:
    hours, _, minutes = value.partition(":")
    return int(hours) * 60 + int(minutes)


class SessionBreakout(Strategy):
    name = "session_breakout"

    def __init__(
        self,
        session_start: str = "13:30",
        range_minutes: int = 30,
        trade_window_minutes: int = 240,
    ) -> None:
        if range_minutes <= 0:
            raise ValueError("range_minutes must be positive")
        if trade_window_minutes <= range_minutes:
            raise ValueError("trade_window_minutes must be longer than range_minutes")

        self.session_start = session_start
        self.range_minutes = range_minutes
        self.trade_window_minutes = trade_window_minutes

    @property
    def warmup_bars(self) -> int:
        # No rolling indicator to warm up; only the previous bar is needed.
        return 2

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        index = pd.DatetimeIndex(out.index)

        start = _parse_hhmm(self.session_start)
        range_end = start + self.range_minutes
        window_end = start + self.trade_window_minutes

        minutes = _minutes_of_day(index)
        session_date = pd.Series(index.date, index=out.index)

        in_range = (minutes >= start) & (minutes < range_end)
        out["in_trade_window"] = (minutes >= range_end) & (minutes < window_end)

        # Opening-range high/low per session day, broadcast to every bar of
        # that day. Days with no bars inside the range window stay NaN and
        # therefore produce no signals.
        range_bars = out[in_range]
        or_high = range_bars.groupby(session_date[in_range])["high"].max()
        or_low = range_bars.groupby(session_date[in_range])["low"].min()

        out["or_high"] = session_date.map(or_high)
        out["or_low"] = session_date.map(or_low)
        return out

    def on_candle(self, history: pd.DataFrame) -> Signal:
        if len(history) < 2:
            return Signal("HOLD", "not enough history")

        prev, curr = history.iloc[-2], history.iloc[-1]

        if not curr["in_trade_window"]:
            return Signal("HOLD", "outside the session trade window")

        if pd.isna(curr["or_high"]) or pd.isna(curr["or_low"]):
            return Signal("HOLD", "no opening range for this session")

        if prev["close"] <= prev["or_high"] and curr["close"] > curr["or_high"]:
            return Signal("BUY", "broke above the opening range")

        if prev["close"] >= prev["or_low"] and curr["close"] < curr["or_low"]:
            return Signal("SELL", "broke below the opening range")

        return Signal("HOLD")
