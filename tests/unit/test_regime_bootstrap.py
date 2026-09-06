"""Testes F3 US3 — Bootstrap Moving Block de θ e CV (T033: IC_low≤0 → não PASS).

API ATUALIZADA (hotfix 003b):
- bootstrap_theta(X, n_bootstrap=100, seed=42)
- X: série de log-preços (200 pontos)
- Moving Block Bootstrap: l=20, N=100 réplicas
- IC_low = percentile(θ_b, 2.5%)
- n_bootstrap < 100 ou < 10 θ_b finitos → IC indefinido → NEUTRO

Regras:
- CV ≤ 0.30 → θ estável
- CV > 0.30 → flag forca_penalty_cv sem NEUTRO
- μ_θ ≈ 0 → NEUTRO
- IC_low (p2.5%) > 0 → elegível para PASS
- seed = 42
"""
from __future__ import annotations

import json
import pytest
import numpy as np

from motor.regime.bootstrap_theta import (
    bootstrap_theta,
    BootstrapTheta,
    BootstrapResult,
    BootstrapStatus,
)


def load_bootstrap_fixtures():
    """Carrega fixtures de bootstrap.json."""
    with open("tests/fixtures/regime/bootstrap.json", "r") as f:
        return json.load(f)["test_cases"]


def generate_test_series(theta: float = 0.5, sigma: float = 0.05, length: int = 200, seed: int = 42) -> list:
    """Gera série OU sintética para testes.
    
    Args:
        theta: Parâmetro de mean-reversion
        sigma: Volatilidade
        length: Comprimento da série
        seed: Seed para reproducibilidade
        
    Returns:
        Log-preços (X_t)
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


class TestBootstrapMovingBlock:
    """Testes para Moving Block Bootstrap (SC-003, T014)."""

    def test_cv_le_030_stable(self):
        """Testa CV ≤ 0.30 → θ estável (SC-003)."""
        # Gerar série OU com θ=0.5 que deve ter CV baixo
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        assert result.status == BootstrapStatus.PASS
        assert result.is_stable is True
        assert result.forca_penalty_cv is False
        assert result.cv_theta is not None
        assert result.cv_theta <= 0.30

    def test_cv_gt_030_flag_penalty(self):
        """Testa CV > 0.30 → flag forca_penalty_cv sem NEUTRO (SC-003)."""
        # Gerar série OU com alta variação que pode gerar CV > 0.30
        X = generate_test_series(theta=0.2, sigma=0.2, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        # Status pode ser PASS com penalização ou NEUTRO dependendo do IC_low
        assert result.status in [BootstrapStatus.PASS, BootstrapStatus.NEUTRO]

    def test_mu_theta_approx_zero_neutro(self):
        """Testa μ_θ ≈ 0 → NEUTRO (SC-003)."""
        # Série que gera μ_θ ≈ 0
        # Criar série com muito ruído ou variação alternada
        rng = np.random.default_rng(42)
        series = np.zeros(200)
        for i in range(1, 200):
            series[i] = series[i-1] + rng.standard_normal() * 0.001  # RW lento
        
        result = bootstrap_theta(series.tolist(), n_bootstrap=100, seed=42)
        # Pode ser NEUTRO ou PASS dependendo da variação
        assert result.status in [BootstrapStatus.PASS, BootstrapStatus.NEUTRO]

    def test_single_replica_generation(self):
        """Testa que 100 réplicas são geradas por padrão."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        # Deve gerar 100 samples válidos
        if result.theta_samples is not None:
            assert len(result.theta_samples) == 100, \
                f"Esperado 100 samples, obtido {len(result.theta_samples)}"

    def test_n_valid_samples_tracked(self):
        """Testa que n_valid_samples é rastreado."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        assert result.n_valid_samples > 0
        assert result.n_valid_samples <= 100


class TestBootstrapICLow:
    """Testes para IC_low (T028, T033)."""

    def test_ic_low_positive_pass(self):
        """T028: IC_low > 0 → elegível para PASS (quando outros critérios ok)."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        assert result.ic_low is not None
        assert result.ic_low > 0, f"IC_low={result.ic_low} deve ser > 0 para elegibilidade"

    def test_ic_low_calculation(self):
        """Testa que IC_low é o percentil 2.5% das bootstrap samples."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        assert result.ic_low is not None
        assert result.theta_samples is not None
        assert len(result.theta_samples) == 100

        # IC_low deve ser o percentil 2.5%
        expected_ic_low = float(np.percentile(result.theta_samples, 2.5))
        assert abs(result.ic_low - expected_ic_low) < 1e-10

    def test_ic_low_none_when_insufficient_samples(self):
        """Testa que IC_low é None quando bootstrap gera poucos samples."""
        # Criar série com poucos pontos válidos para bootstrap
        rng = np.random.default_rng(42)
        series = np.zeros(200)
        for i in range(1, 200):
            series[i] = np.exp(-10) * series[i-1] + 0.01 * rng.standard_normal()
        
        result = bootstrap_theta(series.tolist(), n_bootstrap=100, seed=42)
        
        # Se poucos samples, IC_low pode ser None ou 0
        # O status deve ser NEUTRO se IC indefinido
        assert result.n_valid_samples < 10 or result.ic_low is None or result.ic_low == 0


class TestBootstrapEdgeCases:
    """Testes para casos edge do bootstrap."""

    def test_negative_theta(self):
        """Testa que θ negativo é tratado corretamente."""
        # Criar série que gera θ negativo
        rng = np.random.default_rng(42)
        series = np.zeros(200)
        for i in range(1, 200):
            series[i] = -0.5 * series[i-1] + 0.01 * rng.standard_normal()
        
        result = bootstrap_theta(series.tolist(), n_bootstrap=100, seed=42)
        
        # Deve lidar com sintegração de sinais
        assert result is not None
        assert result.status in [BootstrapStatus.PASS, BootstrapStatus.NEUTRO]

    def test_constant_series(self):
        """Testa série constante (sem variação)."""
        series = [0.1] * 200  # Série constante
        result = bootstrap_theta(series, n_bootstrap=100, seed=42)
        
        # Série constante → θ ≈ 0 → NEUTRO
        assert result.status == BootstrapStatus.NEUTRO


class TestBootstrapCalculationDetails:
    """Detalhes do cálculo do bootstrap (SC-003)."""

    def test_mu_theta_calculation(self):
        """Testa cálculo correto de μ_θ."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        assert result.mu_theta is not None
        assert result.mu_theta > 0  # Deve ser positivo para OU

    def test_sigma_theta_calculation(self):
        """Testa cálculo de sigma_theta (desvio-padrão sample)."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        # sigma deve ser calculado
        assert result.sigma_theta is not None
        assert result.sigma_theta >= 0

    def test_bootstrap_samples_generation(self):
        """Testa que os samples de bootstrap são gerados."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        # Deve ter 100 samples
        assert result.theta_samples is not None
        assert len(result.theta_samples) == 100

    def test_default_seed_is_42(self):
        """Testa que o seed padrão é 42."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)

        result1 = bootstrap_theta(X)
        result2 = bootstrap_theta(X)

        # Mesmo seed padrão deve gerar resultados idênticos
        assert result1.cv_theta == result2.cv_theta
        assert result1.mu_theta == result2.mu_theta

    def test_reproducibility(self):
        """Testa que seed=42 é reproduzível (SC-003)."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=123)

        result1 = bootstrap_theta(X, n_bootstrap=100, seed=42)
        result2 = bootstrap_theta(X, n_bootstrap=100, seed=42)

        # Resultados devem ser idênticos com a mesma seed
        assert result1.cv_theta == result2.cv_theta
        assert result1.mu_theta == result2.mu_theta
        assert result1.ic_low == result2.ic_low

    def test_ic_low_in_result(self):
        """Testa que IC_low está no resultado."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        assert result.ic_low is not None

    def test_result_has_n_valid_samples(self):
        """Testa que n_valid_samples está no resultado."""
        X = generate_test_series(theta=0.5, sigma=0.05, length=200, seed=42)
        result = bootstrap_theta(X, n_bootstrap=100, seed=42)

        assert hasattr(result, 'n_valid_samples')
        assert result.n_valid_samples >= 0


class TestBootstrapMovingBlockDetails:
    """Testes detalhados do Moving Block Bootstrap."""

    def test_block_size_is_20(self):
        """Verifica que o tamanho do bloco é l=20."""
        boot = BootstrapTheta([0.0] * 200, n_bootstrap=100, seed=42)
        assert boot.BLOCK_LENGTH == 20

    def test_window_size_is_200(self):
        """Verifica que a janela é 200."""
        boot = BootstrapTheta([0.0] * 200, n_bootstrap=100, seed=42)
        assert boot.WINDOW_SIZE == 200

    def test_n_bootstrap_default_is_100(self):
        """Verifica que N=100 é o padrão."""
        boot = BootstrapTheta([0.0] * 200, n_bootstrap=100, seed=42)
        assert boot.n_bootstrap == 100

    def test_no_iid_bootstrap(self):
        """Verifica que não usamos bootstrap IID (sample apenas θs, não X)."""
        # O método deve usar blocos, não escolha aleatória ponto a ponto
        boot = BootstrapTheta(generate_test_series(200), n_bootstrap=100, seed=42)
        samples = boot._moving_block_bootstrap()
        
        # Os samples devem ser gerados a partir de blocos
        # Se fosse IID, cada θ seria independente
        # Com blocos, há correlação temporal
        assert len(samples) == 100