"""Maps strategy names to classes so the CLI, config file and parameter
sweep can all build a strategy from a name plus a dict of parameters.
"""
from __future__ import annotations

from typing import Any, Type

from .base import Strategy
from .bollinger_reversion import BollingerReversion
from .ema_rsi_scalper import EmaRsiScalper
from .session_breakout import SessionBreakout

STRATEGIES: dict[str, Type[Strategy]] = {
    EmaRsiScalper.name: EmaRsiScalper,
    BollingerReversion.name: BollingerReversion,
    SessionBreakout.name: SessionBreakout,
}


def build_strategy(name: str, params: dict[str, Any] | None = None) -> Strategy:
    if name not in STRATEGIES:
        known = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"unknown strategy {name!r}; available: {known}")

    return STRATEGIES[name](**(params or {}))
