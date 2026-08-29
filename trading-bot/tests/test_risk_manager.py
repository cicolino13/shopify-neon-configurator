import pytest

from src.risk.risk_manager import RiskManager


def make_rm(**overrides):
    defaults = dict(
        risk_per_trade_pct=1.0,
        sl_atr_mult=1.5,
        tp_atr_mult=2.5,
        max_trades_per_day=5,
        max_daily_loss_pct=3.0,
    )
    defaults.update(overrides)
    return RiskManager(**defaults)


def test_compute_stop_take_for_buy():
    rm = make_rm()
    sl, tp = rm.compute_stop_take("BUY", entry_price=2000.0, atr_value=2.0)
    assert sl == pytest.approx(2000.0 - 2.0 * 1.5)
    assert tp == pytest.approx(2000.0 + 2.0 * 2.5)


def test_compute_stop_take_for_sell():
    rm = make_rm()
    sl, tp = rm.compute_stop_take("SELL", entry_price=2000.0, atr_value=2.0)
    assert sl == pytest.approx(2000.0 + 2.0 * 1.5)
    assert tp == pytest.approx(2000.0 - 2.0 * 2.5)


def test_compute_stop_take_rejects_unknown_action():
    rm = make_rm()
    with pytest.raises(ValueError):
        rm.compute_stop_take("HOLD", 2000.0, 2.0)


def test_position_size_scales_with_risk_amount_and_stop_distance():
    rm = make_rm(risk_per_trade_pct=1.0)
    size = rm.position_size(balance=10_000, entry_price=2000.0, stop_loss_price=1990.0)
    # risk_amount = 100, stop_distance = 10 -> size = 10
    assert size == pytest.approx(10.0)


def test_position_size_is_zero_for_zero_stop_distance():
    rm = make_rm()
    size = rm.position_size(balance=10_000, entry_price=2000.0, stop_loss_price=2000.0)
    assert size == 0.0


def test_can_trade_blocks_after_max_trades_per_day():
    rm = make_rm(max_trades_per_day=2)
    assert rm.can_trade(trades_today=1, pnl_today=0.0, balance=10_000) is True
    assert rm.can_trade(trades_today=2, pnl_today=0.0, balance=10_000) is False


def test_can_trade_blocks_after_max_daily_loss():
    rm = make_rm(max_daily_loss_pct=3.0)
    assert rm.can_trade(trades_today=0, pnl_today=-299.0, balance=10_000) is True
    assert rm.can_trade(trades_today=0, pnl_today=-300.0, balance=10_000) is False
