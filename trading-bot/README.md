# Gold Scalping Bot (XAU/USD, MetaTrader 5)

A fast intraday scalping bot skeleton for gold (XAU/USD), built around
MetaTrader 5 for market data. It ships in **paper-trading / backtest mode
only** — no code path in this project places a real order or touches real
money.

> **This is not financial advice and comes with no guarantee of
> profitability.** Trading gold, especially short-term scalping, carries a
> real risk of loss. Backtest and paper-trade thoroughly, understand exactly
> what the strategy and risk settings do, and only ever risk capital you can
> afford to lose. If you later decide to connect this to live order
> execution, that is a deliberate, separate step this project does not take
> for you (see "Going live" below).

## What's here

- `src/strategy/ema_rsi_scalper.py` — example fast EMA-crossover + RSI-filter
  strategy for short timeframes (default M1).
- `src/risk/risk_manager.py` — position sizing from a fixed % risk per trade,
  ATR-based stop-loss/take-profit distances, max trades/day and max daily
  loss circuit breakers.
- `src/broker/paper_broker.py` — simulates fills and exits against candle
  data with a virtual balance. Used by *both* the backtester and live
  paper-trading, so a strategy behaves identically in both.
- `src/data/csv_feed.py` — loads historical OHLCV candles for backtesting.
- `src/data/mt5_feed.py` — reads real-time candles from a running MT5
  terminal (read-only: market data only, never order placement).
- `src/engine/backtest.py` — bar-by-bar backtest producing a trade log,
  equity curve, win rate, profit factor and max drawdown.
- `src/engine/live_paper.py` — polls MT5 for new candles and runs the same
  session logic in real time, still only via the paper broker.

## Setup

```bash
cd trading-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then adjust to taste
```

## Backtesting (works anywhere, no MT5 needed)

A small synthetic sample dataset is included at
`data_samples/xauusd_m1_sample.csv` (seeded random walk, **not real market
data** — only useful for exercising the code end-to-end). Regenerate it with:

```bash
python scripts/generate_sample_data.py
```

For a real backtest, export actual XAU/USD M1 history from your MT5
terminal (Tools ▸ History Center ▸ Export) or another data vendor, in the
same `time,open,high,low,close,volume` CSV layout, then run:

```bash
python main.py backtest --config config.yaml --data path/to/your_data.csv --trades
```

This prints trade count, win rate, profit factor, max drawdown and the
balance change — plus every individual trade with `--trades`.

## Live paper-trading (real prices, simulated orders)

Requires a running MT5 terminal (Windows or Wine) with the `MetaTrader5`
Python package installed, and credentials in environment variables:

```bash
pip install MetaTrader5
export MT5_LOGIN=...
export MT5_PASSWORD=...
export MT5_SERVER=...
python main.py paper --config config.yaml
```

This streams real MT5 candles and runs the strategy against them, but every
"trade" only updates the in-memory `PaperBroker` balance — nothing is ever
sent to the broker.

## Tests

```bash
python -m pytest
```

Covers the indicators, risk manager, paper broker fill/exit logic, and a
full backtest run.

## Tuning the strategy

All strategy and risk parameters live in `config.yaml`:

- `strategy.ema_fast` / `ema_slow` — crossover periods (defaults 9/21).
- `strategy.rsi_period`, `rsi_overbought`, `rsi_oversold` — entry filter.
- `strategy.atr_period` — volatility measure used for stop/target distance.
- `risk.risk_per_trade_pct` — % of balance risked per trade.
- `risk.sl_atr_mult` / `tp_atr_mult` — stop-loss / take-profit distance as a
  multiple of ATR.
- `risk.max_trades_per_day`, `max_daily_loss_pct` — daily circuit breakers;
  the bot stops opening new trades once either limit is hit.

## Going live (not implemented here, on purpose)

There is intentionally no code in this project that places, modifies, or
closes a real order. To move beyond paper-trading you would need to add a
broker adapter that actually calls MT5's `order_send()` (or your broker's
equivalent), map `RiskManager.position_size()`'s abstract "units" into that
broker's real lot/contract size (e.g. MT5's XAUUSD is commonly 100 oz per
standard lot — check your broker's contract specification), and add
explicit safeguards (an opt-in flag, a kill switch, monitoring/alerting)
before ever risking real capital. Do this only after a long, honest
paper-trading track record, and treat it as a distinct, carefully reviewed
change rather than flipping a flag in this codebase.
