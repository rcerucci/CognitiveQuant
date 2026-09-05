"""Success Criteria Verification Tests (SC-001 to SC-004)."""

import pytest
import json
from pathlib import Path
from motor.ohlc.validation import validate_bar, validate_bars_sequence, ValidationError
from motor.ohlc.transform import transform_to_returns

class TestSC001:
    """SC-001: 100% das violações resultam em Abort com log correto."""
    
    def test_format_invalido(self):
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75]  # Missing fields
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar)
        assert exc_info.value.code == "format_invalido"

    def test_integridade_preco_invalida(self):
        bar = [1704067200000, 100.50, 99.00, 100.25, 100.75, 100.50, 101.00]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar)
        assert exc_info.value.code == "integridade_preco_invalida"

    def test_ordem_temporal_invalida(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704067200000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25]
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_bars_sequence(bars)
        assert exc_info.value.code == "ordem_temporal_invalida"

class TestSC002:
    """SC-002: Gap behavior matches spec."""
    
    def test_gap_1_interpolated(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704070800000, 101.00, 101.50, 100.80, 101.25, 101.00, 101.50]
        ]
        result = validate_bars_sequence(bars)
        assert len(result.bars) == 3
    
    def test_gap_5_neutro(self):
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704078000000, 103.00, 103.50, 102.75, 103.25, 103.00, 103.50]
        ]
        result = validate_bars_sequence(bars)
        assert result.bars[1].status.value == "neutro"

class TestSC003:
    """SC-003: Transform values match reference."""
    
    def test_transform_values(self):
        bars = [
            [1704067200000, 100.0, 101.0, 99.0, 100.5, 100.0, 101.0],
            [1704069000000, 100.5, 101.5, 100.0, 101.0, 100.5, 101.5]
        ]
        result = validate_bars_sequence(bars)
        transform = transform_to_returns(result)
        
        assert transform.P_t[0] == pytest.approx(100.5)
        assert transform.P_t[1] == pytest.approx(101.0)
        assert len(transform.r_t) == 1  # t >= 1

class TestSC004:
    """SC-004: No filter dependencies."""
    
    def test_no_filter_imports(self):
        # Verify no filter modules are imported
        import sys
        forbidden = ['motor.filtros', 'motor.hurst', 'motor.garch']
        for mod in forbidden:
            assert mod not in sys.modules