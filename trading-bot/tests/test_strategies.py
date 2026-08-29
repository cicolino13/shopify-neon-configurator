import numpy as np
import pandas as pd
import pytest

from src.strategy import BollingerReversion, EmaRsiScalper, SessionBreakout, build_strategy
from src.strategy.registry import STRATEGIES

from tests.helpers import make_candles


def _frame(closes, index=None, high_pad=0.5, low_pad=0.5):
    closes = np.asarray(closes, dtype=float)
    if index is None:
        index = pd.date_range("2024-01-01", periods=len(closes), freq="1min")
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes + high_pad,
            "low": closes - low_pad,
            "close": closes,
        },
        index=pd.Index(index, name="time"),
    )


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def test_registry_builds_every_registered_strategy():
    for name in STRATEGIES:
        assert build_strategy(name).name == name


def test_registry_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="unknown strategy"):
        build_strategy("does_not_exist")


def test_registry_passes_params_through():
    strategy = build_strategy("ema_rsi_scalper", {"ema_fast": 3, "ema_slow": 8})
    assert strategy.ema_fast == 3
    assert strategy.ema_slow == 8


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_prepare_preserves_length_and_adds_columns(name):
    strategy = build_strategy(name)
    df = make_candles(n=400)
    out = strategy.prepare(df)

    assert len(out) == len(df)
    assert set(df.columns).issubset(out.columns)
    assert len(out.columns) > len(df.columns)


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_on_candle_returns_a_valid_action(name):
    strategy = build_strategy(name)
    df = strategy.prepare(make_candles(n=400))

    for i in range(strategy.warmup_bars, len(df)):
        assert strategy.on_candle(df.iloc[: i + 1]).action in ("BUY", "SELL", "HOLD")


# --------------------------------------------------------------------------
# EMA / RSI scalper
# --------------------------------------------------------------------------

def test_ema_scalper_rejects_inverted_periods():
    with pytest.raises(ValueError, match="ema_fast must be shorter"):
        EmaRsiScalper(ema_fast=21, ema_slow=9)


def test_ema_scalper_buys_on_an_upward_cross():
    # falling then sharply rising -> fast EMA crosses above slow EMA
    closes = list(np.linspace(2000, 1990, 40)) + list(np.linspace(1990, 2010, 20))
    strategy = EmaRsiScalper(ema_fast=3, ema_slow=10, rsi_period=5, rsi_overbought=100)
    df = strategy.prepare(_frame(closes))

    actions = [strategy.on_candle(df.iloc[: i + 1]).action for i in range(len(df))]
    assert "BUY" in actions


def test_ema_scalper_rsi_filter_blocks_overbought_entries():
    closes = list(np.linspace(2000, 1990, 40)) + list(np.linspace(1990, 2010, 20))
    df_source = _frame(closes)

    permissive = EmaRsiScalper(ema_fast=3, ema_slow=10, rsi_period=5, rsi_overbought=100)
    strict = EmaRsiScalper(ema_fast=3, ema_slow=10, rsi_period=5, rsi_overbought=0)

    def buys(strategy):
        df = strategy.prepare(df_source)
        return sum(strategy.on_candle(df.iloc[: i + 1]).action == "BUY" for i in range(len(df)))

    assert buys(permissive) > 0
    assert buys(strict) == 0


# --------------------------------------------------------------------------
# Bollinger reversion
# --------------------------------------------------------------------------

def test_bollinger_rejects_degenerate_period():
    with pytest.raises(ValueError, match="period must be at least 2"):
        BollingerReversion(period=1)


def test_bollinger_buys_when_price_re_enters_the_lower_band():
    # flat, one sharp dip below the band, then back to the mean
    closes = [2000.0] * 25 + [1990.0] + [2000.0] * 5
    strategy = BollingerReversion(period=20, num_std=2.0)
    df = strategy.prepare(_frame(closes))

    actions = [strategy.on_candle(df.iloc[: i + 1]).action for i in range(len(df))]
    assert "BUY" in actions


def test_bollinger_holds_while_bands_are_not_warmed_up():
    strategy = BollingerReversion(period=20)
    df = strategy.prepare(_frame([2000.0] * 10))

    assert strategy.on_candle(df).action == "HOLD"


# --------------------------------------------------------------------------
# Session breakout
# --------------------------------------------------------------------------

def test_session_breakout_rejects_a_window_shorter_than_the_range():
    with pytest.raises(ValueError, match="trade_window_minutes"):
        SessionBreakout(range_minutes=60, trade_window_minutes=30)


def test_session_breakout_computes_the_opening_range():
    index = pd.date_range("2024-01-02 13:00", periods=120, freq="1min")
    closes = np.full(len(index), 2000.0)
    df = _frame(closes, index=index)

    strategy = SessionBreakout(session_start="13:30", range_minutes=30, trade_window_minutes=120)
    out = strategy.prepare(df)

    in_range = out.loc["2024-01-02 13:30":"2024-01-02 13:59"]
    assert in_range["or_high"].notna().all()
    # opening range is high/low of the range window: 2000 +/- the pads
    assert out["or_high"].dropna().iloc[0] == pytest.approx(2000.5)
    assert out["or_low"].dropna().iloc[0] == pytest.approx(1999.5)

    # bars before the range window are not tradeable
    assert not out.loc["2024-01-02 13:15", "in_trade_window"]
    assert out.loc["2024-01-02 14:00", "in_trade_window"]


def test_session_breakout_fires_on_a_break_above_the_range():
    index = pd.date_range("2024-01-02 13:30", periods=90, freq="1min")
    closes = np.full(len(index), 2000.0)
    closes[45:] = 2010.0  # decisive break well after the opening range closes
    df = _frame(closes, index=index)

    strategy = SessionBreakout(session_start="13:30", range_minutes=30, trade_window_minutes=120)
    out = strategy.prepare(df)

    actions = [strategy.on_candle(out.iloc[: i + 1]).action for i in range(len(out))]
    assert "BUY" in actions


def test_session_breakout_holds_outside_the_trade_window():
    index = pd.date_range("2024-01-02 20:00", periods=30, freq="1min")
    df = _frame(np.full(len(index), 2000.0), index=index)

    strategy = SessionBreakout(session_start="13:30", range_minutes=30, trade_window_minutes=120)
    out = strategy.prepare(df)

    actions = {strategy.on_candle(out.iloc[: i + 1]).action for i in range(len(out))}
    assert actions == {"HOLD"}
