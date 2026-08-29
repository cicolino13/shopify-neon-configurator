#!/usr/bin/env python3
"""Build a config.yaml from config.example.yaml with overrides applied.

Used by the CI workflow (and handy locally) so a run can be parameterised
without hand-editing YAML. Switching strategy also resets `strategy.params`
to that strategy's own defaults -- carrying EMA parameters over to the
Bollinger strategy would simply crash.
"""
from __future__ import annotations

import argparse
import inspect
from pathlib import Path

import yaml

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.strategy.registry import STRATEGIES  # noqa: E402


def default_params(strategy_name: str) -> dict:
    """The strategy class's own constructor defaults."""
    signature = inspect.signature(STRATEGIES[strategy_name].__init__)
    return {
        name: parameter.default
        for name, parameter in signature.parameters.items()
        if name != "self" and parameter.default is not inspect.Parameter.empty
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default="config.example.yaml")
    parser.add_argument("--out", default="config.yaml")
    parser.add_argument("--strategy", choices=sorted(STRATEGIES))
    parser.add_argument("--spread", type=float, help="costs.spread override")
    parser.add_argument("--commission", type=float, help="costs.commission_per_unit override")
    parser.add_argument("--slippage", type=float, help="costs.slippage override")
    parser.add_argument("--risk-per-trade", type=float, help="risk.risk_per_trade_pct override")
    args = parser.parse_args()

    with open(args.template, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if args.strategy:
        config["strategy"] = {"name": args.strategy, "params": default_params(args.strategy)}

    for key, value in (
        ("spread", args.spread),
        ("commission_per_unit", args.commission),
        ("slippage", args.slippage),
    ):
        if value is not None:
            config.setdefault("costs", {})[key] = value

    if args.risk_per_trade is not None:
        config["risk"]["risk_per_trade_pct"] = args.risk_per_trade

    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)

    print(f"wrote {args.out}: strategy={config['strategy']['name']} costs={config.get('costs')}")


if __name__ == "__main__":
    main()
