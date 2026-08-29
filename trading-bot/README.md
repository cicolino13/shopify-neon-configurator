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

**Strategies** (`src/strategy/`) — each one only decides *entries*; stops and
targets always come from the risk manager, so all of them get the same risk
controls:

| name | idea | works best when |
|---|---|---|
| `ema_rsi_scalper` | fast/slow EMA crossover with an RSI filter | price trends |
| `bollinger_reversion` | buy/sell when price snaps back inside a Bollinger band | price ranges |
| `session_breakout` | break of the opening range after the London/NY open | volatility clusters at the open |

**Everything else:**

- `src/broker/costs.py` — spread, commission and slippage. Candles are bid
  prices, so a BUY enters at the ask and a SELL exits at the ask, and every
  round trip pays the spread. **This is the part that decides whether a
  scalping strategy is real**; see "Why costs matter" below.
- `src/broker/paper_broker.py` — simulates fills and exits with a virtual
  balance. Used by *both* the backtester and live paper-trading, so a
  strategy behaves identically in both.
- `src/risk/risk_manager.py` — position sizing from a fixed % risk per trade,
  ATR-based stop-loss/take-profit distances, max trades/day and max daily
  loss circuit breakers.
- `src/engine/backtest.py` — bar-by-bar backtest producing a trade log,
  equity curve, win rate, profit factor and max drawdown.
- `src/engine/optimize.py` — parameter grid search and **walk-forward
  validation** (optimise on one slice of history, measure on the next,
  unseen one).
- `src/engine/live_paper.py` — polls MT5 for new candles and runs the same
  session logic in real time, still only via the paper broker.

## Setup

```bash
cd trading-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then adjust to taste
```

## Getting real data

A small synthetic sample lives at `data_samples/xauusd_m1_sample.csv`
(seeded random walk, **not real market data** — only useful for exercising
the code; regenerate with `python scripts/generate_sample_data.py`).

For anything meaningful, export real XAU/USD history from MT5
(`View ▸ Symbols ▸ XAUUSD ▸ Bars`, or `Save As` from a chart) in the same
`time,open,high,low,close,volume` layout.

## Commands

```bash
# single backtest
python main.py backtest --config config.yaml --data XAUUSD_M1.csv --trades

# grid search (in-sample -- optimistic by construction)
python main.py sweep --config config.yaml --data XAUUSD_M1.csv \
    --grid grids/ema_rsi_scalper.yaml

# grid search validated on data it never optimised on -- the honest one
python main.py walkforward --config config.yaml --data XAUUSD_M1.csv \
    --grid grids/ema_rsi_scalper.yaml --folds 4

# verify the MT5 connection and read the broker's real spread (no trading)
python main.py check --config config.yaml

# live paper-trading against MT5 real-time prices (no real orders)
python main.py paper --config config.yaml
```

Switch strategy by editing the `strategy.name` and `strategy.params` block in
`config.yaml`; grids for each strategy live in `grids/`.

## Why costs matter

Scalping profits are small per trade, so transaction costs are not a detail —
they are usually the whole result. Running the bundled sample data through
increasing cost assumptions:

| costs | profit factor | return |
|---|---|---|
| none | 0.87 | −2.18% |
| spread 0.30 | 0.87 | −2.18% |
| spread 0.30 + commission + slippage | 0.84 | −2.90% |
| spread 1.50 (news-widened) | 0.20 | −12.65% |

Note how the spread does *not* change the profit or loss of any individual
trade: stops and targets are set relative to the price you actually filled
at, so the spread instead makes targets harder to reach and stops easier to
hit. It shows up as a worse *distribution* of outcomes, which makes it easy
to underestimate — until the spread widens, as in the last row. Take the
real numbers from your broker's contract specification.

## Why walk-forward matters

`sweep` searches the whole dataset and reports the best parameters it found.
Those numbers are always flattering: the same data both chose and graded
them. With enough combinations something always looks brilliant in
hindsight — that is curve fitting, not an edge.

`walkforward` cuts history into chunks, optimises on one and then measures
those exact parameters on the *next*, unseen chunk. On the synthetic sample
data (a pure random walk, where no edge can possibly exist) it correctly
exposes the illusion:

```
fold   IS score   OOS ret   OOS PF   trades
   1     0.9032    -4.03%     0.55       14
   2     5.2166    -5.88%     0.00        6
   3     1.1254     5.01%     2.25       10
   4     2.6442    -5.89%     0.00        6
Chained out-of-sample return: -10.74% over 36 trades
```

Strong in-sample scores, out-of-sample returns scattered around zero and
negative overall. If your real data produces a picture like this, the
strategy has no edge no matter how good the `sweep` table looked.

## Live paper-trading

**Runs on your machine only.** The `MetaTrader5` package is published for
Windows only — there is no Linux build at all — and it drives a running MT5
terminal via local IPC, so this cannot be run from a container or a remote
session on your behalf.

Credentials are read from environment variables and never written to
`config.yaml` (which is git-ignored anyway). Keep it that way: don't paste
account logins into a chat, a config file, or a commit. Use a **demo**
account for all of this.

```bash
pip install MetaTrader5
export MT5_LOGIN=... MT5_PASSWORD=... MT5_SERVER=...

# 1. confirm the connection and read the broker's real numbers (no trading)
python main.py check --config config.yaml

# 2. then run the paper session
python main.py paper --config config.yaml
```

`check` prints the account type (it warns loudly if the account is not a
demo), the live bid/ask and **actual spread**, the contract size and lot
limits, and the last few candles. Put the spread it reports into
`costs.spread` — a guessed spread is the single easiest way to make a losing
scalping strategy look profitable, and the contract size is what you need to
convert the risk manager's units into lots later.

The paper session streams real MT5 candles and runs the strategy against
them, but every "trade" only updates the in-memory `PaperBroker` balance —
nothing is ever sent to the broker. It acts on the last *closed* candle,
never the bar still forming, so it cannot accidentally trade on a price that
is not final.

## Running from a phone (or any browser)

Backtests, sweeps and walk-forward runs can be started from the **GitHub
mobile app** — no laptop needed:

> Actions ▸ *Trading bot backtest* ▸ Run workflow ▸ pick strategy/mode ▸ Run

Results are written to the run summary as Markdown tables, which the mobile
app renders natively. The workflow also runs the test suite first, so a run
that reports numbers is a run whose code passed its tests.

To use your own data, commit the exported MT5 CSV to the repo and pass its
path in the `data` field; otherwise it falls back to the synthetic sample and
labels the result accordingly.

**Live paper-trading cannot be run this way.** The `MetaTrader5` package is
Windows-only and drives a locally installed terminal, so it needs your own
Windows machine or a Windows VPS — a CI runner or a phone cannot host it, and
the MT5 mobile app runs neither Python nor Expert Advisors.

## Tests

```bash
python -m pytest
```

Covers the indicators, cost model, risk manager, paper broker fill/exit
logic, all three strategies, the backtester, the optimiser and the live
paper-trading loop (driven by a stub feed, so it runs without MT5).

## Configuration

All strategy, cost and risk parameters live in `config.yaml`:

- `strategy.name` / `strategy.params` — which strategy and its settings.
- `costs.spread`, `commission_per_unit`, `slippage` — USD per ounce.
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
