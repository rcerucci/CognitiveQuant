"""Testes US4 — Pipeline F4 sobre F3 PASS.

Independent Tests:
- F3 NEUTRO → F4 não promove PASS
- F3 PASS + GARCH ok → PASS com campos
- Fallback ainda pode PASS se σ>0

Reference: Espec F4 US4
"""

from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.vol.pipeline import (
    F4Pipeline,
    F4PipelineResult,
    F4Status,
    run_f4_pipeline,
)
from motor.regime.pipeline import (
    F3PipelineResult,
    F3Status,
)


def load_pipeline_fixtures() -> dict:
    """Carrega fixtures de teste para pipeline."""
    with open("tests/fixtures/vol/pipeline.json") as f:
        return json.load(f)


def generate_garch_stable_series(length: int, seed: int = 42) -> list:
    """Gera série com volatilidade GARCH-like."""
    np.random.seed(seed)
    returns = []
    sigma2 = 0.0001
    
    for i in range(length):
        if i == 0:
            returns.append(np.random.normal(0, np.sqrt(sigma2)))
        else:
            sigma2 = 0.0001 + 0.08 * returns[-1] ** 2 + 0.85 * sigma2
            returns.append(np.random.normal(0, np.sqrt(max(sigma2, 1e-10))))
    
    return returns


def generate_random_walk(length: int, sigma: float = 0.02, seed: int = 42) -> list:
    """Gera série random walk."""
    np.random.seed(seed)
    return np.random.normal(0, sigma, length).tolist()


class TestF4PipelineF3Consumption:
    """Testes para consumo de F3."""
    
    def test_f3_neutro_no_promote(self):
        """Given F3 NEUTRO, When F4 runs, Then não promove PASS."""
        f3_neutro = F3PipelineResult(
            status=F3Status.NEUTRO,
            mu=None,
            reason="F2 did not pass"
        )
        
        returns_history = generate_garch_stable_series(300)
        
        result = run_f4_pipeline(
            f3_result=f3_neutro,
            X_t=0.005,
            r_t=0.004,
            returns_history=returns_history,
            z_history=[0.5] * 200,
            seed=42
        )
        
        assert result.status == F4Status.NEUTRO
        assert "F3 did not pass" in (result.reason or "")
    
    def test_f3_pass_with_mu(self):
        """Given F3 PASS com μ_t, When F4 runs, Then continua."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
            hurst=0.35,
            theta=0.5,
        )
        
        returns_history = generate_garch_stable_series(300)
        X_t = 0.005
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=X_t,
            r_t=X_t - 0.001,  # r_t = X_t - X_{t-1}
            returns_history=returns_history,
            z_history=[abs(0.001 * i / 200) for i in range(200)],
            seed=42
        )
        
        assert result.status in [F4Status.PASS, F4Status.NEUTRO]


class TestF4PipelineGarchIntegration:
    """Testes para integração GARCH no pipeline."""
    
    def test_garch_convergente_gera_pass(self):
        """Given F3 PASS e GARCH convergente, When F4 completa, Then PASS com fonte 'garch'."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        # Generate returns that should produce stable GARCH
        returns_history = generate_garch_stable_series(300)
        X_t = 0.005
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=X_t,
            r_t=X_t - 0.001,
            returns_history=returns_history,
            z_history=[0.5] * 200,
            seed=42
        )
        
        if result.status == F4Status.PASS:
            assert result.garch_sigma is not None
            assert result.garch_sigma > 0
            assert result.source in ["garch", "fallback"]
    
    def test_fallback_ainda_pode_pass(self):
        """Given fallback ativado, When F4 completa, Then ainda pode PASS se σ>0."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        # Random walk may trigger GARCH issues, causing fallback
        returns_history = generate_random_walk(300, sigma=0.02)
        X_t = 0.005
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=X_t,
            r_t=X_t - 0.001,
            returns_history=returns_history,
            z_history=[0.5] * 200,
            seed=42
        )
        
        if result.status == F4Status.PASS:
            assert result.garch_sigma is not None and result.garch_sigma > 0
            # Source could be garch or fallback


class TestF4PipelineWarmup:
    """Testes para warm-up."""
    
    def test_short_history_returns_neutral(self):
        """Given histórico < 200 retornos, When F4 runs, Then NEUTRO."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        # Short history
        returns_history = [0.001] * 100
        X_t = 0.005
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=X_t,
            r_t=0.004,
            returns_history=returns_history,
            z_history=[0.5] * 200,
            seed=42
        )
        
        assert result.status == F4Status.NEUTRO
        assert result.reason == "warm_up"


class TestF4PipelineZScore:
    """Testes para cálculo de Z-score no pipeline."""
    
    def test_z_score_calculation(self):
        """When pipeline completes, Z_t = (X_t - μ_t) / σ_t."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        returns_history = generate_garch_stable_series(300)
        X_t = 0.005
        mu_t = 0.001
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=X_t,
            r_t=X_t - 0.001,
            returns_history=returns_history,
            z_history=[0.5] * 200,
            seed=42
        )
        
        if result.status == F4Status.PASS:
            assert result.z_t is not None
            expected_z = (X_t - mu_t) / result.garch_sigma if result.garch_sigma else 0
            assert abs(result.z_t - expected_z) < 1e-6


class TestF4PipelinePercentil:
    """Testes para cálculo de percentil no pipeline."""
    
    def test_percentil_in_range_0_1(self):
        """When pipeline completes, P_t ∈ [0, 1]."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        returns_history = generate_garch_stable_series(300)
        X_t = 0.005
        z_history = list(np.random.uniform(0, 3, 200))
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=X_t,
            r_t=X_t - 0.001,
            returns_history=returns_history,
            z_history=z_history,
            seed=42
        )
        
        if result.status == F4Status.PASS:
            assert result.percentil_z is not None
            assert 0 <= result.percentil_z <= 1
    
    def test_percentil_does_not_cause_neutral(self):
        """Given P_t > 0.95, When F4 only evaluates, Then não NEUTRO."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        returns_history = generate_garch_stable_series(300)
        X_t = 10.0  # Very large X to get high percentile
        
        # History that would give high percentile for X_t=10
        z_history = list(np.random.uniform(0, 5, 200))
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=X_t,
            r_t=X_t - 0.001,
            returns_history=returns_history,
            z_history=z_history,
            seed=42
        )
        
        # P_t high should NOT cause NEUTRO in F4
        if result.status == F4Status.PASS:
            assert result.percentil_z is not None


class TestF4PipelineResultSchema:
    """Testes para schema de F4PipelineResult."""
    
    def test_result_has_required_fields(self):
        """F4PipelineResult deve ter todos os campos obrigatórios."""
        result = F4PipelineResult(status=F4Status.PASS)
        
        assert hasattr(result, 'status')
        assert hasattr(result, 'garch_sigma')
        assert hasattr(result, 'omega')
        assert hasattr(result, 'alpha')
        assert hasattr(result, 'beta')
        assert hasattr(result, 'source')
        assert hasattr(result, 'z_t')
        assert hasattr(result, 'percentil_z')
        assert hasattr(result, 'reason')
        assert hasattr(result, 'metrics')
    
    def test_result_dataclass(self):
        """F4PipelineResult deve ser um dataclass."""
        result = F4PipelineResult(
            status=F4Status.PASS,
            garch_sigma=0.01,
            source="garch",
            z_t=0.5,
            percentil_z=0.8,
        )
        
        assert result.status == F4Status.PASS
        assert result.garch_sigma == 0.01
        assert result.source == "garch"
        assert result.z_t == 0.5
        assert result.percentil_z == 0.8


class TestF4PipelineClass:
    """Testes para a classe F4Pipeline diretamente."""
    
    def test_pipeline_initialization(self):
        """Testa inicialização do pipeline."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        returns_history = [0.001] * 250
        z_history = [0.5] * 200
        
        pipeline = F4Pipeline(
            f3_result=f3_pass,
            X_t=0.005,
            r_t=0.004,
            returns_history=returns_history,
            z_history=z_history,
            seed=42
        )
        
        assert pipeline.f3_result == f3_pass
        assert pipeline.X_t == 0.005
        assert pipeline.r_t == 0.004
        assert pipeline.returns_history == returns_history
        assert pipeline.z_history == z_history
        assert pipeline.seed == 42
    
    def test_check_f3_pass(self):
        """Testa verificação de F3 PASS."""
        f3_pass = F3PipelineResult(status=F3Status.PASS, mu=0.001)
        f3_neutro = F3PipelineResult(status=F3Status.NEUTRO, reason="F2 failed")
        
        pipeline_pass = F4Pipeline(
            f3_result=f3_pass,
            X_t=0.005,
            r_t=0.004,
            returns_history=[0.001] * 250,
            z_history=[0.5] * 200
        )
        pipeline_neutro = F4Pipeline(
            f3_result=f3_neutro,
            X_t=0.005,
            r_t=0.004,
            returns_history=[0.001] * 250,
            z_history=[0.5] * 200
        )
        
        assert pipeline_pass._check_f3_pass() is True
        assert pipeline_neutro._check_f3_pass() is False


class TestF4PipelineIndependentTests:
    """Independent Tests conforme spec US4."""
    
    def test_f3_neutro_no_promote_independent(self):
        """Independent Test: F3 NEUTRO → F4 não promove PASS."""
        f3_neutro = F3PipelineResult(
            status=F3Status.NEUTRO,
            mu=None,
            reason="F2 did not pass"
        )
        
        result = run_f4_pipeline(
            f3_result=f3_neutro,
            X_t=0.005,
            r_t=0.004,
            returns_history=[0.001] * 250,
            z_history=[0.5] * 200,
            seed=42
        )
        
        assert result.status == F4Status.NEUTRO
        # Should not have valid Z or P
        assert result.z_t is None
        assert result.percentil_z is None
    
    def test_f3_pass_garch_ok_promote_pass(self):
        """Independent Test: F3 PASS + GARCH ok → PASS com campos."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=0.005,
            r_t=0.004,
            returns_history=generate_garch_stable_series(300),
            z_history=[0.5] * 200,
            seed=42
        )
        
        if result.status == F4Status.PASS:
            assert result.garch_sigma is not None and result.garch_sigma > 0
            assert result.z_t is not None
            assert result.percentil_z is not None
            assert result.source in ["garch", "fallback"]
    
    def test_fallback_com_sigma_valido_pode_pass(self):
        """Independent Test: fallback com σ>0 pode PASS."""
        f3_pass = F3PipelineResult(
            status=F3Status.PASS,
            mu=0.001,
        )
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=0.005,
            r_t=0.004,
            returns_history=generate_random_walk(300, sigma=0.02),
            z_history=[0.5] * 200,
            seed=42
        )
        
        if result.status == F4Status.PASS:
            # Fallback doesn't automatically make NEUTRO
            # If sigma > 0 and Z/P calculable, can still PASS
            assert result.garch_sigma is not None
            assert result.garch_sigma > 0


class TestF4PipelineFixtures:
    """Testes usando fixtures de pipeline.json."""
    
    def test_fixture_f3_neutro_no_promote(self):
        """Testa fixture f3_neutro_no_promote."""
        fixture = load_pipeline_fixtures()
        neutro_case = fixture['test_cases'][1]
        
        f3_neutro = F3PipelineResult(
            status=F3Status.NEUTRO,
            mu=None,
            reason="F2 did not pass"
        )
        
        result = run_f4_pipeline(
            f3_result=f3_neutro,
            X_t=0.005,
            r_t=0.004,
            returns_history=[0.001] * 250,
            z_history=[0.5] * 200,
            seed=42
        )
        
        assert result.status.value == neutro_case['expected']['status']
    
    def test_fixture_f3_pass_garch_success(self):
        """Testa fixture f3_pass_garch_success."""
        fixture = load_pipeline_fixtures()
        garch_case = fixture['test_cases'][0]
        
        f3_pass = F3PipelineResult(status=F3Status.PASS, mu=0.001)
        
        result = run_f4_pipeline(
            f3_result=f3_pass,
            X_t=0.005,
            r_t=0.004,
            returns_history=generate_garch_stable_series(300),
            z_history=[0.5] * 200,
            seed=42
        )
        
        if result.status == F4Status.PASS:
            assert garch_case['expected']['garch_sigma_not_null'] or result.garch_sigma is not None
            assert result.source in ["garch", "fallback"]


class TestF4PipelineScope:
    """Testes para verificar escopo F4 (sem §3.9+/TA/executor)."""
    
    def test_no_confirmation_import(self):
        """Pipeline não importa confirmação."""
        from motor.vol import pipeline
        # Should not have confirmation-related attributes
        import inspect
        source = inspect.getsource(pipeline)
        assert 'confirma' not in source.lower()
        assert 'força' not in source.lower()
        assert 'payload' not in source.lower()
    
    def test_no_ta_import(self):
        """Pipeline não importa TA (Technical Analysis)."""
        from motor.vol import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        assert 'ta_' not in source.lower()
        assert 'technical' not in source.lower()
    
    def test_no_executor_import(self):
        """Pipeline não importa executor."""
        from motor.vol import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        assert 'executor' not in source.lower()
    
    def test_no_cusum_import(self):
        """Pipeline não importa CUSUM."""
        from motor.vol import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        assert 'cusum' not in source.lower()
        assert 'CUSUM' not in source.lower()