"""Testes US2 — Z-score condicional.

Independent Tests:
- Z com μ, X, σ conhecidos → Z bate referência
- σ≤0 ou não-finito → NEUTRO

Reference: Espec F4 US2
"""

from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.vol.zscore import (
    ZScoreResult,
    ZScoreStatus,
    calculate_zscore,
)


def load_zscore_fixtures() -> dict:
    """Carrega fixtures de teste para Z-score."""
    with open("tests/fixtures/vol/zscore.json") as f:
        return json.load(f)


class TestZScoreCalculo:
    """Testes para cálculo básico de Z-score."""
    
    def test_zscore_basic_calculation(self):
        """Given X_t, μ_t, σ_t, When calcula Z, Then Z = (X - μ) / σ."""
        X_t = 0.005
        mu_t = 0.001
        sigma_t = 0.02
        
        result = calculate_zscore(X_t, mu_t, sigma_t)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t is not None
        expected_z = (X_t - mu_t) / sigma_t
        assert abs(result.z_t - expected_z) < 1e-10
    
    def test_zscore_positive_X(self):
        """Given X > μ, When calcula Z, Then Z positivo."""
        result = calculate_zscore(0.01, 0.002, 0.02)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t is not None
        assert result.z_t > 0
    
    def test_zscore_negative_X(self):
        """Given X < μ, When calcula Z, Then Z negativo."""
        result = calculate_zscore(-0.005, 0.001, 0.02)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t is not None
        assert result.z_t < 0
    
    def test_zscore_zero_X_equals_mu(self):
        """Given X = μ, When calcula Z, Then Z = 0."""
        result = calculate_zscore(0.001, 0.001, 0.02)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t is not None
        assert abs(result.z_t) < 1e-10


class TestZScoreCasosEspeciais:
    """Testes para casos especiais de Z-score."""
    
    def test_zscore_sigma_zero(self):
        """Given σ = 0, When calcula Z, Then NEUTRO."""
        result = calculate_zscore(0.001, 0.001, 0.0)
        
        assert result.status == ZScoreStatus.NEUTRO
        assert result.reason == "invalid_sigma_non_positive"
        assert result.z_t is None
    
    def test_zscore_sigma_negative(self):
        """Given σ < 0, When calcula Z, Then NEUTRO."""
        result = calculate_zscore(0.001, 0.001, -0.01)
        
        assert result.status == ZScoreStatus.NEUTRO
        assert result.reason == "invalid_sigma_non_positive"
        assert result.z_t is None
    
    def test_zscore_sigma_nan(self):
        """Given σ = NaN, When calcula Z, Then NEUTRO."""
        result = calculate_zscore(0.001, 0.001, float('nan'))
        
        assert result.status == ZScoreStatus.NEUTRO
        assert result.reason == "invalid_sigma_not_finite"
        assert result.z_t is None
    
    def test_zscore_sigma_infinity(self):
        """Given σ = inf, When calcula Z, Then NEUTRO."""
        result = calculate_zscore(0.001, 0.001, float('inf'))
        
        assert result.status == ZScoreStatus.NEUTRO
        assert result.reason == "invalid_sigma_not_finite"
        assert result.z_t is None
    
    def test_zscore_sigma_negative_infinity(self):
        """Given σ = -inf, When calcula Z, Then NEUTRO."""
        result = calculate_zscore(0.001, 0.001, float('-inf'))
        
        assert result.status == ZScoreStatus.NEUTRO
        assert result.z_t is None


class TestZScoreComSigmaFallback:
    """Testes para Z-score com sigma do fallback."""
    
    def test_zscore_with_fallback_sigma(self):
        """Given σ proveniente do fallback, When calcula Z, Then usa mesma fórmula."""
        # Simulate fallback sigma
        fallback_sigma = 0.015
        X_t = 0.003
        mu_t = 0.001
        
        result = calculate_zscore(X_t, mu_t, fallback_sigma)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t is not None
        expected_z = (X_t - mu_t) / fallback_sigma
        assert abs(result.z_t - expected_z) < 1e-10


class TestZScoreValoresGrandes:
    """Testes para valores numéricos grandes."""
    
    def test_zscore_large_values(self):
        """Given valores grandes, When calcula Z, Then resulta válido."""
        X_t = 1000000.0
        mu_t = 999999.0
        sigma_t = 100.0
        
        result = calculate_zscore(X_t, mu_t, sigma_t)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t is not None
        expected_z = (X_t - mu_t) / sigma_t
        assert abs(result.z_t - expected_z) < 1e-6
    
    def test_zscore_very_small_sigma(self):
        """Given σ muito pequeno, When calcula Z, Then Z grande."""
        X_t = 0.01
        mu_t = 0.0
        sigma_t = 0.0001
        
        result = calculate_zscore(X_t, mu_t, sigma_t)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t is not None
        # Z should be large
        assert abs(result.z_t) > 50


class TestZScoreResultSchema:
    """Testes para schema de ZScoreResult."""
    
    def test_result_has_required_fields(self):
        """ZScoreResult deve ter campos status e z_t."""
        result = ZScoreResult(status=ZScoreStatus.PASS, z_t=1.5)
        
        assert hasattr(result, 'status')
        assert hasattr(result, 'z_t')
        assert hasattr(result, 'reason')
    
    def test_result_dataclass(self):
        """ZScoreResult deve ser um dataclass."""
        result = ZScoreResult(status=ZScoreStatus.PASS, z_t=1.5)
        
        assert result.status == ZScoreStatus.PASS
        assert result.z_t == 1.5


class TestZScoreFixtures:
    """Testes usando fixtures de zscore.json."""
    
    def test_fixture_basic_calculation(self):
        """Testa fixture zscore_basic_calculation."""
        fixture = load_zscore_fixtures()
        basic_case = fixture['test_cases'][0]
        
        result = calculate_zscore(
            basic_case['X_t'],
            basic_case['mu_t'],
            basic_case['sigma_t']
        )
        
        assert result.status.value == basic_case['expected']['status']
        assert abs(result.z_t - basic_case['expected']['z_t']) < 1e-10
    
    def test_fixture_sigma_zero(self):
        """Testa fixture zscore_sigma_zero."""
        fixture = load_zscore_fixtures()
        zero_case = fixture['test_cases'][3]
        
        result = calculate_zscore(
            zero_case['X_t'],
            zero_case['mu_t'],
            zero_case['sigma_t']
        )
        
        assert result.status.value == zero_case['expected']['status']
        assert result.reason == zero_case['expected']['reason']
    
    def test_fixture_sigma_nan(self):
        """Testa fixture zscore_sigma_nan com None."""
        fixture = load_zscore_fixtures()
        nan_case = fixture['test_cases'][6]
        
        result = calculate_zscore(
            nan_case['X_t'],
            nan_case['mu_t'],
            nan_case['sigma_t']
        )
        
        assert result.status.value == nan_case['expected']['status']
        assert result.reason == nan_case['expected']['reason']


class TestZScoreStatus:
    """Testes para status do Z-score."""
    
    def test_status_enum_values(self):
        """ZScoreStatus deve ter valores PASS e NEUTRO."""
        assert ZScoreStatus.PASS.value == "PASS"
        assert ZScoreStatus.NEUTRO.value == "NEUTRO"
    
    def test_status_comparison(self):
        """Status deve ser comparável."""
        result = calculate_zscore(0.01, 0.001, 0.02)
        assert result.status == ZScoreStatus.PASS
        
        result2 = calculate_zscore(0.01, 0.001, 0.0)
        assert result2.status == ZScoreStatus.NEUTRO