#!/usr/bin/env python3
"""CLI entrypoint for the gold-scalping bot.

Examples:
    python main.py backtest --config config.example.yaml --data data_samples/xauusd_m1_sample.csv
    python main.py paper --config config.example.yaml
"""
from __future__ import annotations

import argparse
import logging
import sys

from src.config import BotConfig
from src.data.csv_feed import load_csv_candles
from src.engine.backtest import run_backtest
from src.risk.risk_manager import RiskManager
from src.strategy.ema_rsi_scalper import EmaRsiScalper


def cmd_backtest(args: argparse.Namespace) -> None:
    config = BotConfig.from_yaml(args.config)
    candles = load_csv_candles(args.data)

    strategy = EmaRsiScalper(
        rsi_overbought=config.strategy.rsi_overbought,
        rsi_oversold=config.strategy.rsi_oversold,
    )
    risk_manager = RiskManager.from_config(config.risk)

    report = run_backtest(
        candles,
        strategy,
        risk_manager,
        initial_balance=config.risk.initial_balance,
        ema_fast=config.strategy.ema_fast,
        ema_slow=config.strategy.ema_slow,
        rsi_period=config.strategy.rsi_period,
        atr_period=config.strategy.atr_period,
    )

    print(report.summary())
    if args.trades:
        for t in report.trade_log:
            print(f"{t.opened_at} -> {t.closed_at} {t.direction} pnl={t.pnl:.2f} ({t.exit_reason})")


def cmd_paper(args: argparse.Namespace) -> None:
    # Imported lazily: this path needs the MetaTrader5 package + a running
    # MT5 terminal, which the backtest path does not.
    from src.engine.live_paper import run_live_paper

    config = BotConfig.from_yaml(args.config)
    strategy = EmaRsiScalper(
        rsi_overbought=config.strategy.rsi_overbought,
        rsi_oversold=config.strategy.rsi_oversold,
    )
    run_live_paper(config, strategy)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_p = subparsers.add_parser("backtest", help="Run a historical backtest")
    backtest_p.add_argument("--config", required=True)
    backtest_p.add_argument("--data", required=True, help="CSV file with OHLCV candles")
    backtest_p.add_argument("--trades", action="store_true", help="Print every trade")
    backtest_p.set_defaults(func=cmd_backtest)

    paper_p = subparsers.add_parser(
        "paper", help="Run live paper-trading against MT5 real-time data (no real orders are placed)"
    )
    paper_p.add_argument("--config", required=True)
    paper_p.set_defaults(func=cmd_paper)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
