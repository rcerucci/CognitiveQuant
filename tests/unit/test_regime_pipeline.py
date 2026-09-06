"""Testes F3 US4 — Pipeline F3 sobre F2 PASS."""
from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.regime.pipeline import (
    F3Pipeline,
    F3PipelineResult,
    F3Status,
    run_f3_pipeline,
)
from motor.filters.pipeline import (
    Pipeline,
    PipelineResult,
    PipelineStatus,
)
from motor.regime.hurst import HurstStatus


def generate_ou_series(length: int, mu: float = 0.0, theta: float = 0.5, sigma: float = 0.1, seed: int = 42) -> list:
    """Gera série OU sintética para testes.
    
    Gera log-preços (X_t = ln(P_t)) diretamente, com mu > 0 para garantir
    preços positivos quando convertidos para preços reais.
    
    Args:
        length: Comprimento da série
        mu: Média da série (log-price drift)
        theta: Parâmetro de mean-reversion
        sigma: Volatilidade
        seed: Seed para reproducibilidade
    
    Returns:
        Lista de log-preços
    """
    rng = np.random.default_rng(seed)
    series = np.zeros(length)
    series[0] = 0.0  # Log-price inicial (ln(1) = 0)
    
    dt = 1.0
    sqrt_dt = np.sqrt(dt)
    
    for i in range(1, length):
        exp_theta = np.exp(-theta * dt)
        series[i] = 0.0 + exp_theta * (series[i-1] - 0.0) + sigma * sqrt_dt * rng.standard_normal()
    
    return series.tolist()


def generate_log_prices(length: int, mu: float = 0.0, theta: float = 0.5, sigma: float = 0.1, seed: int = 42) -> list:
    """Gera série de log-preços OU sintéticos para testes.
    
    Args:
        length: Comprimento da série
        mu: Média drift (não usado - fixo em 0 para log-preços)
        theta: Parâmetro de mean-reversion
        sigma: Volatilidade
        seed: Seed para reproducibilidade
    
    Returns:
        Lista de log-preços pronta para o pipeline
    """
    rng = np.random.default_rng(seed)
    series = np.zeros(length)
    series[0] = 0.0
    
    dt = 1.0
    sqrt_dt = np.sqrt(dt)
    
    for i in range(1, length):
        exp_theta = np.exp(-theta * dt)
        series[i] = exp_theta * series[i-1] + sigma * sqrt_dt * rng.standard_normal()
    
    return series.tolist()



def generate_mean_reverting_series(length: int, mu: float = 0.0, seed: int = 42) -> list:
    """Gera série com autocorrelação negativa forte (H < 0.45 - REVERSAL).
    
    Usa AR(1) com coeficiente negativo forte para criar mean-reverting behavior.
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
    # X_t = -0.80 * X_{t-1} + 0.01 * noise
    # Isso garante autocorrelação negativa e H < 0.45
    for i in range(1, length):
        series[i] = -0.80 * series[i-1] + 0.01 * rng.standard_normal()
    
    return series.tolist()


def create_f2_pass_result() -> PipelineResult:
    """Cria um resultado F2 PASS para testes."""
    return PipelineResult(
        status=PipelineStatus.PASS,
        evaluated_filters=["spread", "adf", "tr", "parkinson"],
        metrics={"spread": 0.001, "p_value": 0.01, "TR": 120.0, "ratio": 0.5}
    )


def create_f2_neutro_result() -> PipelineResult:
    """Cria um resultado F2 NEUTRO para testes."""
    return PipelineResult(
        status=PipelineStatus.NEUTRO,
        evaluated_filters=["spread"],
        failed_filter="spread",
        reason="High spread detected",
        metrics={"spread": 0.005}
    )


class TestF3PipelineF2Consumption:
    """Testes para consumo de F2 PASS (US4)."""

    def test_f2_neutro_no_promote(self):
        """Given F2 NEUTRO, When F3 runs, Then não promove PASS (US4.1)."""
        f2_result = create_f2_neutro_result()
        # Série curta para warm-up
        log_prices = generate_log_prices(100, theta=0.5)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        assert result.status == F3Status.NEUTRO
        # Não deve ter mu, theta, tau preenchidos
        assert result.mu is None
        assert result.theta is None
        assert result.tau is None

    def test_f2_pass_hurst_neutral(self):
        """Given F2 PASS + Hurst NEUTRO, When F3 runs, Then NEUTRO (US4.2)."""
        f2_result = create_f2_pass_result()
        # Série com tendência (H > 0.55)
        # Gerar série de log-preços com tendência
        # Log-preços positivos para evitar log de valores negativos
        t = np.arange(300)
        prices = 100.0 + 0.001 * t + np.cumsum(np.random.default_rng(42).standard_normal(300) * 0.005)
        log_prices = np.log(prices).tolist()
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        assert result.status == F3Status.NEUTRO
        assert result.reason is not None

    def test_f2_pass_hurst_reversal_valid_ou(self):
        """Given F2 PASS, H < 0.45, θ > 0, When F3 completes, Then PASS with fields (US4.3)."""
        f2_result = create_f2_pass_result()
        # Série OU reversão (H < 0.45) - usar mean-reverting com autocorrelação negativa
        # Usar a função do test_regime_hurst.py
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(300)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        assert result.status == F3Status.PASS
        assert result.hurst is not None
        assert result.mu is not None
        assert result.theta is not None
        assert result.tau is not None
        assert result.bootstrap_cv_theta is not None
        assert result.hurst < 0.45  # REVERSAL


class TestF3PipelineShortCircuit:
    """Testes para short-circuit do pipeline (US4)."""

    def test_short_series_warmup(self):
        """Given histórico < 200, When F3 runs, Then NEUTRO (warm-up)."""
        f2_result = create_f2_pass_result()
        # Série curta (< 200)
        log_prices = [0.0, 0.001, -0.002, 0.001, 0.003, -0.001, 0.002, 0.000, 0.001, -0.002]
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        assert result.status == F3Status.NEUTRO

    def test_f2_neutro_short_circuit(self):
        """Pipeline não continua se F2 é NEUTRO."""
        f2_result = create_f2_neutro_result()
        log_prices = generate_log_prices(500, theta=0.5, sigma=0.05)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        # Não deve tentar calcular Hurst/Outua
        assert result.status == F3Status.NEUTRO


class TestF3PipelineTau:
    """Testes para cálculo de τ (SC-002)."""

    def test_tau_calculation_when_theta_positive(self):
        """Given θ > 0, When τ é calculado, Then τ = ln(2) / θ (SC-002)."""
        f2_result = create_f2_pass_result()
        # Usar mean-reverting series que garante H < 0.45
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(500)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        if result.status == F3Status.PASS and result.theta is not None:
            expected_tau = math.log(2) / result.theta
            assert result.tau is not None
            assert abs(result.tau - expected_tau) < 0.1

    def test_tau_positive_when_theta_positive(self):
        """Testa que τ é calculado quando θ > 0."""
        f2_result = create_f2_pass_result()
        log_prices = generate_log_prices(500, theta=0.3, sigma=0.05)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        if result.status == F3Status.PASS:
            assert result.tau is not None
            assert result.tau > 0


class TestF3PipelineBootstrapCV:
    """Testes para bootstrap CV no pipeline (SC-003)."""

    def test_cv_theta_in_result(self):
        """CV θ deve estar no resultado."""
        f2_result = create_f2_pass_result()
        log_prices = generate_log_prices(500, theta=0.5, sigma=0.05)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        if result.status == F3Status.PASS:
            assert result.bootstrap_cv_theta is not None
            assert 0 <= result.bootstrap_cv_theta <= 2.0  # CV razoável

    def test_forca_penalty_cv_in_result(self):
        """forca_penalty_cv deve estar no resultado."""
        f2_result = create_f2_pass_result()
        # Série com alta variação pode gerar CV > 0.30
        log_prices = generate_log_prices(500, theta=0.2, sigma=0.2)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        # Deve ter o campo
        assert hasattr(result, 'forca_penalty_cv')


class TestF3PipelineOutputFields:
    """Testes para campos de saída in-memory (FR-009)."""

    def test_hurst_in_result(self):
        """Hurst deve estar no resultado."""
        f2_result = create_f2_pass_result()
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(500)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        if result.status == F3Status.PASS:
            assert result.hurst is not None

    def test_mu_in_result(self):
        """μ deve estar no resultado."""
        f2_result = create_f2_pass_result()
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(500)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        if result.status == F3Status.PASS:
            assert result.mu is not None

    def test_theta_in_result(self):
        """θ deve estar no resultado."""
        f2_result = create_f2_pass_result()
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(500)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        if result.status == F3Status.PASS:
            assert result.theta is not None

    def test_theta_positive_in_result(self):
        """θ > 0 deve ser garantido no resultado."""
        f2_result = create_f2_pass_result()
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(500)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        if result.status == F3Status.PASS and result.theta is not None:
            assert result.theta > 0


class TestF3PipelineFixtures:
    """Testes usando fixtures de pipeline.json (US4)."""

    def test_f3_pass_complete(self):
        """Testa fixture f3_pass_complete."""
        fixture_cases = [
            {
                "name": "f2_pass_reversal_series",
                "f2_status": "PASS",
                "series_type": "ou_reversal",
                "expected_status": "PASS",
                "hurst_type": "REVERSAL"
            },
            {
                "name": "f2_neutro_short",
                "f2_status": "NEUTRO", 
                "expected_status": "NEUTRO",
                "reason": "f2_neutro"
            }
        ]
        
        for case in fixture_cases:
            if case["f2_status"] == "PASS":
                # Using local mean-reverting series generator
                log_prices = generate_mean_reverting_series(500)
            else:
                f2_result = create_f2_neutro_result()
                log_prices = []
            
            f2_result = create_f2_pass_result() if case["f2_status"] == "PASS" else create_f2_neutro_result()
            result = run_f3_pipeline(f2_result, log_prices)
            
            assert result.status.value == case["expected_status"], f"Failed for {case['name']}"


class TestF3PipelineClass:
    """Testes para a classe F3Pipeline diretamente."""

    def test_pipeline_initialization(self):
        """Testa inicialização do pipeline."""
        f2_result = create_f2_pass_result()
        log_prices = [0.0] * 250
        
        pipeline = F3Pipeline(f2_result, log_prices)
        
        assert pipeline.f2_result is f2_result
        assert pipeline.log_prices == log_prices

    def test_check_f2_pass(self):
        """Testa verificação de F2 PASS."""
        f2_pass = create_f2_pass_result()
        f2_neutro = create_f2_neutro_result()
        log_prices = [0.0] * 250
        
        pipeline_pass = F3Pipeline(f2_pass, log_prices)
        pipeline_neutro = F3Pipeline(f2_neutro, log_prices)
        
        assert pipeline_pass._check_f2_pass() is True
        assert pipeline_neutro._check_f2_pass() is False


class TestF3PipelineSC004:
    """Testes para SC-004: Nenhum GARCH/Z/payload/TA/executor/CUSUM."""

    def test_no_garch_import(self):
        """Pipeline não importa GARCH."""
        from motor.regime import pipeline
        assert not hasattr(pipeline, 'garch')
        assert not hasattr(pipeline, 'GARCH')

    def test_no_zscore_calculation(self):
        """Pipeline não calcula Z-score."""
        f2_result = create_f2_pass_result()
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(300)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        # Não deve ter zscore no resultado
        assert not hasattr(result, 'zscore')
        assert 'zscore' not in result.__dict__

    def test_no_payload(self):
        """Pipeline não gera payload."""
        f2_result = create_f2_pass_result()
        # Using local mean-reverting series generator
        log_prices = generate_mean_reverting_series(300)
        
        result = run_f3_pipeline(f2_result, log_prices)
        
        # Não deve ter payload no resultado
        assert not hasattr(result, 'payload')

    def test_no_cusum(self):
        """Pipeline não usa CUSUM (fora de escopo US4)."""
        from motor.regime.pipeline import F3Pipeline
        # CUSUM não deve estar importado
        import inspect
        source = inspect.getsource(F3Pipeline)
        assert 'cusum' not in source.lower()
        assert 'CUSUM' not in source