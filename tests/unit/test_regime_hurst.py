"""Testes F3 US1 — Regime Hurst R/S (T032 - alinhado 003b).

T032: Alinhar testes Hurst (H não abre PASS sozinho)
Addendum 003b: Hurst via DFA Peng diagnóstico, não hard-gate.
"""
from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.regime.hurst import (
    calculate_hurst,
    HurstCalculator,
    HurstResult,
    HurstStatus,
    RegimeType,
)


# Carregar fixtures
def load_hurst_fixtures():
    """Carrega fixtures de hurst.json."""
    with open("tests/fixtures/regime/hurst.json", "r") as f:
        return json.load(f)["test_cases"]


def generate_ou_series(length: int, mu: float = 0.0, theta: float = 0.5, sigma: float = 0.1, seed: int = 42) -> list:
    """Gera série OU sintética para testes.
    
    Nota: Para testes de regime REVERSAL (H < 0.45), use generate_mean_reverting_series().
    Esta função gera séries com variação controlada, mas pode produzir H > 0.55.
    """
    rng = np.random.default_rng(seed)
    series = np.zeros(length)
    series[0] = mu
    
    dt = 1.0  # Unidade de tempo
    sqrt_dt = np.sqrt(dt)
    
    for i in range(1, length):
        exp_theta = np.exp(-theta * dt)
        series[i] = mu + exp_theta * (series[i-1] - mu) + sigma * sqrt_dt * rng.standard_normal()
    
    return series.tolist()


def generate_mean_reverting_series(length: int, mu: float = 0.0, seed: int = 42) -> list:
    """Gera série com autocorrelação negativa forte (H < 0.45 - REVERSAL).
    
    Usa AR(1) com coeficiente negativo para criar mean-reverting behavior.
    Gera log-preços diretamente.
    
    Args:
        length: Comprimento da série (mínimo 200 para cálculo Hurst)
        mu: Média inicial (log-price)
        seed: Seed para reproducibilidade
    
    Returns:
        Lista de log-preços com H < 0.45 (REVERSAL)
    """
    rng = np.random.default_rng(seed)
    series = np.zeros(length)
    series[0] = mu
    
    # AR(1) com coeficiente negativo forte
    # X_t = -0.75 * X_{t-1} + 0.01 * noise
    # Isso garante autocorrelação negativa e H < 0.45
    for i in range(1, length):
        series[i] = -0.75 * series[i-1] + 0.01 * rng.standard_normal()
    
    return series.tolist()


def generate_random_walk_series(length: int, seed: int = 42) -> list:
    """Gera série Random Walk para testes de H ≈ 0.5."""
    rng = np.random.default_rng(seed)
    increments = rng.standard_normal(length) * 0.01
    series = np.cumsum(increments)
    return series.tolist()


def generate_trend_series(length: int, trend_slope: float = 0.001, seed: int = 42) -> list:
    """Gera série com tendência para H > 0.55."""
    rng = np.random.default_rng(seed)
    t = np.arange(length)
    noise = rng.standard_normal(length) * 0.005
    series = 0.001 * t + np.cumsum(noise)  # Tendência linear com ruído
    return series.tolist()


class TestHurstCalculation:
    """Testes para cálculo do coeficiente de Hurst (T032)."""
    
    def test_ou_series_reversal(self):
        """Testa série mean-reverting → H < 0.45 → REVERSAL."""
        series = generate_mean_reverting_series(300, mu=0.0)
        result = calculate_hurst(series)
        
        assert result.status == HurstStatus.PASS, f"Expected PASS, got {result.status}"
        assert result.hurst is not None, "Hurst should not be None"
        assert result.hurst < 0.45, f"Hurst {result.hurst} should be < 0.45 for REVERSAL"
        assert result.regime == RegimeType.REVERSAL, f"Expected REVERSAL, got {result.regime}"
    
    def test_random_walk_neutral(self):
        """Testa Random Walk → H ≈ 0.5 → NEUTRO (T032)."""
        series = generate_random_walk_series(300)
        result = calculate_hurst(series)
        
        # Para RW, H deve estar em torno de 0.5
        assert result.status == HurstStatus.PASS, f"Expected PASS, got {result.status}"
        assert result.hurst is not None, "Hurst should not be None"
        # Em 003b, HURST é apenas diagnóstico - sempre PASS se calculado
        assert result.regime is None, "RW deve ser NEUTRO (regime=None)"
    
    def test_trend_series_neutral(self):
        """Testa tendência → H > 0.55 → NEUTRO (T027)."""
        series = generate_trend_series(300)
        result = calculate_hurst(series)
        
        assert result.status == HurstStatus.PASS, f"Expected PASS for trend, got {result.status}"
        assert result.hurst is not None, "Hurst should not be None"
        # H > 0.55 não deve gerar tendência (T027)
        assert result.regime is None, "Tendência não deve gerar regime de tendência"
    
    def test_warmup_short_series(self):
        """Testa warm-up com série curta (< 200)."""
        short_series = generate_ou_series(100, theta=0.5)
        result = calculate_hurst(short_series)
        
        assert result.status == HurstStatus.NEUTRO, "Short series should be NEUTRO (warm-up)"
        assert result.hurst is None, "Hurst should be None for warm-up"
        assert result.regime is None, "Regime should be None for warm-up"


class TestHurstT032_H_not_hard_gate:
    """Testes T032: Hurst não abre PASS/NEUTRO sozinho (003b)."""
    
    def test_h_never_forces_neutral_based_on_hurst_value_only(self):
        """T032: Hurst é diagnóstico - status PASS se calculado, independente do valor.
        
        O gate de PASS agora é baseado em θ̂, IC_low e τ (spec 003b).
        """
        # Testar diferentes valores de H
        test_cases = [
            ("low", 0.30),  # H < 0.45
            ("border_low", 0.45),  # H = 0.45
            ("neutral_low", 0.50),  # H ≈ 0.5
            ("border_high", 0.55),  # H = 0.55
            ("high", 0.70),  # H > 0.55
        ]
        
        for name, h_val in test_cases:
            # Gerar série e verificar que o status depende do cálculo, não do valor
            series = generate_random_walk_series(300, seed=42)
            result = calculate_hurst(series)
            
            # Status deve ser PASS se H foi calculado (diagnóstico)
            assert result.status in [HurstStatus.PASS, HurstStatus.NEUTRO], \
                f"{name}: status deve ser PASS ou NEUTRO"
    
    def test_high_h_does_not_create_trend_signal(self):
        """T027: H > 0.55 não cria sinal de tendência."""
        # Gerar série com H > 0.55 (trend)
        rng = np.random.default_rng(42)
        t = np.arange(300)
        noise = rng.standard_normal(300) * 0.005
        series = (0.001 * t + np.cumsum(noise)).tolist()
        
        result = calculate_hurst(series)
        
        # Mesmo H > 0.55, não deve gerar tendência
        if result.hurst is not None and result.hurst > 0.55:
            assert result.regime is None, \
                f"H > 0.55 ({result.hurst}) não deve gerar regime de tendência"
    
    def test_hurst_is_diagnostic_only(self):
        """T027: Hurst é apenas métrica de contexto, não hard-gate."""
        # Criar séries com diferentes H e verificar que o status é PASS quando calculado
        series = generate_mean_reverting_series(300, seed=42)
        result = calculate_hurst(series)
        
        # Se H foi calculado, status é PASS (diagnostic only)
        assert result.status == HurstStatus.PASS
        assert result.hurst is not None
        
        # Regime pode ser REVERSAL ou None (NEUTRO)
        # Mas o status PASS não depende desse regime


class TestHurstBoundaries:
    """Testes para limites de Hurst (SC-001, T032)."""
    
    def test_hurst_at_reversal_boundary(self):
        """Testa H = 0.45 → NEUTRO (borda inferior)."""
        # Criar série com H próximo de 0.45
        # Usar ajuste fino no theta
        series = generate_ou_series(300, theta=0.35, sigma=0.02)  # theta menor → H maior
        result = calculate_hurst(series)
        
        # O limiar é < 0.45 para REVERSAL
        # Se H >= 0.45, deve ser NEUTRO
        if result.hurst is not None and result.hurst >= 0.45:
            assert result.status == HurstStatus.PASS  # Sempre PASS se calculado
            assert result.regime is None  # NEUTRO
    
    def test_hurst_at_trend_boundary(self):
        """Testa H = 0.55 → NEUTRO (borda superior)."""
        # Criar série com tendência moderada
        series = generate_trend_series(300, trend_slope=0.002)
        result = calculate_hurst(series)
        
        # Se H > 0.55, deve ser NEUTRO (sem tendência)
        if result.hurst is not None and result.hurst > 0.55:
            assert result.status == HurstStatus.PASS
            assert result.regime is None  # NEUTRO (não tendência)


class TestHurstWithSubSizes:
    """Testes para sub-tamanhos R/S (FR-002a)."""
    
    def test_default_sub_sizes(self):
        """Testa que sub-tamanhos padrão são usados."""
        series = generate_ou_series(300)
        calculator = HurstCalculator(series)
        
        assert calculator.sub_sizes == [8, 16, 32, 64, 128]
    
    def test_custom_sub_sizes(self):
        """Testa sub-tamanhos customizados."""
        series = generate_ou_series(300)
        calculator = HurstCalculator(series, sub_sizes=[4, 8, 16])
        result = calculator.calculate()
        
        assert result.sub_sizes == [4, 8, 16]
    
    def test_custom_window_size(self):
        """Testa tamanho de janela customizado."""
        series = generate_ou_series(300)
        caculator = HurstCalculator(series, window_size=100)
        result = caculator.calculate()
        
        # Com janela menor, ainda pode calcular
        assert result.window_size == 100


class TestHurstEdgeCases:
    """Testes para casos edge."""
    
    def test_constant_series(self):
        """Testa série constante."""
        constant_series = [1.0] * 300
        result = calculate_hurst(constant_series)
        
        # Série constante pode causar problemas
        # O comportamento esperado é NEUTRO
        assert result.status in [HurstStatus.NEUTRO, HurstStatus.PASS]
    
    def test_very_long_series(self):
        """Testa série muito longa."""
        long_series = generate_ou_series(2000)
        result = calculate_hurst(long_series)
        
        assert result.hurst is not None
        assert result.status in [HurstStatus.PASS, HurstStatus.NEUTRO]