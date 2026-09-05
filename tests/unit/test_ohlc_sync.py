"""Independent Test US3: Sincronizacao multi-instrumento."""

import json
import pytest
from pathlib import Path
from motor.ohlc.sync import sync_instruments, SyncResult

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/ohlc/sync_multi.json"

@pytest.fixture
def fixtures():
    with open(FIXTURES_PATH) as f:
        return json.load(f)

def _build_bars(timestamps, prices):
    bars = []
    for ts, price in zip(timestamps, prices):
        bar = [ts] + price
        bars.append(bar)
    return bars

class TestUS3Sync:
    def test_partial_overlap_sync(self, fixtures):
        partial = fixtures["partial_overlap"]
        bars_a = _build_bars(partial["instrument_a"]["timestamps"], partial["instrument_a"]["prices"])
        bars_b = _build_bars(partial["instrument_b"]["timestamps"], partial["instrument_b"]["prices"])
        
        instruments = {"A": bars_a, "B": bars_b}
        result = sync_instruments(instruments)
        
        assert result is not None
        assert len(result.timestamps) == 4

    def test_sync_result_type(self, fixtures):
        partial = fixtures["partial_overlap"]
        bars_a = _build_bars(partial["instrument_a"]["timestamps"], partial["instrument_a"]["prices"])
        
        instruments = {"A": bars_a}
        result = sync_instruments(instruments)
        
        assert isinstance(result, SyncResult)
        assert hasattr(result, 'timestamps')
        assert hasattr(result, 'instruments')

    def test_sync_respects_utc(self):
        instruments = {
            "BTC": [[1704067200000, 100.0, 101.0, 99.0, 100.5, 100.0, 101.0]],
            "ETH": [[1704067200000, 50.0, 51.0, 49.0, 50.5, 50.0, 51.0]]
        }
        result = sync_instruments(instruments)
        assert result.timestamps[0] == 1704067200000