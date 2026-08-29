import numpy as np
import pandas as pd

from src.engine.backtest import run_backtest
from src.risk.risk_manager import RiskManager
from src.strategy.ema_rsi_scalper import EmaRsiScalper


def _trending_candles(n=500, seed=1):
    rng = np.random.default_rng(seed)
    # alternate up/down trends so EMA crossovers actually occur
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
    open_[0] = 2000

    time = pd.date_range("2024-01-01", periods=n, freq="1min")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close}, index=pd.Index(time, name="time")
    )


def test_run_backtest_produces_a_consistent_report():
    candles = _trending_candles()
    strategy = EmaRsiScalper()
    risk_manager = RiskManager(
        risk_per_trade_pct=1.0,
        sl_atr_mult=1.5,
        tp_atr_mult=2.5,
        max_trades_per_day=50,
        max_daily_loss_pct=100.0,  # effectively disabled for this test
    )

    report = run_backtest(
        candles,
        strategy,
        risk_manager,
        initial_balance=10_000,
        ema_fast=9,
        ema_slow=21,
        rsi_period=14,
        atr_period=14,
    )

    assert report.total_trades > 0
    assert report.wins + report.losses == report.total_trades
    assert report.final_balance == report.equity_curve.iloc[-1]
    assert 0.0 <= report.max_drawdown_pct <= 1.0


def test_run_backtest_rejects_too_little_data():
    candles = _trending_candles(n=10)
    strategy = EmaRsiScalper()
    risk_manager = RiskManager(1.0, 1.5, 2.5, 50, 100.0)

    try:
        run_backtest(candles, strategy, risk_manager, 10_000, 9, 21, 14, 14)
        assert False, "expected ValueError"
    except ValueError:
        pass
