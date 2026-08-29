"""Parameter sweeps with walk-forward validation.

Why walk-forward: running a grid over your whole history and picking the best
numbers is the fastest way to fool yourself. With enough combinations,
something always looks brilliant *in hindsight* -- that is curve fitting, not
an edge. Walk-forward instead repeatedly optimises on one slice of history
and then measures the chosen parameters on the *next*, unseen slice. The
out-of-sample column is the only one worth believing, and a strategy whose
in-sample results look great while its out-of-sample results scatter around
zero has no edge, however pretty the grid looks.

Grid keys are strategy parameter names, except keys prefixed `risk.` which
override risk-manager settings, e.g.::

    {"ema_fast": [5, 9], "ema_slow": [21, 34], "risk.sl_atr_mult": [1.0, 2.0]}
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Sequence

import pandas as pd

from ..broker.costs import CostModel
from ..config import RiskConfig
from ..risk.risk_manager import RiskManager
from ..strategy.registry import build_strategy
from .backtest import BacktestReport, prepare_candles, run_backtest

RISK_PREFIX = "risk."


@dataclass
class SweepResult:
    params: dict[str, Any]
    report: BacktestReport
    score: float

    @property
    def strategy_params(self) -> dict[str, Any]:
        return {k: v for k, v in self.params.items() if not k.startswith(RISK_PREFIX)}

    @property
    def risk_overrides(self) -> dict[str, Any]:
        return {k[len(RISK_PREFIX):]: v for k, v in self.params.items() if k.startswith(RISK_PREFIX)}


@dataclass
class FoldResult:
    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    best_params: dict[str, Any]
    train_score: float
    test_report: BacktestReport


@dataclass
class WalkForwardReport:
    folds: list[FoldResult] = field(default_factory=list)

    @property
    def out_of_sample_return(self) -> float:
        """Compounded return of the out-of-sample segments chained together."""
        total = 1.0
        for fold in self.folds:
            total *= 1 + fold.test_report.return_pct
        return total - 1

    @property
    def out_of_sample_trades(self) -> int:
        return sum(f.test_report.total_trades for f in self.folds)

    def table(self) -> str:
        header = (
            f"{'fold':>4}  {'test window':<43}  {'params':<44}  "
            f"{'IS score':>9}  {'OOS ret':>9}  {'OOS PF':>7}  {'trades':>6}"
        )
        lines = [header, "-" * len(header)]

        for fold in self.folds:
            params = ", ".join(f"{k}={v}" for k, v in fold.best_params.items())
            window = f"{fold.test_start:%Y-%m-%d %H:%M} .. {fold.test_end:%Y-%m-%d %H:%M}"
            pf = fold.test_report.profit_factor
            pf_text = "  inf" if math.isinf(pf) else f"{pf:7.2f}"
            lines.append(
                f"{fold.fold:>4}  {window:<43}  {params[:44]:<44}  "
                f"{fold.train_score:>9.4f}  {fold.test_report.return_pct:>8.2%}  "
                f"{pf_text:>7}  {fold.test_report.total_trades:>6}"
            )

        lines.append("-" * len(header))
        lines.append(
            f"Chained out-of-sample return: {self.out_of_sample_return:+.2%} "
            f"over {self.out_of_sample_trades} trades"
        )
        return "\n".join(lines)

    def markdown(self) -> str:
        """The same table as Markdown. The fixed-width `table()` is 138
        columns wide and scrolls sideways on a phone; a Markdown table
        reflows, so this is what CI summaries use.
        """
        lines = [
            "| fold | test window | params | IS score | OOS ret | OOS PF | trades |",
            "|---:|---|---|---:|---:|---:|---:|",
        ]

        for fold in self.folds:
            params = ", ".join(f"`{k}={v}`" for k, v in fold.best_params.items())
            window = f"{fold.test_start:%Y-%m-%d %H:%M} → {fold.test_end:%Y-%m-%d %H:%M}"
            pf = fold.test_report.profit_factor
            pf_text = "∞" if math.isinf(pf) else f"{pf:.2f}"
            lines.append(
                f"| {fold.fold} | {window} | {params} | {fold.train_score:.4f} | "
                f"{fold.test_report.return_pct:+.2%} | {pf_text} | "
                f"{fold.test_report.total_trades} |"
            )

        lines.append("")
        lines.append(
            f"**Chained out-of-sample return: {self.out_of_sample_return:+.2%}** "
            f"over {self.out_of_sample_trades} trades"
        )
        return "\n".join(lines)


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------

def make_scorer(metric: str = "return_pct", min_trades: int = 10) -> Callable[[BacktestReport], float]:
    """Build a scoring function. Parameter sets producing fewer than
    `min_trades` trades score -inf: a 100% win rate over two trades is noise,
    and letting it win the grid is one of the easiest ways to overfit.
    """

    def score(report: BacktestReport) -> float:
        if report.total_trades < min_trades:
            return float("-inf")

        if metric == "return_pct":
            return report.return_pct
        if metric == "profit_factor":
            # cap inf so a lucky loss-free run cannot dominate the ranking
            return min(report.profit_factor, 100.0)
        if metric == "return_over_drawdown":
            if report.max_drawdown_pct <= 0:
                return report.return_pct
            return report.return_pct / report.max_drawdown_pct
        raise ValueError(f"unknown metric: {metric!r}")

    return score


# --------------------------------------------------------------------------
# grid expansion
# --------------------------------------------------------------------------

def expand_grid(grid: dict[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """Cartesian product of the grid, as a list of parameter dicts."""
    if not grid:
        return [{}]

    keys = list(grid)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(grid[k] for k in keys))]


def _split_params(params: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    strategy_params = {k: v for k, v in params.items() if not k.startswith(RISK_PREFIX)}
    risk_overrides = {k[len(RISK_PREFIX):]: v for k, v in params.items() if k.startswith(RISK_PREFIX)}
    return strategy_params, risk_overrides


# --------------------------------------------------------------------------
# sweep
# --------------------------------------------------------------------------

def run_sweep(
    candles: pd.DataFrame,
    strategy_name: str,
    grid: dict[str, Sequence[Any]],
    risk_config: RiskConfig,
    costs: CostModel,
    scorer: Callable[[BacktestReport], float] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> list[SweepResult]:
    """Backtest every parameter combination, best score first.

    Combinations sharing the same strategy parameters reuse one prepared
    indicator frame, so sweeping risk parameters is nearly free.
    """
    scorer = scorer or make_scorer()
    combos = expand_grid(grid)

    # group by strategy params so indicators are computed once per group
    grouped: dict[tuple, list[dict[str, Any]]] = {}
    for params in combos:
        strategy_params, _ = _split_params(params)
        grouped.setdefault(tuple(sorted(strategy_params.items())), []).append(params)

    results: list[SweepResult] = []
    done = 0

    for strategy_key, group in grouped.items():
        strategy_params = dict(strategy_key)
        try:
            strategy = build_strategy(strategy_name, strategy_params)
        except (ValueError, TypeError):
            # invalid combination (e.g. ema_fast >= ema_slow) -- skip the group
            done += len(group)
            if progress:
                progress(done, len(combos))
            continue

        prepared = prepare_candles(candles, strategy, risk_config.atr_period)

        for params in group:
            _, risk_overrides = _split_params(params)
            fold_risk = replace(risk_config, **risk_overrides)

            try:
                report = run_backtest(
                    prepared,
                    strategy,
                    RiskManager.from_config(fold_risk),
                    initial_balance=fold_risk.initial_balance,
                    atr_period=fold_risk.atr_period,
                    costs=costs,
                    _prepared=True,
                )
            except ValueError:
                # not enough bars in this slice to warm up -- skip
                done += 1
                if progress:
                    progress(done, len(combos))
                continue

            results.append(SweepResult(params=params, report=report, score=scorer(report)))
            done += 1
            if progress:
                progress(done, len(combos))

    results.sort(key=lambda r: r.score, reverse=True)
    return results


# --------------------------------------------------------------------------
# walk-forward
# --------------------------------------------------------------------------

def walk_forward(
    candles: pd.DataFrame,
    strategy_name: str,
    grid: dict[str, Sequence[Any]],
    risk_config: RiskConfig,
    costs: CostModel,
    n_folds: int = 4,
    scorer: Callable[[BacktestReport], float] | None = None,
    progress: Callable[[str], None] | None = None,
) -> WalkForwardReport:
    """Optimise on each slice of history, then measure the winning parameters
    on the following, unseen slice.

    The data is cut into `n_folds + 1` equal chunks; fold i trains on chunk i
    and tests on chunk i+1, so every test segment is strictly in the future
    relative to the data that selected its parameters.
    """
    scorer = scorer or make_scorer()

    chunk_count = n_folds + 1
    if len(candles) < chunk_count * 2:
        raise ValueError(f"need at least {chunk_count * 2} candles for {n_folds} folds")

    bounds = [round(i * len(candles) / chunk_count) for i in range(chunk_count + 1)]
    report = WalkForwardReport()

    for fold in range(n_folds):
        train = candles.iloc[bounds[fold]: bounds[fold + 1]]
        test = candles.iloc[bounds[fold + 1]: bounds[fold + 2]]

        if progress:
            progress(f"fold {fold + 1}/{n_folds}: optimising on {len(train)} bars")

        ranked = run_sweep(train, strategy_name, grid, risk_config, costs, scorer)
        ranked = [r for r in ranked if r.score > float("-inf")]

        if not ranked:
            if progress:
                progress(f"fold {fold + 1}: no parameter set met the minimum trade count -- skipped")
            continue

        best = ranked[0]
        strategy = build_strategy(strategy_name, best.strategy_params)
        fold_risk = replace(risk_config, **best.risk_overrides)

        try:
            test_report = run_backtest(
                test,
                strategy,
                RiskManager.from_config(fold_risk),
                initial_balance=fold_risk.initial_balance,
                atr_period=fold_risk.atr_period,
                costs=costs,
            )
        except ValueError:
            if progress:
                progress(f"fold {fold + 1}: test slice too short to warm up -- skipped")
            continue

        report.folds.append(
            FoldResult(
                fold=fold + 1,
                train_start=train.index[0],
                train_end=train.index[-1],
                test_start=test.index[0],
                test_end=test.index[-1],
                best_params=best.params,
                train_score=best.score,
                test_report=test_report,
            )
        )

    return report
