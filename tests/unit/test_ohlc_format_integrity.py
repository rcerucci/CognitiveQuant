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
    
    def test_negative_prices_rejected(self):
        """FR-001: Preços negativos devem ser rejeitados."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, -100.50, 101.00]
        assert validate_ohlc_format(bar) is False
    
    def test_zero_prices_rejected(self):
        """FR-001: Preços zero devem ser rejeitados."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, 0.0, 101.00]
        assert validate_ohlc_format(bar) is False
    
    def test_negative_timestamp_rejected(self):
        """Timestamp negativo deve ser rejeitado."""
        bar = [-1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]
        assert validate_ohlc_format(bar) is False

class TestUS1ValidationPositive:
    """Testes para validação de preços positivos (FR-001)."""
    
    def test_valid_all_positive_prices(self):
        """Todos os preços positivos devem passar."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]
        # Should not raise any error
        result = validate_bar(bar)
        assert result["valid"] is True
    
    def test_negative_bid_rejected(self):
        """Bid negativo deve causar abort com format_invalido."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, -100.0, 101.00]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar)
        assert exc_info.value.code == "format_invalido"
    
    def test_negative_ask_rejected(self):
        """Ask negativo deve causar abort com format_invalido."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.0, -101.0]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar)
        assert exc_info.value.code == "format_invalido"