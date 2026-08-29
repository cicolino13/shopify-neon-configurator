#!/usr/bin/env python3
"""CLI entrypoint for the gold-scalping bot.

Examples:
    python main.py backtest    --config config.yaml --data data.csv
    python main.py sweep       --config config.yaml --data data.csv --grid grids/ema_rsi_scalper.yaml
    python main.py walkforward --config config.yaml --data data.csv --grid grids/ema_rsi_scalper.yaml
    python main.py paper       --config config.yaml
"""
from __future__ import annotations

import argparse
import logging
import sys

import yaml

from src.config import BotConfig
from src.data.csv_feed import load_csv_candles
from src.engine.backtest import run_backtest
from src.engine.optimize import make_scorer, run_sweep, walk_forward
from src.risk.risk_manager import RiskManager
from src.strategy.registry import STRATEGIES, build_strategy


def _load_grid(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _quiet_trade_logging() -> None:
    """Sweeps run hundreds of backtests; their per-trade INFO lines would bury
    the results table.
    """
    logging.getLogger("src.engine.session").setLevel(logging.WARNING)


def cmd_backtest(args: argparse.Namespace) -> None:
    config = BotConfig.from_yaml(args.config)
    candles = load_csv_candles(args.data)
    strategy = build_strategy(config.strategy.name, config.strategy.params)

    report = run_backtest(
        candles,
        strategy,
        RiskManager.from_config(config.risk),
        initial_balance=config.risk.initial_balance,
        atr_period=config.risk.atr_period,
        costs=config.costs,
    )

    print(f"Strategy: {config.strategy.name} {config.strategy.params}")
    print(report.summary())

    if args.trades:
        print()
        for t in report.trade_log:
            print(
                f"{t.opened_at} -> {t.closed_at} {t.direction} "
                f"entry={t.entry_price:.3f} exit={t.exit_price:.3f} "
                f"pnl={t.pnl:.2f} ({t.exit_reason})"
            )


def cmd_sweep(args: argparse.Namespace) -> None:
    _quiet_trade_logging()
    config = BotConfig.from_yaml(args.config)
    candles = load_csv_candles(args.data)
    grid = _load_grid(args.grid)
    scorer = make_scorer(metric=args.metric, min_trades=args.min_trades)

    def progress(done: int, total: int) -> None:
        print(f"\r  {done}/{total} combinations", end="", file=sys.stderr, flush=True)

    results = run_sweep(candles, config.strategy.name, grid, config.risk, config.costs, scorer, progress)
    print("", file=sys.stderr)

    ranked = [r for r in results if r.score > float("-inf")]
    if not ranked:
        print(
            f"No parameter set produced at least {args.min_trades} trades. "
            "Use more data, a wider grid, or lower --min-trades."
        )
        return

    print(f"\nTop {min(args.top, len(ranked))} of {len(ranked)} valid combinations (metric: {args.metric})\n")
    header = f"{'score':>9}  {'return':>9}  {'PF':>6}  {'DD':>7}  {'trades':>6}  params"
    print(header)
    print("-" * len(header))

    for result in ranked[: args.top]:
        r = result.report
        params = ", ".join(f"{k}={v}" for k, v in result.params.items())
        print(
            f"{result.score:>9.4f}  {r.return_pct:>8.2%}  {min(r.profit_factor, 99.99):>6.2f}  "
            f"{r.max_drawdown_pct:>6.2%}  {r.total_trades:>6}  {params}"
        )

    print(
        "\nThese are IN-SAMPLE results: the same data chose and scored the "
        "parameters, so they are optimistic by construction. Run "
        "`walkforward` before believing any of them."
    )


def cmd_walkforward(args: argparse.Namespace) -> None:
    _quiet_trade_logging()
    config = BotConfig.from_yaml(args.config)
    candles = load_csv_candles(args.data)
    grid = _load_grid(args.grid)
    scorer = make_scorer(metric=args.metric, min_trades=args.min_trades)

    def progress(message: str) -> None:
        print(f"  {message}", file=sys.stderr, flush=True)

    report = walk_forward(
        candles,
        config.strategy.name,
        grid,
        config.risk,
        config.costs,
        n_folds=args.folds,
        scorer=scorer,
        progress=progress,
    )

    if not report.folds:
        print("No fold produced a usable result. Try more data, fewer folds, or a lower --min-trades.")
        return

    print()
    print(report.table())
    print(
        "\nIS score = in-sample score of the parameters chosen on the training "
        "slice.\nOOS = how those same parameters then did on the following, "
        "unseen slice -- that is the number that matters.\nIf OOS returns "
        "scatter around zero while IS scores look strong, the grid is fitting "
        "noise, not an edge."
    )


def _open_feed(config: BotConfig):
    """Connect to MT5, turning the expected setup failures into a plain
    message instead of a traceback -- these are the first thing a user hits
    when their terminal or platform is not ready.
    """
    from src.data.mt5_feed import Mt5Feed

    try:
        return Mt5Feed(config.symbol, config.timeframe)
    except RuntimeError as exc:
        print(f"MT5 connection failed:\n  {exc}", file=sys.stderr)
        raise SystemExit(1)


def cmd_check(args: argparse.Namespace) -> None:
    """Verify the MT5 connection and print the broker's real numbers.

    Reads only -- it selects the symbol, fetches quotes and candles, and
    places nothing.
    """
    config = BotConfig.from_yaml(args.config)
    feed = _open_feed(config)

    try:
        account = feed.account_summary()
        print("Account")
        print(f"  login       : {account['login']}")
        print(f"  server      : {account['server']}")
        print(f"  type        : {account['trade_mode']}")
        print(f"  balance     : {account['balance']:.2f} {account['currency']}")
        print(f"  leverage    : 1:{account['leverage']}")

        if account["trade_mode"] != "DEMO":
            print(
                "\n  !! This is NOT a demo account. Nothing in this project places an\n"
                "     order, but do your testing on a demo account regardless."
            )

        info = feed.describe_symbol()
        print(f"\nSymbol: {info['symbol']} ({info['description']})")
        print(f"  bid / ask   : {info['bid']:.{info['digits']}f} / {info['ask']:.{info['digits']}f}")
        print(f"  spread      : {info['spread_price']:.{info['digits']}f} "
              f"({info['spread_points']} points)")
        print(f"  contract    : {info['contract_size']:g} units per lot")
        print(f"  lot size    : min {info['volume_min']:g}, max {info['volume_max']:g}, "
              f"step {info['volume_step']:g}")

        candles = feed.get_candles(5)
        print(f"\nLast {len(candles)} {config.timeframe} candles (broker server time):")
        print(candles.to_string())

        print("\nSuggested config values from this broker, right now:")
        print(f"  costs.spread: {info['spread_price']:.{info['digits']}f}")
        print(
            "\nSpreads widen around news and outside liquid hours, so re-run this at\n"
            "different times and use the worse number -- an optimistic spread is the\n"
            "easiest way to make a losing scalping strategy look profitable."
        )
    finally:
        feed.shutdown()


def cmd_paper(args: argparse.Namespace) -> None:
    # Imported lazily: this path needs the MetaTrader5 package + a running
    # MT5 terminal, which the backtest path does not.
    from src.engine.live_paper import run_live_paper

    config = BotConfig.from_yaml(args.config)
    strategy = build_strategy(config.strategy.name, config.strategy.params)
    run_live_paper(config, strategy, feed=_open_feed(config))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--list-strategies", action="version",
        version=", ".join(sorted(STRATEGIES)), help="show available strategies and exit"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_p = subparsers.add_parser("backtest", help="Run a single historical backtest")
    backtest_p.add_argument("--config", required=True)
    backtest_p.add_argument("--data", required=True, help="CSV file with OHLCV candles")
    backtest_p.add_argument("--trades", action="store_true", help="Print every trade")
    backtest_p.set_defaults(func=cmd_backtest)

    sweep_p = subparsers.add_parser("sweep", help="Grid-search parameters over the whole dataset (in-sample)")
    sweep_p.add_argument("--config", required=True)
    sweep_p.add_argument("--data", required=True)
    sweep_p.add_argument("--grid", required=True, help="YAML file describing the parameter grid")
    sweep_p.add_argument("--metric", default="return_over_drawdown",
                         choices=["return_pct", "profit_factor", "return_over_drawdown"])
    sweep_p.add_argument("--min-trades", type=int, default=20,
                         help="Discard parameter sets with fewer trades than this")
    sweep_p.add_argument("--top", type=int, default=15, help="How many rows to print")
    sweep_p.set_defaults(func=cmd_sweep)

    wf_p = subparsers.add_parser("walkforward", help="Optimise and validate out-of-sample across folds")
    wf_p.add_argument("--config", required=True)
    wf_p.add_argument("--data", required=True)
    wf_p.add_argument("--grid", required=True)
    wf_p.add_argument("--folds", type=int, default=4)
    wf_p.add_argument("--metric", default="return_over_drawdown",
                      choices=["return_pct", "profit_factor", "return_over_drawdown"])
    wf_p.add_argument("--min-trades", type=int, default=10)
    wf_p.set_defaults(func=cmd_walkforward)

    check_p = subparsers.add_parser(
        "check", help="Verify the MT5 connection and print the broker's real spread/contract specs"
    )
    check_p.add_argument("--config", required=True)
    check_p.set_defaults(func=cmd_check)

    paper_p = subparsers.add_parser(
        "paper", help="Live paper-trading on MT5 real-time data (no real orders are placed)"
    )
    paper_p.add_argument("--config", required=True)
    paper_p.set_defaults(func=cmd_paper)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
