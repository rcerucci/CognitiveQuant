"""Testes US2 — Direção e força.

Independent Tests:
- Força calculada pela fórmula: 0.35×P_t + 0.25×max(ρ₁,0) + 0.25×|CLV| + 0.15×RB
- Penalizações aplicadas corretamente
- Piso 0.18 respeitado
- Round 2 casas decimais

Reference: Espec F5 US2
"""

from __future__ import annotations

import json
import math
import pytest

from motor.signal.forca import (
    calcular_forca,
    ForcaResult,
    ForcaStatus,
    Direction,
    Confidence,
)


def load_forca_fixtures() -> dict:
    """Carrega fixtures de teste para força."""
    with open("tests/fixtures/signal/forca.json") as f:
        return json.load(f)


class TestForcaBasica:
    """Testes básicos de cálculo de força."""
    
    def test_forca_bruta_calculation(self):
        """Força bruta = 0.35×P_t + 0.25×max(ρ₁,0) + 0.25×|CLV| + 0.15×RB."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=0.3,
            clv=0.5,
            rb=0.6,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        # Força bruta esperada:
        # 0.35*0.80 + 0.25*0.3 + 0.25*0.5 + 0.15*0.6
        # = 0.28 + 0.075 + 0.125 + 0.09 = 0.57
        expected_bruta = 0.35 * 0.80 + 0.25 * 0.3 + 0.25 * 0.5 + 0.15 * 0.6
        
        assert result.forca_bruta is not None
        assert abs(result.forca_bruta - expected_bruta) < 0.01
    
    def test_forca_bruta_none_values(self):
        """Given None values, Força bruta uses 0."""
        result = calcular_forca(
            z_t=None,
            percentil_z=None,
            rho_1=None,
            clv=None,
            rb=None,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        assert result.forca_bruta == 0.0
        assert result.direction == Direction.NEUTRO
        assert result.forca == 0.18  # Piso


class TestDirecao:
    """Testes para determinação de direção."""
    
    def test_direction_long(self):
        """Z_t < 0 → LONG."""
        result = calcular_forca(
            z_t=-1.5,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        assert result.direction == Direction.LONG
    
    def test_direction_short(self):
        """Z_t > 0 → SHORT."""
        result = calcular_forca(
            z_t=1.5,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        assert result.direction == Direction.SHORT
    
    def test_direction_neutro_zero_z(self):
        """Z_t == 0 → NEUTRO."""
        result = calcular_forca(
            z_t=0.0,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        assert result.direction == Direction.NEUTRO


class TestPenalizacoes:
    """Testes para penalizações."""

    def test_penalizacao_skewness(self):
        """|S| in (1, 2) → ×0.70."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=1.5,  # 1 < |S| < 2
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )

        # Força bruta = 0.35*0.8 + 0.25*0.2 + 0.25*0.4 + 0.15*0.5 = 0.565
        # Com penalização skewness: 0.565 * 0.70 = 0.3955
        assert "skewness" in result.penalizacoes_aplicadas

    def test_penalizacao_lb_soft_gate(self):
        """Ljung-Box p >= 0.05 → ×0.70 (soft gate 8.2)."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=0.0,
            cv_theta=None,
            forca_penalty_cv=False,
            lb_soft_gate=True,
            seed=42,
        )

        # Força bruta = 0.35*0.8 + 0.25*0.2 + 0.25*0.4 + 0.15*0.5 = 0.505
        # Com penalização lb_soft: 0.505 * 0.70 = 0.3535
        # Rounded: 0.35
        assert "lb_soft" in result.penalizacoes_aplicadas
        assert abs(result.forca - 0.35) < 0.01

    def test_penalizacao_cv_theta(self):
        """CV_θ > 0.30 → ×0.80."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=0.35,  # > 0.30
            forca_penalty_cv=False,
            seed=42,
        )
        
        assert "cv_theta" in result.penalizacoes_aplicadas
    
    def test_penalizacao_cv_flag(self):
        """forca_penalty_cv=True sem cv_theta → ×0.80."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=True,
            seed=42,
        )
        
        assert "cv_theta" in result.penalizacoes_aplicadas
    
    def test_penalizacao_cv_theta_and_flag(self):
        """cv_theta > 0.30 e forca_penalty_cv=True → apenas um ×0.80."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=0.35,  # > 0.30
            forca_penalty_cv=True,  # Flag também True
            seed=42,
        )
        
        # Apenas uma penalização cv_theta (não duas)
        assert result.penalizacoes_aplicadas.count("cv_theta") == 1
    
    def test_penalizacao_acf_negativo(self):
        """ρ₁ < 0 → ×0.70 (reversão)."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=-0.3,  # Negativo
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        assert "acf_neg" in result.penalizacoes_aplicadas
    
    def test_multiple_penalizacoes(self):
        """Múltiplas penalizações aplicadas em sequência."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=-0.3,  # ACF negativo
            clv=0.4,
            rb=0.5,
            skewness=1.5,  # Skewness (1 < |S| < 2)
            cv_theta=0.35,  # CV alto (> 0.30)
            forca_penalty_cv=True,  # Flag também True (mas sinônimo de cv_theta > 0.30)
            seed=42,
        )
        
        # Penalizações: skewness, cv_theta, acf_neg (3 penalizações)
        # NÃO há cv_penalty_flag adicional pois cv_theta > 0.30 já cobre
        assert len(result.penalizacoes_aplicadas) == 3
        assert "skewness" in result.penalizacoes_aplicadas
        assert "cv_theta" in result.penalizacoes_aplicadas
        assert "acf_neg" in result.penalizacoes_aplicadas


class TestPisoECasoDecimais:
    """Testes para piso e arredondamento."""
    
    def test_piso_018_respeitado(self):
        """Força não cai abaixo de 0.18."""
        result = calcular_forca(
            z_t=0.5,
            percentil_z=0.30,
            rho_1=-0.5,  # ACF negativo
            clv=0.1,
            rb=0.1,
            skewness=1.5,  # Skewness
            cv_theta=0.35,  # CV alto
            forca_penalty_cv=True,
            seed=42,
        )
        
        # Força final deve ser >= 0.18
        assert result.forca >= 0.18
    
    def test_rounding_2_casas(self):
        """Força arredondada para 2 casas decimais."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.7234,
            rho_1=0.2567,
            clv=0.4444,
            rb=0.5555,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        # Verificar que tem apenas 2 casas decimais
        assert result.forca == round(result.forca, 2)
    
    def test_forca_exatamente_018(self):
        """Força exatamente 0.18 é permitida (piso)."""
        result = calcular_forca(
            z_t=0.5,
            percentil_z=0.0,  # Mínimo
            rho_1=-0.5,  # ACF negativo
            clv=0.0,
            rb=0.0,
            skewness=1.5,  # Skewness extrema
            cv_theta=0.35,  # CV alto
            forca_penalty_cv=True,
            seed=42,
        )
        
        assert result.forca == 0.18


class TestForcaEdgeCases:
    """Testes para casos de borda."""
    
    def test_clv_negative_not_capped(self):
        """CLV negativo usado no cálculo (abs no RB, mas CLV pode ser negativo)."""
        # CLV negativo significa close < low
        # Mas |CLV| é usado na fórmula
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.80,
            rho_1=0.2,
            clv=-0.5,  # Negativo
            rb=0.6,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        # |CLV| = 0.5
        assert result.forca_bruta is not None
    
    def test_forca_without_penalizacoes(self):
        """Força sem penalizações."""
        result = calcular_forca(
            z_t=-1.5,
            percentil_z=0.95,
            rho_1=0.4,
            clv=0.6,
            rb=0.7,
            skewness=0.0,  # Sem skewness extrema
            cv_theta=0.1,  # CV baixo
            forca_penalty_cv=False,  # Sem flag
            seed=42,
        )
        
        assert len(result.penalizacoes_aplicadas) == 0
        # Força bruta = 0.35*0.95 + 0.25*0.4 + 0.25*0.6 + 0.15*0.7
        # = 0.3325 + 0.1 + 0.15 + 0.105 = 0.6875
        # SEM penalizações, força deve ser 0.69 (round)
        expected = round(0.35*0.95 + 0.25*0.4 + 0.25*0.6 + 0.15*0.7, 2)
        assert result.forca == expected


class TestForcaFixtures:
    """Testes usando fixtures de forca.json."""
    
    def test_fixture_direction_validation(self):
        """Valida direção nos fixtures."""
        fixture_cases = load_forca_fixtures()
        
        for case in fixture_cases["test_cases"]:
            result = calcular_forca(
                z_t=case["z_t"],
                percentil_z=case["percentil_z"],
                rho_1=case["rho_1"],
                clv=case["clv"],
                rb=case["rb"],
                skewness=case["skewness"],
                cv_theta=case["cv_theta"],
                forca_penalty_cv=case["forca_penalty_cv"],
                seed=42,
            )
            
            expected = case["expected"]
            
            # Verificar direção
            assert result.direction.value == expected["direction"], \
                f"TestCase {case['name']}: direção {result.direction.value} != {expected['direction']}"
    
    def test_fixture_penalizacoes_validation(self):
            """Valida penalizações nos fixtures."""
            fixture_cases = load_forca_fixtures()

            for case in fixture_cases["test_cases"]:
                # Build kwargs dynamically - lb_soft_gate is optional
                kwargs = {
                    "z_t": case["z_t"],
                    "percentil_z": case["percentil_z"],
                    "rho_1": case["rho_1"],
                    "clv": case["clv"],
                    "rb": case["rb"],
                    "skewness": case["skewness"],
                    "cv_theta": case["cv_theta"],
                    "forca_penalty_cv": case["forca_penalty_cv"],
                    "seed": 42,
                }
                if "lb_soft_gate" in case:
                    kwargs["lb_soft_gate"] = case["lb_soft_gate"]

                result = calcular_forca(**kwargs)

                expected = case["expected"]

                if "penalizacoes" in expected:
                    for penal in expected["penalizacoes"]:
                        assert penal in result.penalizacoes_aplicadas, \
                            f"TestCase {case['name']}: penalização {penal} não aplicada"


class TestForcaResultSchema:
    """Testes para schema de ForcaResult."""
    
    def test_result_has_required_fields(self):
        """ForcaResult deve ter todos os campos obrigatórios."""
        result = calcular_forca(
            z_t=-1.0,
            percentil_z=0.8,
            rho_1=0.2,
            clv=0.4,
            rb=0.5,
            skewness=None,
            cv_theta=None,
            forca_penalty_cv=False,
            seed=42,
        )
        
        assert hasattr(result, 'status')
        assert hasattr(result, 'direction')
        assert hasattr(result, 'forca')
        assert hasattr(result, 'forca_bruta')
        assert hasattr(result, 'penalizacoes_aplicadas')
        assert hasattr(result, 'rho_1')
        assert hasattr(result, 'cv_theta')
        assert hasattr(result, 'skewness')
        assert hasattr(result, 'reason')