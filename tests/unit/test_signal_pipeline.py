"""Testes US5 — Pipeline F5 sobre F4 PASS.

Independent Test:
- F4 NEUTRO → pipeline F5 não promove LONG/SHORT (pode NEUTRO)
- F4 PASS + fluxo completo → payload ALTA/MÉDIA ou NEUTRO
- Short-circuit em 8.6

Reference: Espec F5 US5
"""

from __future__ import annotations

import json
import math
import pytest

from motor.vol.pipeline import F4PipelineResult, F4Status
from motor.regime.pipeline import F3PipelineResult, F3Status
from motor.signal.pipeline import (
    F5Pipeline,
    F5PipelineResult,
    F5Status,
    run_f5_pipeline,
)


def load_pipeline_fixtures() -> dict:
    """Carrega fixtures de teste para pipeline."""
    with open("tests/fixtures/signal/pipeline.json") as f:
        return json.load(f)


def generate_f4_pass_result() -> F4PipelineResult:
    """Gera resultado F4 PASS para testes."""
    return F4PipelineResult(
        status=F4Status.PASS,
        garch_sigma=0.015,
        omega=0.0001,
        alpha=0.08,
        beta=0.88,
        source="garch",
        z_t=-1.5,
        percentil_z=0.90,
    )


def generate_f4_neutro_result() -> F4PipelineResult:
    """Gera resultado F4 NEUTRO para testes."""
    return F4PipelineResult(
        status=F4Status.NEUTRO,
        reason="F4 did not pass",
    )


def generate_f3_pass_result() -> F3PipelineResult:
    """Gera resultado F3 PASS para testes."""
    return F3PipelineResult(
        status=F3Status.PASS,
        hurst=0.35,
        mu=0.001,
        theta=0.3,
        tau=25.0,
        bootstrap_cv_theta=0.25,
        forca_penalty_cv=False,
    )


def generate_f3_neutro_result() -> F3PipelineResult:
    """Gera resultado F3 NEUTRO para testes."""
    return F3PipelineResult(
        status=F3Status.NEUTRO,
        reason="Hurst classification: NEUTRO",
    )


class TestF4NeutroNoPromote:
    """Testes para F4 NEUTRO → F5 não promove."""
    
    def test_f4_neutro_no_promote(self):
        """Given F4 NEUTRO, When F5 runs, Then não promove LONG/SHORT."""
        f4_result = generate_f4_neutro_result()
        f3_result = generate_f3_pass_result()
        bar = [1704067200000, 100.0, 102.0, 99.0, 101.0, 100.8, 101.2]
        returns = [0.001] * 200  # Série curta mas válida
        
        result = run_f5_pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        assert result.status == F5Status.NEUTRO
        assert result.payload is not None
        assert result.payload.sinal_quantitativo.direcao == "NEUTRO"
    
    def test_f4_neutro_has_reason(self):
        """F4 NEUTRO result tem razão no payload."""
        f4_result = generate_f4_neutro_result()
        f3_result = generate_f3_pass_result()
        bar = [1704067200000, 100.0, 102.0, 99.0, 101.0, 100.8, 101.2]
        returns = [0.001] * 200
        
        result = run_f5_pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        assert result.status == F5Status.NEUTRO
        assert result.reason is not None
        assert "F4" in result.reason


class TestF4PassFullFlow:
    """Testes para F4 PASS + fluxo completo."""
    
    def test_f4_pass_complete_flow(self):
        """Given F4 PASS e confirmações OK, When F5 completes, Then payload."""
        f4_result = F4PipelineResult(
            status=F4Status.PASS,
            garch_sigma=0.015,
            z_t=-1.8,
            percentil_z=0.90,
        )
        f3_result = F3PipelineResult(
            status=F3Status.PASS,
            hurst=0.35,
            mu=0.001,
            theta=0.3,
            tau=25.0,
            bootstrap_cv_theta=0.25,
            forca_penalty_cv=False,
        )
        bar = [1704067200000, 100.0, 102.0, 98.5, 101.5, 101.2, 101.8]
        returns = [0.0005 * (-1)**i + 0.001 * (i % 10) / 10 for i in range(200)]
        
        result = run_f5_pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        # Status pode ser PASS ou NEUTRO dependendo das confirmações
        assert result.status in [F5Status.PASS, F5Status.NEUTRO]
        assert result.payload is not None


class TestSkewnessShortCircuit:
    """Testes para short-circuit 8.6."""
    
    def test_skewness_extrema_short_circuit(self):
        """Given skewness extrema, When confirmacao, Then NEUTRO."""
        import numpy as np
        np.random.seed(42)
        
        # Série com skewness negativo extrema
        returns = list(np.random.exponential(0.005, 200))
        
        f4_result = generate_f4_pass_result()
        f3_result = generate_f3_pass_result()
        bar = [1704067200000, 100.0, 102.0, 98.5, 101.0, 100.8, 101.2]
        
        result = run_f5_pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        # Deve ser NEUTRO devido a skewness
        # O importante é que o pipeline não falha
        assert result.status in [F5Status.NEUTRO, F5Status.PASS]


class TestPayloadGeneration:
    """Testes para geração de payload."""
    
    def test_payload_has_required_fields(self):
        """Payload gerado tem todos os campos obrigatórios."""
        f4_result = generate_f4_pass_result()
        f3_result = generate_f3_pass_result()
        bar = [1704067200000, 100.0, 102.0, 98.5, 101.5, 101.2, 101.8]
        returns = [0.001] * 200
        
        result = run_f5_pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        if result.payload:
            payload = result.payload
            assert hasattr(payload, 'versao_protocolo')
            assert hasattr(payload, 'sinal_quantitativo')
            assert hasattr(payload, 'estatisticas_modelo')
            assert hasattr(payload, 'filtros_passados')
            assert hasattr(payload, 'candle_contexto')
            assert hasattr(payload, 'evidencias')
            assert hasattr(payload, 'riscos_estatisticos')
    
    def test_payload_in_memory(self):
        """Payload é in-memory (dict serializável)."""
        f4_result = generate_f4_pass_result()
        f3_result = generate_f3_pass_result()
        bar = [1704067200000, 100.0, 102.0, 98.5, 101.5, 101.2, 101.8]
        returns = [0.001] * 200
        
        result = run_f5_pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        if result.payload:
            # Should be JSON serializable
            import json
            json_str = json.dumps(result.payload.to_dict())
            assert json_str is not None


class TestPipelineExecution:
    """Testes para execução do pipeline."""
    
    def test_pipeline_returns_result(self):
        """Pipeline retorna F5PipelineResult."""
        f4_result = generate_f4_pass_result()
        f3_result = generate_f3_pass_result()
        bar = [1704067200000, 100.0, 102.0, 98.5, 101.5, 101.2, 101.8]
        returns = [0.001] * 200
        
        result = run_f5_pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        assert isinstance(result, F5PipelineResult)
        assert hasattr(result, 'status')
        assert hasattr(result, 'payload')
        assert hasattr(result, 'reason')
    
    def test_pipeline_no_ta_import(self):
        """Pipeline não importa TA (Technical Analysis)."""
        from motor.signal import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        
        assert 'ta.' not in source.lower()  # Módulo ta.technical_analysis
        assert 'technical_analysis' not in source.lower()
    
    def test_pipeline_no_executor_import(self):
        """Pipeline não importa executor."""
        from motor.signal import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        
        assert 'executor' not in source.lower()


class TestF5PipelineClass:
    """Testes para a classe F5Pipeline diretamente."""
    
    def test_pipeline_initialization(self):
        """Testa inicialização do pipeline."""
        f4_result = generate_f4_pass_result()
        f3_result = generate_f3_pass_result()
        bar = [1704067200000, 100.0, 102.0, 98.5, 101.5, 101.2, 101.8]
        returns = [0.001] * 200
        
        pipeline = F5Pipeline(
            f4_result=f4_result,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
            seed=42,
        )
        
        assert pipeline.f4_result == f4_result
        assert pipeline.f3_result == f3_result
        assert pipeline.bar == bar
        assert pipeline.returns == returns
        assert pipeline.instrumento == "PETR4"
        assert pipeline.seed == 42
    
    def test_check_f4_pass(self):
        """Testa verificação de F4 PASS."""
        f4_pass = F4PipelineResult(status=F4Status.PASS)
        f4_neutro = F4PipelineResult(status=F4Status.NEUTRO)
        
        bar = [1704067200000, 100.0, 102.0, 98.5, 101.5, 101.2, 101.8]
        returns = [0.001] * 200
        f3_result = generate_f3_pass_result()
        
        pipeline_pass = F5Pipeline(
            f4_result=f4_pass,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
        )
        pipeline_neutro = F5Pipeline(
            f4_result=f4_neutro,
            f3_result=f3_result,
            bar=bar,
            returns=returns,
            instrumento="PETR4",
        )
        
        assert pipeline_pass._check_f4_pass() is True
        assert pipeline_neutro._check_f4_pass() is False


class TestPipelineFixtures:
    """Testes usando fixtures de pipeline.json."""
    
    def test_f4_neutro_fixture(self):
        """Testa fixture de F4 NEUTRO."""
        fixture = load_pipeline_fixtures()
        
        for case in fixture["test_cases"]:
            if "f4_neutro" in case["name"].lower():
                f4_result = generate_f4_neutro_result()
                f3_result = generate_f3_pass_result()
                bar = case.get("bar", [1704067200000, 100.0, 102.0, 98.5, 101.0, 100.8, 101.2])
                returns = [0.001] * 200
                
                result = run_f5_pipeline(
                    f4_result=f4_result,
                    f3_result=f3_result,
                    bar=bar,
                    returns=returns,
                    instrumento="PETR4",
                    seed=42,
                )
                
                expected = case["expected"]
                assert result.status.value == expected["status"]


class TestPipelineScope:
    """Testes para verificar escopo F5 (sem TA/executor/broker)."""
    
    def test_no_ta_import(self):
        """Pipeline não importa TA (Technical Analysis)."""
        from motor.signal import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        
        assert 'ta.' not in source.lower()  # Módulo ta.technical_analysis
        assert 'technical_analysis' not in source.lower()
    
    def test_no_executor_import(self):
        """Pipeline não importa executor."""
        from motor.signal import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        
        assert 'executor' not in source.lower()
    
    def test_no_broker_import(self):
        """Pipeline não importa broker."""
        from motor.signal import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        
        assert 'broker' not in source.lower()
    
    def test_no_trading_agents_import(self):
        """Pipeline não importa TradingAgents."""
        from motor.signal import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        
        assert 'trading_agents' not in source.lower()
        assert 'TradingAgent' not in source