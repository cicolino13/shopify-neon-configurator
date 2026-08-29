"""Load and validate the bot's YAML configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class StrategyConfig:
    ema_fast: int
    ema_slow: int
    rsi_period: int
    rsi_overbought: float
    rsi_oversold: float
    atr_period: int


@dataclass
class RiskConfig:
    initial_balance: float
    risk_per_trade_pct: float
    sl_atr_mult: float
    tp_atr_mult: float
    max_trades_per_day: int
    max_daily_loss_pct: float


@dataclass
class LiveConfig:
    poll_seconds: int
    history_bars: int


@dataclass
class BotConfig:
    symbol: str
    timeframe: str
    strategy: StrategyConfig
    risk: RiskConfig
    live: LiveConfig

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BotConfig":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        return cls(
            symbol=raw["symbol"],
            timeframe=raw["timeframe"],
            strategy=StrategyConfig(**raw["strategy"]),
            risk=RiskConfig(**raw["risk"]),
            live=LiveConfig(**raw["live"]),
        )
