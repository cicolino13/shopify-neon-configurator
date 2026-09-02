"""Tests for the parts of the MT5 feed that do not need MetaTrader5 itself
(which is Windows-only), so credential handling stays covered everywhere.
"""
from __future__ import annotations

import pytest

from src.data.mt5_feed import Mt5Feed


def test_no_environment_variables_means_no_credentials(monkeypatch):
    """With nothing set, MT5 should attach to the already-logged-in terminal
    rather than being handed None for every field.
    """
    for name in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER"):
        monkeypatch.delenv(name, raising=False)

    assert Mt5Feed._credentials() == {}


def test_credentials_are_read_and_login_is_numeric(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "12345678")
    monkeypatch.setenv("MT5_PASSWORD", "secret")
    monkeypatch.setenv("MT5_SERVER", "Broker-Demo")

    assert Mt5Feed._credentials() == {
        "login": 12345678,
        "password": "secret",
        "server": "Broker-Demo",
    }


def test_surrounding_whitespace_is_ignored(monkeypatch):
    """Copy-pasting an account number easily drags a space along."""
    monkeypatch.setenv("MT5_LOGIN", "  12345678  ")
    monkeypatch.setenv("MT5_SERVER", " Broker-Demo ")
    monkeypatch.delenv("MT5_PASSWORD", raising=False)

    assert Mt5Feed._credentials() == {"login": 12345678, "server": "Broker-Demo"}


def test_empty_values_are_treated_as_unset(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "")
    monkeypatch.setenv("MT5_PASSWORD", "   ")
    monkeypatch.delenv("MT5_SERVER", raising=False)

    assert Mt5Feed._credentials() == {}


def test_a_non_numeric_login_is_reported_clearly(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "my-account")

    with pytest.raises(RuntimeError, match="numeric account number"):
        Mt5Feed._credentials()


def _metatrader5_installed() -> bool:
    try:
        import MetaTrader5  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(_metatrader5_installed(), reason="MetaTrader5 is installed on this host")
def test_missing_metatrader5_package_explains_itself():
    """Off Windows the package cannot exist, so constructing the feed must
    fail with guidance rather than a bare ImportError traceback.
    """
    with pytest.raises(RuntimeError, match="only works on Windows"):
        Mt5Feed("XAUUSD", "M1")
