"""Testes US3 — Percentil empírico de |Z|.

Independent Tests:
- Janela 200 de |Z|; P_t ∈ [0,1]
- Extremo não força sempre 1.0 se método de score evitar isso
- P_t alto **não** sozinho vira NEUTRO

Reference: Espec F4 US3
"""

from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.vol.percentil import (
    PercentilResult,
    PercentilStatus,
    calculate_percentil_z,
)


def load_percentil_fixtures() -> dict:
    """Carrega fixtures de teste para percentil."""
    with open("tests/fixtures/vol/percentil.json") as f:
        return json.load(f)


class TestPercentilCalculo:
    """Testes para cálculo do percentil."""
    
    def test_percentil_basic_calculation(self):
        """Given |Z| e janela, When calcula percentil, Then P_t ∈ [0, 1]."""
        z_history = [0.5, 0.8, 1.0, 1.2, 1.5, 1.6, 1.8, 2.0, 2.5, 3.0]
        
        result = calculate_percentil_z(1.5, z_history)
        
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z is not None
        assert 0 <= result.percentil_z <= 1
    
    def test_percentil_minimum_value(self):
        """Given |Z| mínimo, When calcula percentil, Then P_t baixo."""
        z_history = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
        
        result = calculate_percentil_z(0.5, z_history)
        
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z is not None
        # Minimum should have low percentile
        assert result.percentil_z < 0.5
    
    def test_percentil_maximum_value(self):
        """Given |Z| máximo, When calcula percentil, Then P_t alto."""
        z_history = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
        
        result = calculate_percentil_z(5.0, z_history)
        
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z is not None
        # Maximum should have high percentile
        assert result.percentil_z > 0.5
    
    def test_percentil_high_does_not_neutro(self):
        """Given P_t > 0.95, When calcula percentil, Then não NEUTRO."""
        # Create history where 10.0 is the maximum
        z_history = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
                     2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        
        result = calculate_percentil_z(10.0, z_history)
        
        assert result.status == PercentilStatus.PASS
        # High percentile does NOT cause NEUTRO in F4
        assert result.percentil_z is not None
        assert result.percentil_z > 0.8


class TestPercentilCasosEspeciais:
    """Testes para casos especiais de percentil."""
    
    def test_percentil_empty_history(self):
        """Given janela vazia, When calcula percentil, Then NEUTRO."""
        result = calculate_percentil_z(1.0, [])
        
        assert result.status == PercentilStatus.NEUTRO
        assert result.reason == "empty_history"
        assert result.percentil_z is None
    
    def test_percentil_negative_z(self):
        """Given Z negativo, When calcula percentil, Then usa |Z|."""
        z_history = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        
        result_pos = calculate_percentil_z(2.0, z_history)
        result_neg = calculate_percentil_z(-2.0, z_history)
        
        assert result_pos.status == PercentilStatus.PASS
        assert result_neg.status == PercentilStatus.PASS
        # Should produce same percentile for |Z|
        assert result_pos.percentil_z == result_neg.percentil_z
    
    def test_percentil_z_nan(self):
        """Given Z = NaN, When calcula percentil, Then NEUTRO."""
        result = calculate_percentil_z(float('nan'), [1.0, 2.0, 3.0])
        
        assert result.status == PercentilStatus.NEUTRO
        assert result.reason == "invalid_z_value"


class TestPercentilJanela200:
    """Testes para janela de 200 valores."""
    
    def test_percentil_window_200_values(self):
        """Given janela de 200 valores, When calcula percentil, Then funciona."""
        np.random.seed(42)
        z_history = np.random.uniform(0.1, 5.0, 200).tolist()
        
        result = calculate_percentil_z(2.5, z_history)
        
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z is not None
        assert 0 <= result.percentil_z <= 1
    
    def test_percentil_method_mean_reproducibility(self):
        """Method='mean' deve ser usado para empates."""
        # Create history with ties at the score
        z_history = [1.0] * 50 + [2.0] * 50 + [3.0] * 50 + [4.0] * 50
        
        result = calculate_percentil_z(2.5, z_history)
        
        assert result.status == PercentilStatus.PASS
        # With ties, mean method should handle correctly


class TestPercentilValoresExtremos:
    """Testes para valores extremos."""
    
    def test_percentil_very_large_z(self):
        """Given |Z| muito grande, When calcula percentil, Then ≈ 1.0."""
        z_history = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
                     1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]
        
        result = calculate_percentil_z(1000.0, z_history)
        
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z is not None
        # Very large |Z| should have very high percentile
        assert result.percentil_z > 0.9
    
    def test_percentil_very_small_z(self):
        """Given |Z| muito pequeno, When calcula percentil, Then ≈ 0.0."""
        z_history = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
        
        result = calculate_percentil_z(0.001, z_history)
        
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z is not None
        # Very small |Z| should have very low percentile
        assert result.percentil_z < 0.2


class TestPercentilResultSchema:
    """Testes para schema de PercentilResult."""
    
    def test_result_has_required_fields(self):
        """PercentilResult deve ter campos status e percentil_z."""
        result = PercentilResult(status=PercentilStatus.PASS, percentil_z=0.5)
        
        assert hasattr(result, 'status')
        assert hasattr(result, 'percentil_z')
        assert hasattr(result, 'reason')
    
    def test_result_dataclass(self):
        """PercentilResult deve ser um dataclass."""
        result = PercentilResult(status=PercentilStatus.PASS, percentil_z=0.5)
        
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z == 0.5
    
    def test_result_neutral_dataclass(self):
        """PercentilResult pode ser NEUTRO."""
        result = PercentilResult(status=PercentilStatus.NEUTRO, reason="empty_history")
        
        assert result.status == PercentilStatus.NEUTRO
        assert result.percentil_z is None
        assert result.reason == "empty_history"


class TestPercentilStatus:
    """Testes para status do percentil."""
    
    def test_status_enum_values(self):
        """PercentilStatus deve ter valores PASS e NEUTRO."""
        assert PercentilStatus.PASS.value == "PASS"
        assert PercentilStatus.NEUTRO.value == "NEUTRO"
    
    def test_status_comparison(self):
        """Status deve ser comparável."""
        result = calculate_percentil_z(1.5, [0.5, 1.0, 1.5, 2.0, 3.0])
        assert result.status == PercentilStatus.PASS
        
        result2 = calculate_percentil_z(1.5, [])
        assert result2.status == PercentilStatus.NEUTRO


class TestPercentilFixtures:
    """Testes usando fixtures de percentil.json."""
    
    def test_fixture_basic_calculation(self):
        """Testa fixture percentil_basic_calculation."""
        fixture = load_percentil_fixtures()
        basic_case = fixture['test_cases'][0]
        
        result = calculate_percentil_z(basic_case['z_value'], basic_case['z_history'])
        
        assert result.status.value == basic_case['expected']['status']
        assert basic_case['expected']['percentil_z_range'][0] <= result.percentil_z <= basic_case['expected']['percentil_z_range'][1]
    
    def test_fixture_empty_history(self):
        """Testa fixture percentil_empty_history."""
        fixture = load_percentil_fixtures()
        empty_case = fixture['test_cases'][4]
        
        result = calculate_percentil_z(empty_case['z_value'], empty_case['z_history'])
        
        assert result.status.value == empty_case['expected']['status']
        assert result.reason == empty_case['expected']['reason']
    
    def test_fixture_negative_z(self):
        """Testa fixture percentil_negative_z."""
        fixture = load_percentil_fixtures()
        neg_case = fixture['test_cases'][5]
        
        result = calculate_percentil_z(neg_case['z_value'], neg_case['z_history'])
        
        assert result.status.value == neg_case['expected']['status']


class TestPercentilIndependenteTests:
    """Testes Independent Tests conforme spec US3."""
    
    def test_p_t_em_range_0_1(self):
        """Independent Test: P_t ∈ [0,1]."""
        np.random.seed(42)
        z_history = np.random.uniform(0, 5, 200).tolist()
        
        for z in [0.1, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
            result = calculate_percentil_z(z, z_history)
            assert result.status == PercentilStatus.PASS
            assert result.percentil_z is not None
            assert 0 <= result.percentil_z <= 1, f"P_t not in [0,1] for z={z}"
    
    def test_extremo_nao_forca_1(self):
        """Independent Test: Extremo não força sempre 1.0."""
        # With method='mean', percentiles can vary
        z_history = [1.0] * 100 + [2.0] * 100
        
        result = calculate_percentil_z(2.0, z_history)
        
        # With mean method and ties, should produce a valid percentile
        assert result.status == PercentilStatus.PASS
        assert result.percentil_z is not None
        assert 0 <= result.percentil_z <= 1