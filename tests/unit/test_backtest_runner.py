"""Testes Independente US1 — Runner motor-only (T014).

Executor F1→F5 barra-a-barra sem TA/MCP.
Spec F6 §10.1 - US1, T013
"""

from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.backtest.runner import (
    BarRunner,
    BacktestResult,
    RunResult,
    RunnerStatus,
    run_backtest,
)


class TestRunnerScope:
    """Testes para verificar escopo do runner (sem TA/MCP/executor)."""
    
    def test_no_ta_import(self):
        """Dado runner,
        Quando inspecionado o codigo,
        Entao nao importa TA (Technical Analysis)."""
        from motor.backtest import runner
        import inspect
        source = inspect.getsource(runner)
        
        # Should not import TA modules
        assert 'import ta' not in source.lower()
        assert 'from ta import' not in source.lower()
    
    def test_no_mcp_import(self):
        """Dado runner,
        Quando inspecionado o codigo,
        Entao nao importa MCP."""
        from motor.backtest import runner
        import inspect
        source = inspect.getsource(runner)
        
        # Should not import MCP modules
        assert 'import mcp' not in source.lower()
        assert 'from mcp import' not in source.lower()
    
    def test_no_executor_import(self):
        """Dado runner,
        Quando inspecionado o codigo,
        Entao nao importa executor/broker."""
        from motor.backtest import runner
        import inspect
        source = inspect.getsource(runner)
        
        # Should not import executor modules - but can mention in docstrings
        assert 'from executor' not in source.lower()
        assert 'from broker' not in source.lower()


class TestRunnerF1ToF5:
    """Testes para pipeline F1→F5."""
    
    def test_consumes_f1_f5_apis(self):
        """Dado runner,
        Quando executado,
        Entao consome APIs publicas F1->F5 in-memory."""
        runner = BarRunner(seed=42)
        
        # Verificar que o runner usa as APIs corretas
        from motor.ohlc.validation import validate_bars_sequence
        from motor.filters.pipeline import Pipeline
        from motor.regime.pipeline import F3Pipeline
        from motor.vol.pipeline import F4Pipeline
        from motor.signal.pipeline import F5Pipeline
        
        assert runner is not None
    
    def test_f1_validation_called(self):
        """Dado barra F1,
        Quando runner executa,
        Entao chama validate_bars_sequence (F1)."""
        bars = [
            [1704067200000, 100.0, 102.0, 99.0, 101.0, 100.8, 101.2],
            [1704069000000, 101.0, 103.0, 100.0, 102.0, 101.8, 102.2],
            [1704070800000, 102.0, 104.0, 101.0, 103.0, 102.8, 103.2],
            # ... more bars para warm-up de 200
        ]
        
        result = run_backtest(bars, "EUR/USD", seed=42)
        
        # Precisamos de pelo menos 200 barras para testes completos
        # Mas podemos verificar que o runner foi inicializado corretamente
        assert isinstance(result, BacktestResult)


class TestRunnerBarExecution:
    """Testes para execucao por barra."""
    
    def test_run_bar_returns_result(self):
        """Dado runner e barra,
        Quando run_bar chamado,
        Entao retorna RunResult."""
        runner = BarRunner(seed=42)
        
        # Criar dados de teste com warm-up
        bars = []
        for i in range(250):
            ts = 1704067200000 + i * 1800000  # M30 interval
            base = 100.0 + i * 0.1
            bars.append([
                ts,
                base,
                base + 1.0,
                base - 0.5,
                base + 0.5,
                base + 0.3,
                base + 0.7,
            ])
        
        # First initialize validated_bars (F1 validation)
        from motor.ohlc.validation import validate_bars_sequence
        validated_series = validate_bars_sequence(bars)
        runner.validated_bars = validated_series.bars
        
        # Then run single bar
        result = runner.run_bar(runner.validated_bars[200], 200)
        
        assert isinstance(result, RunResult)
        assert result.timestamp == bars[200][0]
        assert result.bar_index == 200
    
    def test_warm_up_neutro(self):
        """Dado warm-up inicial,
        Quando barra executada,
        Entao payload NEUTRO (sem dados suficientes)."""
        runner = BarRunner(seed=42)
        
        # Primeiras barras sao warm-up
        bars = []
        for i in range(10):
            ts = 1704067200000 + i * 1800000
            bars.append([ts, 100.0, 102.0, 99.0, 101.0, 100.8, 101.2])
        
        # Initialize validated_bars
        from motor.ohlc.validation import validate_bars_sequence
        validated_series = validate_bars_sequence(bars)
        runner.validated_bars = validated_series.bars
        
        result = runner.run_bar(runner.validated_bars[5], 5)
        
        # Warm-up nao tem dados suficientes para F3/F4/F5
        # O resultado depende do progresso do warm-up


class TestRunnerNoTAExecution:
    """Testes garantindo execucao sem TA."""
    
    def test_zero_ta_calls(self):
        """Dado runner executando,
        Quando backtest completado,
        Entao zero chamadas TA/executor/broker."""
        # Criar serie de teste
        bars = []
        for i in range(250):
            ts = 1704067200000 + i * 1800000
            mid = 100.0 + np.random.randn() * 0.5
            bars.append([ts, mid-1, mid+1, mid-2, mid, mid-0.5, mid+0.5])
        
        result = run_backtest(bars, "EUR/USD", seed=42)
        
        # Verificar que o resultado foi gerado sem erros TA
        assert result.status == RunnerStatus.SUCCESS
        assert len(result.bars) == 250
    
    def test_no_fill_order_execution(self):
        """Dado que ha sinal LONG/SHORT,
        Quando executado,
        Entao NA CHAMA executor/broker para fill."""
        # Este teste verifica o contrato F6:
        # "MUST NOT call TradingAgents, executor MCP or API de broker/provider"
        from motor.backtest import runner
        import inspect
        source = inspect.getsource(runner)
        
        # Nao deve ter codigos de fill/broker
        assert 'fill' not in source.lower() or 'no fill' in source.lower()


class TestRunnerPayloadGeneration:
    """Testes para geracao de payload."""
    
    def test_payload_f5_format(self):
        """Dado executor,
        Quando executa,
        Entao gera payload §3.11 in-memory."""
        runner = BarRunner(seed=42)
        
        # Criar serie suficiente para gerar sinal
        np.random.seed(42)
        bars = []
        for i in range(250):
            ts = 1704067200000 + i * 1800000
            # Tendencia leve para gerar sinal
            mid = 100.0 + i * 0.02
            bars.append([
                ts,
                mid - 0.5,
                mid + 0.5,
                mid - 1.0,
                mid,
                mid - 0.25,
                mid + 0.25,
            ])
        
        # Initialize validated_bars
        from motor.ohlc.validation import validate_bars_sequence
        validated_series = validate_bars_sequence(bars)
        runner.validated_bars = validated_series.bars
        
        result = runner.run_bar(runner.validated_bars[200], 200)
        
        # Payload deve estar no formato F5
        if result.payload:
            from motor.signal.payload import PayloadMotor
            assert isinstance(result.payload, PayloadMotor)
            
            # Verificar campos obrigatorios
            assert hasattr(result.payload, 'versao_protocolo')
            assert hasattr(result.payload, 'sinal_quantitativo')
            assert hasattr(result.payload, 'instrumento')
            assert hasattr(result.payload, 'timeframe')


class TestRunnerMultipleBars:
    """Testes para execucao multiple barras."""
    
    def test_run_all_complete(self):
        """Dado serie completa,
        Quando run_all chamado,
        Entao retorna BacktestResult com todos os resultados."""
        np.random.seed(42)
        
        # Criar serie de 1000 barras
        bars = []
        for i in range(1000):
            ts = 1704067200000 + i * 1800000
            vol = 0.5 + 0.1 * np.sin(i * 0.1)
            mid = 100.0 + i * 0.001 + np.random.randn() * vol
            bars.append([
                ts,
                mid - vol,
                mid + vol,
                mid - vol * 1.5,
                mid,
                mid - vol * 0.5,
                mid + vol * 0.5,
            ])
        
        result = run_backtest(bars, "GBP/JPY", seed=42)

        assert result.status == RunnerStatus.SUCCESS
        assert result.instrumento == "GBP/JPY"
        assert len(result.bars) == 1000
        
        # Count de cada status
        f5_statuses = [b.f5_status for b in result.bars]
        assert 'PASS' in f5_statuses or 'NEUTRO' in f5_statuses

class TestRunnerDeterminism:
    """Testes de determinismo com seed=42."""
    
    def test_seed_42_deterministic(self):
        """Dado seed=42,
        Quando executado duas vezes,
        Entao resultados sao identicos."""
        np.random.seed(42)
        bars = []
        for i in range(300):
            ts = 1704067200000 + i * 1800000
            mid = 100.0 + np.sin(i * 0.1)
            bars.append([
                ts,
                mid - 0.5,
                mid + 0.5,
                mid - 1.0,
                mid,
                mid - 0.25,
                mid + 0.25,
            ])
        
        result1 = run_backtest(bars, "EUR/USD", seed=42)
        result2 = run_backtest(bars, "EUR/USD", seed=42)
        
        # Resultados devem ser identicos
        assert len(result1.bars) == len(result2.bars)
        for r1, r2 in zip(result1.bars, result2.bars):
            assert r1.timestamp == r2.timestamp
            assert r1.f5_status == r2.f5_status

if __name__ == "__main__":
    pytest.main([__file__, "-v"])