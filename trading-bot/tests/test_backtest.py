import pytest

from src.broker.costs import CostModel
from src.config import RiskConfig
from src.engine.backtest import run_backtest
from src.risk.risk_manager import RiskManager
from src.strategy.ema_rsi_scalper import EmaRsiScalper

from tests.helpers import make_candles, make_choppy_candles


def _risk_config(**overrides):
    defaults = dict(
        initial_balance=10_000.0,
        atr_period=14,
        risk_per_trade_pct=1.0,
        sl_atr_mult=1.5,
        tp_atr_mult=2.5,
        max_trades_per_day=50,
        max_daily_loss_pct=100.0,  # effectively disabled for these tests
    )
    defaults.update(overrides)
    return RiskConfig(**defaults)


def _run(candles, costs=None, risk_config=None, strategy=None):
    risk_config = risk_config or _risk_config()
    return run_backtest(
        candles,
        strategy or EmaRsiScalper(),
        RiskManager.from_config(risk_config),
        initial_balance=risk_config.initial_balance,
        atr_period=risk_config.atr_period,
        costs=costs,
    )


def test_run_backtest_produces_a_consistent_report(candles):
    report = _run(candles)

    assert report.total_trades > 0
    assert report.wins + report.losses == report.total_trades
    assert report.final_balance == pytest.approx(report.equity_curve.iloc[-1])
    assert 0.0 <= report.max_drawdown_pct <= 1.0
    assert report.return_pct == pytest.approx(
        (report.final_balance - report.initial_balance) / report.initial_balance
    )


def test_backtest_leaves_no_position_open(candles):
    report = _run(candles)
    # every trade is accounted for in the log, including any final flatten
    assert sum(t.pnl for t in report.trade_log) == pytest.approx(
        report.final_balance - report.initial_balance
    )


def test_costs_make_results_worse(candles):
    free = _run(candles, costs=CostModel.zero())
    costly = _run(candles, costs=CostModel(spread=0.50, commission_per_unit=0.05, slippage=0.02))

    assert costly.final_balance < free.final_balance
    assert costly.total_commission > 0


def test_daily_loss_limit_caps_the_number_of_trades():
    # needs data that actually produces losing days for the limit to bind
    choppy = make_choppy_candles()
    unlimited = _run(choppy, risk_config=_risk_config(max_daily_loss_pct=100.0))
    limited = _run(choppy, risk_config=_risk_config(max_daily_loss_pct=0.5))

    assert unlimited.losses > 0, "test data must contain losing trades"
    assert limited.total_trades < unlimited.total_trades


def test_max_trades_per_day_is_respected():
    report = _run(make_choppy_candles(), risk_config=_risk_config(max_trades_per_day=2))

    per_day = {}
    for trade in report.trade_log:
        per_day[trade.closed_at.date()] = per_day.get(trade.closed_at.date(), 0) + 1

    # the cap applies when *opening*, so a day can close at most cap + 1 trades
    # (the last one may have been opened before the cap was reached)
    assert max(per_day.values()) <= 3


def test_run_backtest_rejects_too_little_data():
    with pytest.raises(ValueError, match="warm up"):
        _run(make_candles(n=10))
