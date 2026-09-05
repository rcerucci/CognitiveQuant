"""Independent Test US2: Ordem temporal e gaps."""

import pytest
from motor.ohlc.validation import validate_bars_sequence, validate_order_temporal, ValidationError

class TestUS2TemporalOrder:
    def test_valid_ordered_sequence(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704069000000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25]
        ]
        valid, error = validate_order_temporal(bars)
        assert valid is True
        assert error is None

    def test_duplicate_timestamps(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704067200000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25]
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_bars_sequence(bars)
        assert exc_info.value.code == "ordem_temporal_invalida"

class TestUS2Gaps:
    def test_gap_1_bar_interpolation(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704070800000, 101.00, 101.50, 100.80, 101.25, 101.00, 101.50]
        ]
        result = validate_bars_sequence(bars)
        assert len(result.bars) == 3  # 2 original + 1 interpolated

    def test_gap_5_bars_gap_dados(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704078000000, 103.00, 103.50, 102.75, 103.25, 103.00, 103.50]
        ]
        result = validate_bars_sequence(bars)
        neutro_bars = [b for b in result.bars if b.status.value == "neutro"]
        assert len(neutro_bars) == 1

class TestUS2WeekendFill:
    def test_weekend_gap_forward_fill(self):
        bars = [
            [1704495600000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704672000000, 102.50, 103.00, 102.25, 102.75, 102.50, 103.00]
        ]
        result = validate_bars_sequence(bars)
        weekend_filled = [b for b in result.bars if "weekend_fill" in b.flags]
        assert len(weekend_filled) >= 1