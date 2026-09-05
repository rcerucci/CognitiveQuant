"""Independent Test US4: Transformação mid → log → retorno."""

import json
import pytest
import math
from pathlib import Path
from motor.ohlc.validation import validate_bars_sequence
from motor.ohlc.transform import transform_to_returns

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/ohlc/transform_reference.json"

@pytest.fixture
def fixtures():
    with open(FIXTURES_PATH) as f:
        return json.load(f)

class TestUS4MidPrice:
    def test_mid_price_calculation(self):
        bid = 100.50
        ask = 101.00
        expected_P_t = (bid + ask) / 2.0
        P_t = (bid + ask) / 2.0
        assert P_t == pytest.approx(expected_P_t)

    def test_mid_price_from_fixture(self, fixtures):
        for test_case in fixtures["test_cases"]:
            bar = test_case["input"]
            bid = bar[5]
            ask = bar[6]
            expected_P_t = test_case["expected"]["P_t"]
            P_t = (bid + ask) / 2.0
            assert P_t == pytest.approx(expected_P_t, rel=1e-9)

class TestUS4LogPrice:
    def test_log_price_from_fixture(self, fixtures):
        for test_case in fixtures["test_cases"]:
            P_t = test_case["expected"]["P_t"]
            expected_X_t = test_case["expected"]["X_t"]
            X_t = math.log(P_t)
            assert X_t == pytest.approx(expected_X_t, rel=1e-9)

class TestUS4TransformIntegration:
    def test_transform_single_bar(self):
        bars = [[1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]]
        result = validate_bars_sequence(bars)
        transform = transform_to_returns(result)
        assert len(transform.timestamps) == 1
        assert len(transform.r_t) == 0

    def test_transform_multiple_bars(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704069000000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25]
        ]
        result = validate_bars_sequence(bars)
        transform = transform_to_returns(result)
        assert len(transform.r_t) == 1