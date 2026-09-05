"""Testes F3 US3 — Bootstrap de θ e CV."""
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


class TestBootstrapSigmaCapitalTheta:
    """Testes para bootstrap CV = σ_θ / μ_θ (US3)."""

    def test_cv_le_030_stable(self):
        """Testa CV ≤ 0.30 → θ estável (SC-003)."""
        thetas = [0.1, 0.12, 0.09, 0.11, 0.08, 0.13, 0.1, 0.11, 0.09, 0.12]
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status == BootstrapStatus.PASS
        assert result.is_stable is True
        assert result.forca_penalty_cv is False
        assert result.cv_theta is not None
        assert result.cv_theta <= 0.30

    def test_cv_gt_030_flag_penalty(self):
        """Testa CV > 0.30 → flag forca_penalty_cv sem NEUTRO (SC-003)."""
        thetas = [0.05, 0.25, 0.08, 0.18, 0.12, 0.22, 0.09, 0.19, 0.11, 0.21]
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        # Status PASS mas com penalização
        assert result.status == BootstrapStatus.PASS
        assert result.is_stable is False
        assert result.forca_penalty_cv is True
        assert result.cv_theta is not None
        assert result.cv_theta > 0.30

    def test_mu_theta_approx_zero_neutro(self):
        """Testa μ_θ ≈ 0 → NEUTRO (SC-003)."""
        thetas = [0.001, -0.002, 0.0005, -0.001, 0.002, -0.0005, 0.001, -0.001, 0.0008, -0.0003]
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status == BootstrapStatus.NEUTRO
        assert result.cv_theta is None  # Indefinido quando μ_θ ≈ 0

    def test_single_theta_stable(self):
        """Testa bootstrap com único θ → CV = 0, estável."""
        thetas = [0.15]
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status == BootstrapStatus.PASS
        assert result.cv_theta == 0.0
        assert result.is_stable is True
        assert result.forca_penalty_cv is False

    def test_empty_thetas_neutro(self):
        """Testa bootstrap com lista vazia → NEUTRO."""
        result = bootstrap_theta([], n_bootstrap=50, seed=42)

        assert result.status == BootstrapStatus.NEUTRO
        assert result.mu_theta == 0.0
        assert result.sigma_theta == 0.0

    def test_seed_42_reproducibility(self):
        """Testa que seed=42 é reproduzível (SC-003)."""
        thetas = [0.1, 0.12, 0.09, 0.11, 0.08]

        result1 = bootstrap_theta(thetas, n_bootstrap=50, seed=42)
        result2 = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        # Resultados devem ser idênticos com a mesma seed
        assert result1.cv_theta == result2.cv_theta
        assert result1.mu_theta == result2.mu_theta
        assert result1.sigma_theta == result2.sigma_theta


class TestBootstrapEdgeCases:
    """Testes para casos edge do bootstrap."""

    def test_negative_theta(self):
        """Testa que θ negativo é tratado corretamente."""
        thetas = [-0.1, -0.05, -0.2]
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        # θ negativo pode resultar em NEUTRO ou PASS dependendo de |μ_θ|
        # Se |μ_θ| < MU_THRESHOLD (0.05), deve ser NEUTRO
        if abs(np.mean(np.array(thetas))) < 0.05:
            assert result.status == BootstrapStatus.NEUTRO

    def test_mixed_sign_thetas(self):
        """Testa lista com θ positivos e negativos."""
        thetas = [0.1, -0.05, 0.08, -0.02, 0.1]
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        # Deve lidar com mistura de sinais
        assert result is not None
        assert result.mu_theta is not None


class TestBootstrapFixtures:
    """Testes usando fixtures de bootstrap.json (US3)."""

    def test_stable_theta_fixture(self):
        """Testa fixture stable_theta_cv_le_030."""
        fixture = load_bootstrap_fixtures()[0]
        thetas = fixture["thetas"]
        expected = fixture["expected"]

        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status.value == expected["status"]
        assert result.is_stable == expected["is_stable"]
        assert result.forca_penalty_cv == expected["forca_penalty_cv"]

    def test_unstable_theta_fixture(self):
        """Testa fixture unstable_theta_cv_gt_030."""
        fixture = load_bootstrap_fixtures()[1]
        thetas = fixture["thetas"]
        expected = fixture["expected"]

        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status.value == expected["status"]
        assert result.is_stable == expected["is_stable"]
        assert result.forca_penalty_cv == expected["forca_penalty_cv"]

    def test_mu_theta_zero_fixture(self):
        """Testa fixture mu_theta_aprox_zero."""
        fixture = load_bootstrap_fixtures()[2]
        thetas = fixture["thetas"]
        expected = fixture["expected"]

        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status.value == expected["status"]

    def test_single_theta_fixture(self):
        """Testa fixture single_theta."""
        fixture = load_bootstrap_fixtures()[3]
        thetas = fixture["thetas"]
        expected = fixture["expected"]

        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status.value == expected["status"]
        assert result.is_stable == expected["is_stable"]

    def test_empty_thetas_fixture(self):
        """Testa fixture empty_thetas."""
        fixture = load_bootstrap_fixtures()[4]
        thetas = fixture["thetas"]
        expected = fixture["expected"]

        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.status.value == expected["status"]


class TestBootstrapCalculationDetails:
    """Detalhes do cálculo do bootstrap (SC-003)."""

    def test_cv_calculation(self):
        """Testa cálculo correto de CV = σ_θ / μ_θ."""
        # Criar thetas com CV conhecido
        thetas = [0.1, 0.1, 0.1, 0.1, 0.1]  # CV = 0
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        assert result.cv_theta == 0.0
        assert result.mu_theta == 0.1

    def test_sigma_theta_calculation(self):
        """Testa cálculo de sigma_theta (desvio-padrão sample)."""
        thetas = [0.1, 0.12, 0.08]  # Amostra com variação
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        # sigma deve ser calculado
        assert result.sigma_theta is not None
        assert result.sigma_theta >= 0

    def test_bootstrap_samples_generation(self):
        """Testa que os samples de bootstrap são gerados."""
        thetas = [0.1, 0.11, 0.09, 0.1, 0.1]
        result = bootstrap_theta(thetas, n_bootstrap=50, seed=42)

        # Deve ter 50 samples (theta_samples pode ser None em alguns casos)
        assert result.theta_samples is not None
        assert len(result.theta_samples) == 50

    def test_default_seed_is_42(self):
        """Testa que o seed padrão é 42."""
        thetas = [0.1, 0.12, 0.08]

        result1 = bootstrap_theta(thetas)
        result2 = bootstrap_theta(thetas)

        # Mesmo seed padrão deve gerar resultados idênticos
        assert result1.cv_theta == result2.cv_theta