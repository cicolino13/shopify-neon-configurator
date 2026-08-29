"""Load and validate the bot's YAML configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .broker.costs import CostModel


@dataclass
class StrategyConfig:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConfig:
    initial_balance: float
    risk_per_trade_pct: float
    sl_atr_mult: float
    tp_atr_mult: float
    max_trades_per_day: int
    max_daily_loss_pct: float
    atr_period: int = 14


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
    costs: CostModel
    live: LiveConfig

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BotConfig":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        strategy_raw = raw["strategy"]
        costs_raw = raw.get("costs") or {}

        return cls(
            symbol=raw["symbol"],
            timeframe=raw["timeframe"],
            strategy=StrategyConfig(
                name=strategy_raw["name"],
                params=strategy_raw.get("params") or {},
            ),
            risk=RiskConfig(**raw["risk"]),
            costs=CostModel(**costs_raw),
            live=LiveConfig(**raw["live"]),
        )
