"""Testes US3 — Thresholds 0.75/0.60.

Independent Test:
- Força 0.75 → ALTA
- Força 0.74 → MÉDIA
- Força 0.60 → MÉDIA
- Força 0.59 → NEUTRO
- Sem limiar adaptativo 0.70 em F5

Reference: Espec F5 US3
"""

from __future__ import annotations

import json
import pytest

from motor.signal.thresholds import (
    classificar_confianca,
    ConfidenceLevel,
    get_threshold_bounds,
)


def load_thresholds_fixtures() -> dict:
    """Carrega fixtures de teste para thresholds."""
    with open("tests/fixtures/signal/thresholds.json") as f:
        return json.load(f)


class TestClassificacao:
    """Testes para classificação de confiança."""
    
    def test_alta_threshold_exact(self):
        """Força exatamente 0.75 → ALTA (>=)."""
        result = classificar_confianca(0.75)
        
        assert result == ConfidenceLevel.ALTA
    
    def test_alta_threshold_above(self):
        """Força acima de 0.75 → ALTA."""
        result = classificar_confianca(0.76)
        
        assert result == ConfidenceLevel.ALTA
    
    def test_alta_threshold_high(self):
        """Força alta → ALTA."""
        result = classificar_confianca(0.95)
        
        assert result == ConfidenceLevel.ALTA
    
    def test_media_threshold_above_70(self):
        """Força 0.74 → MÉDIA (< 0.75, mas >= 0.60)."""
        result = classificar_confianca(0.74)
        
        assert result == ConfidenceLevel.MEDIA
    
    def test_media_threshold_exact(self):
        """Força exatamente 0.60 → MÉDIA (>=)."""
        result = classificar_confianca(0.60)
        
        assert result == ConfidenceLevel.MEDIA
    
    def test_media_threshold_below_75(self):
        """Força 0.65 → MÉDIA."""
        result = classificar_confianca(0.65)
        
        assert result == ConfidenceLevel.MEDIA
    
    def test_neutro_threshold_below_60(self):
        """Força 0.59 → NEUTRO (< 0.60)."""
        result = classificar_confianca(0.59)
        
        assert result == ConfidenceLevel.NEUTRO
    
    def test_neutro_threshold_70_is_media(self):
        """Força 0.70 → MÉDIA (0.60 <= 0.70 < 0.75)."""
        result = classificar_confianca(0.70)
        
        assert result == ConfidenceLevel.MEDIA


class TestThresholdBounds:
    """Testes para limites de threshold."""
    
    def test_get_threshold_bounds(self):
        """get_threshold_bounds returns correct bounds."""
        bounds = get_threshold_bounds()
        
        assert "alta" in bounds
        assert "media" in bounds
        assert bounds["alta"] == 0.75
        assert bounds["media"] == 0.60
    
    def test_no_adaptive_threshold(self):
        """F5 usa apenas thresholds fixos 0.75/0.60."""
        # 0.70 está entre 0.60 e 0.75, então é MÉDIA
        result = classificar_confianca(0.70)
        
        assert result == ConfidenceLevel.MEDIA
    
    def test_no_adaptive_threshold_below_60(self):
        """Força < 0.60 é NEUTRO (sem limiar adaptativo)."""
        result = classificar_confianca(0.59)
        
        assert result == ConfidenceLevel.NEUTRO


class TestEdgeCases:
    """Testes para casos de borda."""
    
    def test_neutro_threshold_zero(self):
        """Força zero → NEUTRO."""
        result = classificar_confianca(0.0)
        
        assert result == ConfidenceLevel.NEUTRO
    
    def test_neutro_threshold_floor(self):
        """Força no piso 0.18 → NEUTRO."""
        result = classificar_confianca(0.18)
        
        assert result == ConfidenceLevel.NEUTRO
    
    def test_forca_floor_still_neutro(self):
        """Força pós-penalty que ficou em 0.18 → NEUTRO."""
        result = classificar_confianca(0.18)
        
        assert result == ConfidenceLevel.NEUTRO
    
    def test_boundary_inclusive(self):
        """Verifica que limites são inclusivos (>=)."""
        # 0.75 deve ser ALTA
        assert classificar_confianca(0.75) == ConfidenceLevel.ALTA
        
        # 0.60 deve ser MÉDIA
        assert classificar_confianca(0.60) == ConfidenceLevel.MEDIA
    
    def test_boundary_exclusive_above_075(self):
        """Força acima de 0.75 é ALTA."""
        assert classificar_confianca(0.751) == ConfidenceLevel.ALTA
    
    def test_boundary_exclusive_below_060(self):
        """Força abaixo de 0.60 é NEUTRO."""
        assert classificar_confianca(0.599) == ConfidenceLevel.NEUTRO


class TestFixtures:
    """Testes usando fixtures de thresholds.json."""
    
    def test_all_fixture_cases(self):
        """Testa todos os casos de fixture."""
        fixture_cases = load_thresholds_fixtures()
        
        for case in fixture_cases["test_cases"]:
            result = classificar_confianca(case["forca"])
            
            # Map expected string to enum value
            expected_map = {
                "ALTA": ConfidenceLevel.ALTA,
                "MÉDIA": ConfidenceLevel.MEDIA,
                "MEDIA": ConfidenceLevel.MEDIA,  # Sem acento também aceito
                "NEUTRO": ConfidenceLevel.NEUTRO,
            }
            expected = expected_map[case["expected"]]
            assert result == expected


class TestConfidenceLevelEnum:
    """Testes para enum ConfidenceLevel."""
    
    def test_enum_values(self):
        """ConfidenceLevel has correct values."""
        assert ConfidenceLevel.ALTA.value == "ALTA"
        assert ConfidenceLevel.MEDIA.value == "MÉDIA"
        assert ConfidenceLevel.NEUTRO.value == "NEUTRO"
    
    def test_enum_string_comparison(self):
        """Can compare with string values."""
        assert ConfidenceLevel.ALTA == "ALTA"
        assert ConfidenceLevel.MEDIA == "MÉDIA"
        assert ConfidenceLevel.NEUTRO == "NEUTRO"