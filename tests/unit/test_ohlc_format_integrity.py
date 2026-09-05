"""Independent Test US1: Formato e integridade de barras OHLC."""

import json
import pytest
from pathlib import Path
from motor.ohlc.validation import validate_bar, validate_ohlc_format, validate_bars_sequence, ValidationError

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/ohlc/format_integrity.json"

@pytest.fixture
def fixtures():
    with open(FIXTURES_PATH) as f:
        return json.load(f)

class TestUS1ValidBars:
    def test_single_valid_bar(self, fixtures):
        bar_data = fixtures["valid_bars"][0]["data"]
        result = validate_bar(bar_data)
        assert result is not None
        assert result["valid"] is True

    def test_multiple_valid_bars_ordered(self, fixtures):
        bars_data = fixtures["valid_bars"][1]["data"]
        result = validate_bars_sequence(bars_data)
        assert result is not None
        assert result.status == "valid"
        assert len(result.bars) == 3

class TestUS1ValidationError:
    def test_missing_fields(self, fixtures):
        bar_data = fixtures["invalid_bars"]["format"][0]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "format_invalido"

    def test_high_less_than_open_close(self, fixtures):
        bar_data = fixtures["invalid_bars"]["price_integrity"][0]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "integridade_preco_invalida"

class TestValidateOhlcFormat:
    def test_valid_format(self):
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]
        assert validate_ohlc_format(bar) is True

    def test_invalid_format_missing_fields(self):
        bar = [1704067200000, 100.50, 101.00]
        assert validate_ohlc_format(bar) is False