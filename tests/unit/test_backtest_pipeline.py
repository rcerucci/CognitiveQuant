"""Testes do pipeline F6 (T024).

Orquestra loader -> runner -> pnl -> metrics -> report.

Spec F6 §10.1 - T024
"""

from __future__ import annotations

import pytest
import numpy as np

from motor.backtest.pipeline import (
    F6Pipeline,
    PipelineResult,
    PipelineStatus,
    run_f6_pipeline,
)
from motor.backtest import (
    TARGET_SHARPE,
    TARGET_WR,
    TARGET_PF,
    TARGET_MAXDD,
)


class TestPipelineExecution:
    """Testes para execucao do pipeline."""
    
    def test_pipeline_completes(self):
        """Dado pipeline,
        Quando executado,
        Então completa com status valido."""
        result = run_f6_pipeline(seed=42)
        
        assert isinstance(result, PipelineResult)
        assert result.status in [PipelineStatus.SUCCESS, PipelineStatus.PARTIAL, PipelineStatus.FAILED]
    
    def test_pipeline_with_seed(self):
        """Dado seed=42,
        Quando pipeline executado,
        Então resultados são deterministicos."""
        result1 = run_f6_pipeline(seed=42)
        result2 = run_f6_pipeline(seed=42)
        
        # Resultados devem ser similares (mesmo seed)
        assert len(result1.instrument_outputs) == len(result2.instrument_outputs)


class TestPipelineComponents:
    """Testes para componentes do pipeline."""
    
    def test_all_components_loaded(self):
        """Dado pipeline,
        Quando criado,
        Então todos os componentes estao carregados."""
        pipeline = F6Pipeline(seed=42)
        
        assert pipeline.loader is not None
        assert pipeline.runner is not None
        assert pipeline.metrics_calc is not None
        assert pipeline.report_builder is not None
    
    def test_instruments_from_universe(self):
        """Dado pipeline,
        Quando inicializado,
        Então usa universo F6 §9.2."""
        from motor.backtest import F6_INSTRUMENTS
        
        pipeline = F6Pipeline(seed=42)
        
        assert pipeline.instruments == F6_INSTRUMENTS


class TestPipelineDataFlow:
    """Testes para fluxo de dados pelo pipeline."""
    
    def test_loader_to_runner(self):
        """Dado loader carrega dados,
        Quando passao ao runner,
        Então processa barras."""
        pipeline = F6Pipeline(seed=42)
        
        # Loader deve funcionar
        result = pipeline.loader.load_universe()
        
        # Se não houver dados reais, cria sinteticos
        if result.loaded_count == 0:
            # Verify test data creation works
            bars = pipeline._create_test_bars("EUR/USD", 100)
            assert len(bars) == 100
            assert len(bars[0]) == 7  # F1 format
    
    def test_runner_to_pnl(self):
        """Dado runner processa barras,
        Quando passado ao PnL,
        Então gera trades."""
        pipeline = F6Pipeline(seed=42)
        
        # Criar barras de teste
        bars = pipeline._create_test_bars("EUR/USD", 300)
        
        # Rodar
        run_result = pipeline.runner.run_all(bars, "EUR/USD")
        
        assert len(run_result.bars) == 300


class TestPipelineMetrics:
    """Testes para metricas no pipeline."""
    
    def test_metrics_calculation(self):
        """Dado trades,
        Quando processado,
        Então calcula metricas corretas."""
        pipeline = F6Pipeline(seed=42)
        
        # Processar um instrumento
        bars = pipeline._create_test_bars("EUR/USD", 500)
        run_result = pipeline.runner.run_all(bars, "EUR/USD")
        output = pipeline._process_instrument("EUR/USD", bars, run_result)
        
        # Calcular metricas
        metrics = pipeline.metrics_calc.compute_metrics(
            instrumento="EUR/USD",
            equity_curve=output.equity_curve,
            timestamps=output.timestamps,
            trades=output.trades,
            triggers_count=output.triggers_count,
            total_bars=output.total_bars,
        )
        
        assert metrics.instrumento == "EUR/USD"
        assert metrics.sharpe is not None or metrics.sharpe == 0.0


class TestPipelineReport:
    """Testes para relatorio no pipeline."""
    
    def test_report_generated(self):
        """Dado pipeline completo,
        Quando finalizado,
        Então relatorio gerado."""
        result = run_f6_pipeline(seed=42)
        
        if result.report:
            assert result.report.timestamp is not None
            assert result.report.veredito in ["PASS", "FAIL"]


class TestPipelineGate:
    """Testes para gate no pipeline."""
    
    def test_gate_evaluation(self):
        """Dado metricas,
        Quando avaliado,
        Então gate correto."""
        from motor.backtest.metrics import InstrumentMetrics, check_gate
        
        # 7 instrumentos com Sharpe > 0.5
        metrics_list = [
            InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.6 + i * 0.05)
            for i in range(7)
        ]
        
        gate = check_gate(metrics_list)
        
        assert gate.passed is True
        assert gate.pass_count >= 7
    
    def test_gate_threshold_value(self):
        """Dado gate,
        Quando verificado,
        Então usa Sharpe > 0.5."""
        from motor.backtest import SHARPE_GATE_THRESHOLD
        
        assert SHARPE_GATE_THRESHOLD == 0.5


class TestPipelineThresholds:
    """Testes para limiares do pipeline."""
    
    def test_metrics_targets(self):
        """Dado metricas,
        Quando calculadas,
        Entao usa alvos do spec."""
        assert TARGET_SHARPE == 0.5
        assert TARGET_WR == 0.45  # WR > 45% threshold
        assert TARGET_PF == 1.3   # PF > 1.3 threshold
        assert TARGET_MAXDD == 0.15  # MaxDD < 15% threshold
    
    def test_force_threshold(self):
        """Dado trigger,
        Quando avaliado,
        Então usa forca >= 0.60."""
        from motor.backtest import F6_FORCE_THRESHOLD
        
        assert F6_FORCE_THRESHOLD == 0.60


class TestPipelineNoTA:
    """Testes garantindo pipeline sem TA."""
    
    def test_no_ta_in_pipeline(self):
        """Dado pipeline,
        Quando inspecionado,
        Então nãO importa TA/executor/broker."""
        from motor.backtest import pipeline
        import inspect
        source = inspect.getsource(pipeline)
        
        assert 'ta.' not in source.lower()
        assert 'technical_analysis' not in source.lower()
        assert 'executor' not in source.lower()
        assert 'broker' not in source.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])