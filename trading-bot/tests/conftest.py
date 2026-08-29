import pytest

from tests.helpers import make_candles


@pytest.fixture
def candles():
    return make_candles()
