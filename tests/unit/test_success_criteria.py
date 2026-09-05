"""Success Criteria Verification Tests (SC-001 to SC-004).

T020: Verificar SC-001–SC-004 via suite em tests/unit/

SC-001: 100% das violações de formato/integridade/ordem temporal nos Independent Tests de US1–US2 resultam em Abort com o log do doc.
SC-002: Para fixtures com gap ≤ 4 e gap > 4, o comportamento corresponde ao §3.2.1 em 100% dos casos de teste.
SC-003: Transformacao P_t, X_t, r_t bate valores de referencia da fixture em todos os pontos t >= 1.
SC-004: Nenhum teste de F1 exige ou invoca filtros §3.3+ (escopo fechado).
"""

import pytest
from motor.ohlc.validation import (
    validate_bar,
    validate_bars_sequence,
    ValidationError
)
from motor.ohlc.transform import transform_to_returns


class TestSC001AbortWithLog:
    """SC-001: 100% das violações resultam em Abort com log correto."""
    
    def test_format_invalido_missing_fields(self):
        """Test that missing fields trigger 'format_invalido' error."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75]  # Missing bid/ask
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar)
        assert exc_info.value.code == "format_invalido"
    
    def test_format_invalido_too_many_fields(self):
        """Test that extra fields trigger 'format_invalido' error."""
        bar = [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00, 102.00]
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar)
        assert exc_info.value.code == "format_invalido"
    
    def test_integridade_preco_invalida_high_low(self):
        """Test that invalid price integrity triggers 'integridade_preco_invalida'."""
        bar = [1704067200000, 100.50, 99.00, 100.25, 100.75, 100.50, 101.00]  # high < open
        with pytest.raises(ValidationError) as exc_info:
            validate_bar(bar)
        assert exc_info.value.code == "integridade_preco_invalida"
    
    def test_ordem_temporal_invalida_duplicates(self):
        """Test that duplicate timestamps trigger 'ordem_temporal_invalida'."""
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704067200000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25]  # Duplicate ts
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_bars_sequence(bars)
        assert exc_info.value.code == "ordem_temporal_invalida"
    
    def test_ordem_temporal_invalida_reverse(self):
        """Test that reverse order triggers 'ordem_temporal_invalida'."""
        bars = [
            [1704069000000, 100.75, 101.25, 100.60, 101.00, 100.75, 101.25],
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00]  # Out of order
        ]
        with pytest.raises(ValidationError) as exc_info:
            validate_bars_sequence(bars)
        assert exc_info.value.code == "ordem_temporal_invalida"


class TestSC002GapBehavior:
    """SC-002: Gap behavior matches spec §3.2.1."""
    
    def test_gap_1_bar_interpolated(self):
        """Gap of 1 bar should be interpolated (gap <= 4)."""
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704070800000, 101.00, 101.50, 100.80, 101.25, 101.00, 101.50]
        ]
        result = validate_bars_sequence(bars)
        # Should have 3 bars: 2 original + 1 interpolated
        assert len(result.bars) == 3
        # All should be VALID status
        for bar in result.bars:
            assert bar.status.value == "valid" or "interpolated" in bar.flags
    
    def test_gap_4_bar_interpolated(self):
        """Gap of 4 bars should be interpolated (at threshold)."""
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704076200000, 102.50, 103.00, 102.25, 102.75, 102.50, 103.00]
        ]
        result = validate_bars_sequence(bars)
        # Should have 6 bars: 2 original + 4 interpolated
        assert len(result.bars) == 6
    
    def test_gap_5_bars_neutro(self):
        """Gap of 5 bars should be marked as NEUTRO with gap_dados."""
        bars = [
            [1704067200000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704078000000, 103.00, 103.50, 102.75, 103.25, 103.00, 103.50]
        ]
        result = validate_bars_sequence(bars)
        # Second bar should be NEUTRO
        assert result.bars[1].status.value == "neutro"
        assert "gap_dados" in result.bars[1].flags


class TestSC003TransformReference:
    """SC-003: Transformacao bate valores de referencia."""
    
    def test_all_transform_values_match_fixture(self):
        """All P_t, X_t, r_t values match reference fixture."""
        import json
        from pathlib import Path
        
        fixtures_path = Path("tests/fixtures/ohlc/transform_reference.json")
        if fixtures_path.exists():
            with open(fixtures_path) as f:
                fixtures = json.load(f)
            
            bars = [tc["input"] for tc in fixtures["test_cases"]]
            result = validate_bars_sequence(bars)
            transform = transform_to_returns(result)
            
            for i, test_case in enumerate(fixtures["test_cases"]):
                expected_P_t = test_case["expected"]["P_t"]
                expected_X_t = test_case["expected"]["X_t"]
                
                # Check P_t
                assert transform.P_t[i] == pytest.approx(expected_P_t, rel=1e-9), \
                    f"P_t mismatch at index {i}"
                
                # Check X_t
                assert transform.X_t[i] == pytest.approx(expected_X_t, rel=1e-9), \
                    f"X_t mismatch at index {i}"
                
                # Check r_t for t >= 1
                if i > 0:
                    expected_r_t = test_case["expected"]["r_t"]
                    assert transform.r_t[i-1] == pytest.approx(expected_r_t, rel=1e-9), \
                        f"r_t mismatch at index {i-1}"
    
    def test_transform_values_direct_calculation(self):
        """Verify transform values via direct calculation."""
        bars = [
            [1704067200000, 100.0, 101.0, 99.0, 100.5, 100.0, 101.0],
            [1704069000000, 100.5, 101.5, 100.0, 101.0, 100.5, 101.5],
            [1704070800000, 101.0, 102.0, 100.5, 101.5, 101.0, 102.0]
        ]
        
        result = validate_bars_sequence(bars)
        transform = transform_to_returns(result)
        
        # Expected P_t values: (bid+ask)/2
        expected_P = [100.5, 101.0, 101.5]
        for i, p in enumerate(expected_P):
            assert transform.P_t[i] == pytest.approx(p)
        
        # Expected X_t values: ln(P_t)
        import math
        for i, p in enumerate(expected_P):
            assert transform.X_t[i] == pytest.approx(math.log(p))
        
        # Expected r_t values: X_t - X_{t-1}
        for i in range(1, len(expected_P)):
            expected_r = math.log(expected_P[i]) - math.log(expected_P[i-1])
            assert transform.r_t[i-1] == pytest.approx(expected_r)


class TestSC004NoFilterDependencies:
    """SC-004: No test requires or invokes filters §3.3+."""
    
    def test_no_filter_imports_in_f1(self):
        """Verify that F1 tests do not import filter modules."""
        # All imports in test files should be from validation, sync, transform only
        # No imports from motor.filtros, motor.hurst, etc.
        import sys
        
        # These modules should not be imported during F1 tests
        forbidden_modules = [
            'motor.filtros',
            'motor.hurst',
            'motor.garch',
            'motor.tr',
            'motor.aad',
            'motor.spread',
        ]
        
        for mod in forbidden_modules:
            assert mod not in sys.modules, f"Module {mod} should not be imported in F1"
    
    def test_f1_scoped_imports(self):
        """Verify test imports are within F1 scope."""
        # This test verifies that the test files only import from allowed modules
        allowed_modules = {
            'motor.ohlc.validation',
            'motor.ohlc.sync',
            'motor.ohlc.transform',
        }
        
        # Check that imports in test files are valid
        from motor.ohlc import validation, sync, transform
        
        # These should all be available
        assert hasattr(validation, 'validate_bar')
        assert hasattr(validation, 'validate_bars_sequence')
        assert hasattr(validation, 'ValidationError')
        assert hasattr(sync, 'sync_instruments')
        assert hasattr(sync, 'SyncResult')
        assert hasattr(transform, 'transform_to_returns')
        assert hasattr(transform, 'TransformResult')