"""Independent Test US1: Formato e integridade de barras OHLC.

Testa a validacao de formato JSON e integridade de precos conforme especificacao.
"""

import json
import pytest
from pathlib import Path
from motor.ohlc.validation import (
    validate_bar,
    validate_ohlc_format,
    validate_bars_sequence,
    ValidationError
)

# Load fixtures
FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/ohlc/format_integrity.json"


@pytest.fixture
def fixtures():
    """Load test fixtures."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


class TestUS1ValidBars:
    """Test cases for valid bars that should pass validation."""

    def test_single_valid_bar(self, fixtures):
        """US1.1: Single valid OHLC bar with UTC timestamp should be accepted."""
        bar_data = fixtures["valid_bars"][0]["data"]
        result = validate_bar(bar_data)
        assert result is not None
        assert result["valid"] is True
        assert result["timestamp"] == bar_data[0]

    def test_multiple_valid_bars_ordered(self, fixtures):
        """US1.2: Multiple valid bars in chronological order should be accepted."""
        bars_data = fixtures["valid_bars"][1]["data"]
        result = validate_bars_sequence(bars_data)
        assert result is not None
        assert result.status == "valid"
        assert len(result.bars) == 3


class TestUS1ValidationError:
    """Test cases for invalid bars that should cause abort."""

    def test_missing_fields(self, fixtures):
        """US1.3: Missing bid/ask fields should abort with 'format_invalido'."""
        bar_data = fixtures["invalid_bars"]["format"][0]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "format_invalido"

    def test_too_many_fields(self, fixtures):
        """US1.4: Extra fields should abort with 'format_invalido'."""
        bar_data = fixtures["invalid_bars"]["format"][1]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "format_invalido"

    def test_invalid_field_type_timestamp(self, fixtures):
        """US1.5: Non-numeric timestamp should abort with 'format_invalido'."""
        bar_data = fixtures["invalid_bars"]["format"][2]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "format_invalido"

    def test_string_values(self, fixtures):
        """US1.6: String values instead of numbers should abort with 'format_invalido'."""
        bar_data = fixtures["invalid_bars"]["format"][3]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "format_invalido"


class TestUS1PriceIntegrity:
    """Test cases for price integrity validation."""

    def test_high_less_than_open_close(self, fixtures):
        """US1.7: High < max(open, close) should abort with 'integridade_preco_invalida'."""
        bar_data = fixtures["invalid_bars"]["price_integrity"][0]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "integridade_preco_invalida"

    def test_low_greater_than_open_close(self, fixtures):
        """US1.8: Low > min(open, close) should abort with 'integridade_preco_invalida'."""
        bar_data = fixtures["invalid_bars"]["price_integrity"][1]["data"]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "integridade_preco_invalida"

    def test_high_equals_open_close_valid(self, fixtures):
        """US1.9: High=Low=open=close should be valid."""
        bar_data = fixtures["invalid_bars"]["price_integrity"][2]["data"]
        result = validate_bar(bar_data)
        assert result is not None
        assert result["valid"] is True


class TestUS1Timezone:
    """Test cases for timezone validation (UTC only).

    A regra do spec é: timestamps devem ser UTC-only.
    Unix timestamps (milissegundos desde a época) são inherentemente UTC.
    Invalidamos apenas timestamps malformados.
    """

    def test_valid_unix_timestamp_is_utc(self):
        """US1.10: Unix timestamps represent UTC time and are valid."""
        # Um timestamp UNIX válido representa tempo UTC
        bar_data = [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]
        result = validate_bar(bar_data)
        assert result is not None
        assert result["valid"] is True

    def test_invalid_timestamp_string(self):
        """US1.10b: Non-numeric timestamp should abort."""
        bar_data = ["invalid", 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "format_invalido"

    def test_nan_timestamp(self):
        """US1.10c: NaN timestamp should abort."""
        import math
        bar_data = [float('nan'), 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar_data)
        assert exc_info.value.code == "format_invalido"


class TestValidateOhlcFormat:
    """Test the format validation function."""

    def test_valid_format(self):
        """Valid format should return True."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]
        assert validate_ohlc_format(bar) is True

    def test_invalid_format_missing_fields(self):
        """Format with missing fields should return False."""
        bar = [1704067200000, 100.50, 101.00]
        assert validate_ohlc_format(bar) is False

    def test_invalid_format_extra_fields(self):
        """Format with extra fields should return False."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00, 102.00]
        assert validate_ohlc_format(bar) is False