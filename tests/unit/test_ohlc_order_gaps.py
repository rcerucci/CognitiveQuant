"""Independent Test US2: Ordem temporal e gaps.

Testa a validacao de ordem temporal, deteccao de gaps e interpolacao.
"""

import json
import pytest
from pathlib import Path
from motor.ohlc.validation import (
    validate_bars_sequence,
    validate_order_temporal,
    calculate_gap_size,
    handle_gaps,
    ValidationError
)

# Load fixtures
FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/ohlc/order_gaps.json"


@pytest.fixture
def fixtures():
    """Load test fixtures."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


class TestUS2TemporalOrder:
    """Test cases for temporal order validation."""

    def test_valid_ordered_sequence(self):
        """US2.1: Ordered sequence should be accepted."""
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704069000000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25],
            [1704070800000, 101.00, 101.50, 100.80, 101.25, 101.00, 101.50]
        ]
        valid, error = validate_order_temporal(bars)
        assert valid is True
        assert error is None

    def test_duplicate_timestamps(self, fixtures):
        """US2.2: Duplicate timestamps should abort with 'ordem_temporal_invalida'."""
        bars = fixtures["duplicates"]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bars_sequence(bars)
        assert exc_info.value.code == "ordem_temporal_invalida"

    def test_not_ordered(self, fixtures):
        """US2.3: Reverse order should abort with 'ordem_temporal_invalida'."""
        bars = fixtures["not_ordered"]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bars_sequence(bars)
        assert exc_info.value.code == "ordem_temporal_invalida"


class TestUS2Gaps:
    """Test cases for gap handling."""

    def test_no_gap(self):
        """US2.4: Consecutive bars should have gap size 0."""
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704069000000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25]
        ]
        gap = calculate_gap_size(bars, 1)
        assert gap == 0

    def test_gap_1_bar_interpolation(self, fixtures):
        """US2.5: Gap of 1 bar (<=4) should be interpolated."""
        bars = fixtures["gap_1_bar"]["data"]
        gap_size = fixtures["gap_1_bar"]["gap_size"]
        assert gap_size == 1
        
        result = validate_bars_sequence(bars)
        # Should have 3 bars: original 2 + 1 interpolated
        assert len(result.bars) == 3

    def test_gap_4_bars_interpolation(self, fixtures):
        """US2.6: Gap of 4 bars (at threshold) should be interpolated."""
        bars = fixtures["gap_4_bars"]["data"]
        gap_size = fixtures["gap_4_bars"]["gap_size"]
        assert gap_size == 4
        
        result = validate_bars_sequence(bars)
        # Should have 6 bars: original 2 + 4 interpolated
        assert len(result.bars) == 6

    def test_gap_5_bars_gap_dados(self, fixtures):
        """US2.7: Gap of 5 bars (>4) should be marked as gap_dados and NEUTRO."""
        bars = fixtures["gap_5_bars"]["data"]
        gap_size = fixtures["gap_5_bars"]["gap_size"]
        assert gap_size == 5
        
        result = validate_bars_sequence(bars)
        # Check that the bar with gap is marked as NEUTRO
        neutro_bars = [b for b in result.bars if b.status.value == "neutro"]
        assert len(neutro_bars) > 0

    def test_gap_8_bars_gap_dados(self, fixtures):
        """US2.8: Gap larger than 5 bars should be marked as gap_dados and NEUTRO."""
        # Use gap_5_bars data with larger gap
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704110400000, 103.00, 103.50, 102.75, 103.25, 103.00, 103.50]
        ]
        
        result = validate_bars_sequence(bars)
        # Check that the bar with gap is marked as NEUTRO
        neutro_bars = [b for b in result.bars if b.status.value == "neutro"]
        assert len(neutro_bars) > 0


class TestUS2WeekendFill:
    """Test cases for weekend gap handling."""

    def test_weekend_gap_forward_fill(self, fixtures):
        """US2.9: Weekend gap should forward-fill prices."""
        bars = fixtures["weekend_gap"]["data"]
        result = validate_bars_sequence(bars)
        
        # Check that weekend_fill flag is present
        weekend_filled = [b for b in result.bars if "weekend_fill" in b.flags]
        # The second bar should have weekend_fill flag
        assert any("weekend_fill" in b.flags for b in result.bars)