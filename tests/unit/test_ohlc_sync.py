"""Independent Test US3: Sincronizacao multi-instrumento.

Testa a sincronizacao de múltiplos instrumentos por timestamp UTC.
"""

import json
import pytest
from pathlib import Path
from motor.ohlc.sync import sync_instruments, SyncResult

# Load fixtures
FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/ohlc/sync_multi.json"


@pytest.fixture
def fixtures():
    """Load test fixtures."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


def _build_bars(timestamps, prices):
    """Build bar data from timestamps and prices arrays."""
    bars = []
    for ts, price in zip(timestamps, prices):
        # price is [open, high, low, close, bid, ask]
        bar = [ts] + price
        bars.append(bar)
    return bars


class TestUS3Sync:
    """Test cases for multi-instrument synchronization."""

    def test_partial_overlap_sync(self, fixtures):
        """US3.1: Sync with partially overlapping timestamps."""
        partial = fixtures["partial_overlap"]
        
        # Build bars from the fixture structure
        bars_a = _build_bars(
            partial["instrument_a"]["timestamps"],
            partial["instrument_a"]["prices"]
        )
        bars_b = _build_bars(
            partial["instrument_b"]["timestamps"],
            partial["instrument_b"]["prices"]
        )
        
        instruments = {
            "A": bars_a,
            "B": bars_b
        }
        
        result = sync_instruments(instruments)
        
        assert result is not None
        assert len(result.timestamps) == 4  # Union of all timestamps

    def test_merged_timestamps(self, fixtures):
        """US3.2: Merged timestamps match expected."""
        partial = fixtures["partial_overlap"]
        
        # Build bars from the fixture structure
        bars_a = _build_bars(
            partial["instrument_a"]["timestamps"],
            partial["instrument_a"]["prices"]
        )
        bars_b = _build_bars(
            partial["instrument_b"]["timestamps"],
            partial["instrument_b"]["prices"]
        )
        
        instruments = {
            "A": bars_a,
            "B": bars_b
        }
        
        result = sync_instruments(instruments)
        
        expected_timestamps = fixtures["expected_merged_timestamps"]
        assert result.timestamps == expected_timestamps

    def test_sync_result_type(self, fixtures):
        """US3.3: Sync result is SyncResult object."""
        partial = fixtures["partial_overlap"]
        
        bars_a = _build_bars(
            partial["instrument_a"]["timestamps"],
            partial["instrument_a"]["prices"]
        )
        bars_b = _build_bars(
            partial["instrument_b"]["timestamps"],
            partial["instrument_b"]["prices"]
        )
        
        instruments = {
            "A": bars_a,
            "B": bars_b
        }
        
        result = sync_instruments(instruments)
        
        assert isinstance(result, SyncResult)
        assert hasattr(result, 'timestamps')
        assert hasattr(result, 'instruments')
        assert hasattr(result, 'status')

    def test_sync_respects_utc(self, fixtures):
        """US3.4: Sync only works with UTC timestamps."""
        # Create a simple sync case
        instruments = {
            "BTC": [[1704067200000, 100.0, 101.0, 99.0, 100.5, 100.0, 101.0]],
            "ETH": [[1704067200000, 50.0, 51.0, 49.0, 50.5, 50.0, 51.0]]
        }
        
        result = sync_instruments(instruments)
        
        assert result is not None
        assert result.timestamps[0] == 1704067200000
        assert result.timestamps[0] > 0  # Is numeric, not a character