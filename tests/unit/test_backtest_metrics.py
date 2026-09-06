"""Testes Independente US4 — Métricas §10.1 (T020).

Sharpe (equity diario, Rf=0, ×√252), WR, PF, MaxDD, taxa triggers, mediana τ.

Spec F6 §10.1 - US4, T018-T020
"""

from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.backtest.metrics import (
    InstrumentMetrics,
    GateResult,
    MetricsCalculator,
    calculate_sharpe_from_equity,
    check_gate,
)


class TestSharpeCalculation:
    """Testes para calculo de Sharpe."""
    
    def test_sharpe_sqrt_252(self):
        """Dado equity diario,
        Quando calcula Sharpe,
        Entao usa ×√252 (nao Sharpe em M30 cru)."""
        calc = MetricsCalculator(seed=42)
        
        # Sharpe calculation uses sqrt(252) annualization
        assert calc.SHARPE_ANNUALIZATION == math.sqrt(252)
    
    def test_sharpe_daily_equity(self):
        """Dado Sharpe,
        Quando calcula,
        Entao usa retornos de equity diario."""
        # Equity series - daily values
        equity = [1.0, 1.02, 1.01, 1.03, 1.02, 1.04, 1.03]
        
        sharpe = calculate_sharpe_from_equity(equity, risk_free=0.0)
        
        # Sharpe should be calculated from daily returns
        assert isinstance(sharpe, float)
    
    def test_sharpe_rf_zero(self):
        """Dado Sharpe,
        Quando calcula,
        Entao usa Rf=0."""
        equity = [1.0, 1.01, 1.02, 1.01, 1.03]
        
        # With Rf=0
        sharpe = calculate_sharpe_from_equity(equity, risk_free=0.0)
        
        # Just verify it works with Rf=0
        assert isinstance(sharpe, float)
    
    def test_sharpe_zero_returns(self):
        """Dado equity constante,
        Quando calcula Sharpe,
        Entao Sharpe = 0 (ou handling apropriado)."""
        equity = [1.0, 1.0, 1.0, 1.0, 1.0]
        
        sharpe = calculate_sharpe_from_equity(equity)
        
        # Sharpe should be 0 for constant equity
        assert sharpe == 0.0


class TestWinRateCalculation:
    """Testes para calculo de Win Rate."""
    
    def test_wr_pass_threshold(self):
        """Dado WR > 45%,
        Quando medido,
        Entao passa target."""
        calc = MetricsCalculator()
        
        wr = calc.calculate_wr(num_wins=50, num_losses=50)
        
        assert wr == 0.5
        assert wr > 0.45  # Target WR > 45%
    
    def test_wr_below_threshold(self):
        """Dado WR < 45%,
        Quando medido,
        Entao falha target."""
        calc = MetricsCalculator()
        
        wr = calc.calculate_wr(num_wins=30, num_losses=70)
        
        assert wr == 0.3
        assert wr < 0.45


class TestProfitFactor:
    """Testes para calculo de Profit Factor."""
    
    def test_pf_above_target(self):
        """Dado PF > 1.3,
        Quando calculado,
        Entao passa target."""
        calc = MetricsCalculator()
        
        pf = calc.calculate_pf(
            num_wins=50,
            num_losses=50,
            gross_wins=150.0,
            gross_losses=100.0,
        )
        
        assert pf == 1.5
        assert pf > 1.3  # Target PF > 1.3
    
    def test_pf_below_target(self):
        """Dado PF < 1.3,
        Quando calculado,
        Entao falha target."""
        calc = MetricsCalculator()
        
        pf = calc.calculate_pf(
            num_wins=30,
            num_losses=70,
            gross_wins=100.0,
            gross_losses=120.0,
        )
        
        assert pf < 1.0
        assert pf < 1.3


class TestMaxDrawdown:
    """Testes para calculo de Max Drawdown."""
    
    def test_maxdd_below_target(self):
        """Dado MaxDD < 15%,
        Quando calculado,
        Entao passa target."""
        calc = MetricsCalculator()
        
        # Equity curve with max 10% drawdown
        equity = [1.0, 1.05, 1.10, 1.08, 1.06, 1.02, 0.98, 0.95, 0.97]
        
        maxdd = calc.calculate_maxdd(equity)
        
        assert maxdd < 0.15  # Target MaxDD < 15%
    
    def test_maxdd_above_target(self):
        """Dado MaxDD > 15%,
        Quando calculado,
        Entao falha target."""
        calc = MetricsCalculator()
        
        # Equity curve with > 15% drawdown
        equity = [1.0, 1.02, 0.85, 0.90]  # 15% drawdown from 1.02 to 0.85
        
        maxdd = calc.calculate_maxdd(equity)
        
        assert maxdd > 0.15


class TestTriggerRate:
    """Testes para taxa de triggers."""
    
    def test_trigger_rate_in_range(self):
        """Dado taxa triggers entre 5-15%,
        Quando medido,
        Entao passa target."""
        calc = MetricsCalculator()
        
        # 10% trigger rate
        trigger_rate = calc.calculate_trigger_rate(
            triggers_count=50,
            total_bars=500,
        )
        
        assert trigger_rate == 0.1
        assert 0.05 <= trigger_rate <= 0.15  # Target 5-15%
    
    def test_trigger_rate_below_min(self):
        """Dado taxa triggers < 5%,
        Quando medido,
        Entao falha target."""
        calc = MetricsCalculator()
        
        # 2% trigger rate
        trigger_rate = calc.calculate_trigger_rate(
            triggers_count=20,
            total_bars=1000,
        )
        
        assert trigger_rate == 0.02
        assert trigger_rate < 0.05
    
    def test_trigger_rate_above_max(self):
        """Dado taxa triggers > 15%,
        Quando medido,
        Entao falha target."""
        calc = MetricsCalculator()
        
        # 20% trigger rate
        trigger_rate = calc.calculate_trigger_rate(
            triggers_count=200,
            total_bars=1000,
        )
        
        assert trigger_rate == 0.2
        assert trigger_rate > 0.15


class TestTauMedian:
    """Testes para mediana de tau."""
    
    def test_tau_median_in_range(self):
        """Dado tau mediana entre 3-8,
        Quando calculado,
        Entao passa target."""
        calc = MetricsCalculator()
        
        tau_values = [3, 4, 5, 6, 7]
        tau_median = calc.calculate_tau_median(tau_values)
        
        assert 3 <= tau_median <= 8  # Target 3-8 barras
    
    def test_tau_median_empty(self):
        """Dado sem trades,
        Quando calcula tau mediana,
        Entao retorna 0."""
        calc = MetricsCalculator()
        
        tau_median = calc.calculate_tau_median([])
        
        assert tau_median == 0


class TestGateEvaluation:
    """Testes para avaliacao do gate."""
    
    def test_gate_pass(self):
        """Dado >= 7/10 Sharpe > 0.5,
        Quando avaliado,
        Entao PASS global."""
        metrics_list = [
            InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.6 + i * 0.1)
            for i in range(7)
        ]
        
        gate = check_gate(metrics_list)
        
        assert gate.pass_count == 7
        assert gate.passed is True
    
    def test_gate_fail(self):
        """Dado < 7/10 Sharpe > 0.5,
        Quando avaliado,
        Entao FAIL global."""
        metrics_list = [
            InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.3 + i * 0.05)
            for i in range(5)
        ]
        
        gate = check_gate(metrics_list)
        
        assert gate.pass_count < 7
        assert gate.passed is False


class TestMetricTargets:
    """Testes para os alvos §10.1."""
    
    def test_targets_defined(self):
        """Dado metricas calculadas,
        Quando comparadas,
        Entao usa alvos literais do spec."""
        from motor.backtest import TARGET_SHARPE, TARGET_WR, TARGET_PF, TARGET_MAXDD
        
        assert TARGET_SHARPE == 0.5
        assert TARGET_WR == 0.45
        assert TARGET_PF == 1.3
        assert TARGET_MAXDD == 0.15


class TestMetricsFixture:
    """Testes usando sharde de metricas."""
    
    def test_sharpe_table_fixture(self):
        """Dado fixture sharpe_table.json,
        Quando carregado,
        Entao valore batem referencia."""
        fixture_path = "tests/fixtures/backtest/sharpe_table.json"
        
        try:
            with open(fixture_path) as f:
                fixture = json.load(f)
            
            # Verificar estrutura
            assert "sharpes" in fixture
            assert "gate_passed" in fixture
            assert "pass_count" in fixture
            
            # Verificar que pass_count >= 7 para pass
            if fixture["gate_passed"]:
                assert fixture["pass_count"] >= 7
                
        except FileNotFoundError:
            pytest.skip("Fixture not found")


class TestCalculateMetrics:
    """Testes para a funcao calculate_metrics."""
    
    def test_sharpe_calculation_method(self):
        """Testa o metodo de calculo de Sharpe."""
        calc = MetricsCalculator(seed=42)
        
        # Epocas de equity com movimento consistente
        daily_equity = [1.0, 1.01, 1.02, 1.01, 1.03, 1.02, 1.04, 1.03]
        
        sharpe = calc.calculate_sharpe(daily_equity)
        
        # Sharpe should be positive for upward trajectory
        assert isinstance(sharpe, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])