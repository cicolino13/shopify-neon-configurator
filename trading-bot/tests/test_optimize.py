import pytest

from src.broker.costs import CostModel
from src.config import RiskConfig
from src.engine.backtest import BacktestReport
from src.engine.optimize import expand_grid, make_scorer, run_sweep, walk_forward

from tests.helpers import make_candles, make_choppy_candles


def _risk_config():
    return RiskConfig(
        initial_balance=10_000.0,
        atr_period=14,
        risk_per_trade_pct=1.0,
        sl_atr_mult=1.5,
        tp_atr_mult=2.5,
        max_trades_per_day=50,
        max_daily_loss_pct=100.0,
    )


def _report(total_trades=50, return_pct=0.1, profit_factor=1.5, max_drawdown_pct=0.05):
    return BacktestReport(
        initial_balance=10_000.0,
        final_balance=10_000.0 * (1 + return_pct),
        total_trades=total_trades,
        wins=total_trades // 2,
        losses=total_trades - total_trades // 2,
        win_rate=0.5,
        profit_factor=profit_factor,
        max_drawdown_pct=max_drawdown_pct,
        return_pct=return_pct,
    )


# --------------------------------------------------------------------------
# grid expansion
# --------------------------------------------------------------------------

def test_expand_grid_produces_the_cartesian_product():
    combos = expand_grid({"a": [1, 2], "b": [3, 4, 5]})

    assert len(combos) == 6
    assert {"a": 1, "b": 3} in combos
    assert {"a": 2, "b": 5} in combos


def test_expand_grid_of_nothing_is_one_empty_combination():
    assert expand_grid({}) == [{}]


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------

def test_scorer_rejects_parameter_sets_with_too_few_trades():
    score = make_scorer(min_trades=10)
    assert score(_report(total_trades=9)) == float("-inf")
    assert score(_report(total_trades=10)) > float("-inf")


def test_profit_factor_metric_is_capped_so_a_loss_free_run_cannot_dominate():
    score = make_scorer(metric="profit_factor")
    assert score(_report(profit_factor=float("inf"))) == 100.0


def test_return_over_drawdown_rewards_smoother_equity():
    score = make_scorer(metric="return_over_drawdown")
    smooth = score(_report(return_pct=0.1, max_drawdown_pct=0.05))
    choppy = score(_report(return_pct=0.1, max_drawdown_pct=0.20))
    assert smooth > choppy


def test_unknown_metric_is_rejected():
    with pytest.raises(ValueError, match="unknown metric"):
        make_scorer(metric="sharpe")(_report())


# --------------------------------------------------------------------------
# sweep
# --------------------------------------------------------------------------

def test_run_sweep_ranks_results_and_reports_progress():
    grid = {"ema_fast": [3, 5], "ema_slow": [20, 30], "risk.sl_atr_mult": [1.0, 2.0]}
    seen = []

    results = run_sweep(
        make_choppy_candles(n=600),
        "ema_rsi_scalper",
        grid,
        _risk_config(),
        CostModel.zero(),
        scorer=make_scorer(min_trades=1),
        progress=lambda done, total: seen.append((done, total)),
    )

    assert len(results) == 8
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)
    assert seen[-1] == (8, 8)


def test_run_sweep_skips_invalid_parameter_combinations():
    # ema_fast >= ema_slow is rejected by the strategy and must not blow up
    grid = {"ema_fast": [5, 30], "ema_slow": [20]}

    results = run_sweep(
        make_choppy_candles(n=600),
        "ema_rsi_scalper",
        grid,
        _risk_config(),
        CostModel.zero(),
        scorer=make_scorer(min_trades=1),
    )

    assert len(results) == 1
    assert results[0].params == {"ema_fast": 5, "ema_slow": 20}


def test_sweep_result_splits_strategy_and_risk_parameters():
    results = run_sweep(
        make_choppy_candles(n=600),
        "ema_rsi_scalper",
        {"ema_fast": [5], "risk.sl_atr_mult": [1.0]},
        _risk_config(),
        CostModel.zero(),
        scorer=make_scorer(min_trades=1),
    )

    assert results[0].strategy_params == {"ema_fast": 5}
    assert results[0].risk_overrides == {"sl_atr_mult": 1.0}


# --------------------------------------------------------------------------
# walk-forward
# --------------------------------------------------------------------------

def test_walk_forward_tests_on_data_it_did_not_optimise_on():
    report = walk_forward(
        make_choppy_candles(n=2000),
        "ema_rsi_scalper",
        {"ema_fast": [3, 5], "ema_slow": [20, 30]},
        _risk_config(),
        CostModel.zero(),
        n_folds=3,
        scorer=make_scorer(min_trades=1),
    )

    assert len(report.folds) > 0
    for fold in report.folds:
        # every test window starts strictly after its training window ends
        assert fold.test_start > fold.train_end
        assert fold.best_params
    assert report.out_of_sample_trades > 0


def test_walk_forward_table_renders_every_fold():
    report = walk_forward(
        make_choppy_candles(n=2000),
        "ema_rsi_scalper",
        {"ema_fast": [3, 5], "ema_slow": [20, 30]},
        _risk_config(),
        CostModel.zero(),
        n_folds=3,
        scorer=make_scorer(min_trades=1),
    )

    table = report.table()
    assert "out-of-sample" in table
    for fold in report.folds:
        assert f"\n{fold.fold:>4}  " in table


def test_walk_forward_needs_enough_data():
    with pytest.raises(ValueError, match="need at least"):
        walk_forward(
            make_candles(n=5),
            "ema_rsi_scalper",
            {"ema_fast": [3]},
            _risk_config(),
            CostModel.zero(),
            n_folds=4,
        )
