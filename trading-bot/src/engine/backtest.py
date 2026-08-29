"""Bar-by-bar backtest over historical candles. Uses the exact same
TradingSession (strategy + risk manager + paper broker) as live paper-trading,
so a strategy behaves identically in both.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from ..broker.base import Trade
from ..broker.costs import CostModel
from ..broker.paper_broker import PaperBroker
from ..indicators import add_atr
from ..risk.risk_manager import RiskManager
from ..strategy.base import Strategy
from .session import TradingSession


@dataclass
class BacktestReport:
    initial_balance: float
    final_balance: float
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    return_pct: float
    total_commission: float = 0.0
    trade_log: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)

    def summary(self) -> str:
        profit_factor = "inf" if math.isinf(self.profit_factor) else f"{self.profit_factor:.2f}"
        return (
            f"Trades: {self.total_trades} (W {self.wins} / L {self.losses}, "
            f"win rate {self.win_rate:.1%})\n"
            f"Profit factor: {profit_factor}\n"
            f"Max drawdown: {self.max_drawdown_pct:.2%}\n"
            f"Commission paid: {self.total_commission:.2f}\n"
            f"Balance: {self.initial_balance:.2f} -> {self.final_balance:.2f} "
            f"({self.return_pct:+.2%})"
        )


def prepare_candles(candles: pd.DataFrame, strategy: Strategy, atr_period: int) -> pd.DataFrame:
    """Attach the ATR the risk manager needs plus the strategy's own
    indicators. Exposed separately so a parameter sweep can avoid
    recomputing indicators it has already built.
    """
    return strategy.prepare(add_atr(candles, atr_period))


def run_backtest(
    candles: pd.DataFrame,
    strategy: Strategy,
    risk_manager: RiskManager,
    initial_balance: float,
    atr_period: int = 14,
    costs: CostModel | None = None,
    _prepared: bool = False,
) -> BacktestReport:
    df = candles if _prepared else prepare_candles(candles, strategy, atr_period)

    warmup = max(strategy.warmup_bars, atr_period + 1)
    if len(df) <= warmup:
        raise ValueError(f"need more than {warmup} candles to warm up indicators, got {len(df)}")

    broker = PaperBroker(initial_balance, costs)
    session = TradingSession(strategy, risk_manager, broker)

    equity_index = []
    equity_values = []

    for i in range(warmup, len(df)):
        history = df.iloc[: i + 1]
        candle = df.iloc[i]
        session.process_candle(candle, history)
        equity_index.append(candle.name)
        equity_values.append(broker.equity(candle["close"]))

    # Flatten any position still open at the end of the data so unrealised
    # PnL is reflected in the results rather than silently dropped.
    if broker.position is not None:
        last_candle = df.iloc[-1]
        broker.force_close(last_candle)
        equity_values[-1] = broker.balance

    equity_curve = pd.Series(equity_values, index=pd.Index(equity_index, name="time"), dtype=float)

    wins = sum(1 for t in broker.trade_log if t.pnl > 0)
    losses = sum(1 for t in broker.trade_log if t.pnl <= 0)
    total_trades = len(broker.trade_log)

    gross_profit = sum(t.pnl for t in broker.trade_log if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in broker.trade_log if t.pnl < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    running_peak = equity_curve.cummax()
    drawdown = (running_peak - equity_curve) / running_peak
    max_drawdown_pct = drawdown.max() if not drawdown.empty else 0.0

    return BacktestReport(
        initial_balance=initial_balance,
        final_balance=broker.balance,
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        win_rate=(wins / total_trades) if total_trades else 0.0,
        profit_factor=profit_factor,
        max_drawdown_pct=float(max_drawdown_pct),
        return_pct=(broker.balance - initial_balance) / initial_balance,
        total_commission=sum(t.commission for t in broker.trade_log),
        trade_log=broker.trade_log,
        equity_curve=equity_curve,
    )
