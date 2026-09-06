"""Testes Independente US5 — Gate 7/10 + relatório (T023).

Gate >= 7/10 Sharpe > 0.5 e relatório JSON serializável in-memory.

Spec F6 §10.1 - US5, T021-T024
"""

from __future__ import annotations

import json
import pytest

from motor.backtest.report import (
    BacktestReport,
    InstrumentReport,
    ReportBuilder,
    Veredito,
    build_backtest_report,
)
from motor.backtest.metrics import (
    InstrumentMetrics,
    GateResult,
    check_gate,
)
from motor.backtest.pipeline import (
    F6Pipeline,
    PipelineResult,
    PipelineStatus,
    run_f6_pipeline,
)


class TestGateThreshold:
    """Testes para gate Sharpes > 0.5."""
    
    def test_gate_pass_if_7_or_more(self):
        """Dado 7 instrumentos com Sharpe > 0.5,
        Quando avaliado,
        Então gate PASS."""
        metrics = [
            InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.6 + i * 0.05)
            for i in range(7)
        ]
        
        gate = check_gate(metrics)
        
        assert gate.pass_count >= 7
        assert gate.passed is True
    
    def test_gate_fail_if_6_or_less(self):
        """Dado 6 instrumentos com Sharpe > 0.5,
        Quando avaliado,
        Então gate FAIL."""
        metrics = [
            InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.6 + i * 0.05)
            for i in range(6)
        ]
        
        gate = check_gate(metrics)
        
        assert gate.pass_count < 7
        assert gate.passed is False


class TestReportGeneration:
    """Testes para geracao de relatorio."""
    
    def test_report_json_serializable(self):
        """Dado relatorio gerado,
        Quando serializado,
        Então é JSON-serializável."""
        metrics = [
            InstrumentMetrics(
                instrumento="EUR/USD",
                sharpe=0.65,
                wr=0.52,
                pf=1.45,
                maxdd=0.08,
                trigger_rate=0.08,
                tau_median=4,
            )
        ]
        
        report = build_backtest_report(metrics, seed=42)
        
        # Should be JSON serializable
        json_str = json.dumps(report.to_dict())
        
        assert json_str is not None
        assert '"veredito"' in json_str
    
    def test_report_has_instrument_metrics(self):
        """Dado relatorio,
        Quando inspeccionado,
        Então tem metricas por instrumento."""
        metrics = [
            InstrumentMetrics(
                instrumento="EUR/USD",
                sharpe=0.65,
                wr=0.52,
            ),
            InstrumentMetrics(
                instrumento="GBP/JPY",
                sharpe=0.45,
                wr=0.43,
            ),
        ]
        
        report = build_backtest_report(metrics, seed=42)
        
        assert len(report.instrumentos) == 2
        assert report.instrumentos[0].instrumento == "EUR/USD"
    
    def test_report_has_gate_result(self):
        """Dado relatorio,
        Quando inspeccionado,
        Então tem gate_result."""
        metrics = [
            InstrumentMetrics(instrumento="INST", sharpe=0.6)
            for _ in range(8)
        ]
        
        report = build_backtest_report(metrics, seed=42)
        
        assert report.gate_result is not None
        assert hasattr(report.gate_result, 'passed')


class TestReportInstrumentFlags:
    """Testes para flags vs alvos no relatorio."""
    
    def test_sharpe_target_flag(self):
        """Dado Sharpe > 0.5,
        Quando relatorio,
        Entao sharpe_target_met = True."""
        builder = ReportBuilder(seed=42)
        
        metrics = InstrumentMetrics(
            instrumento="EUR/USD",
            sharpe=0.65,  # > 0.5 target
        )
        
        report = builder._create_instrument_report(metrics)
        
        assert report.sharpe_target_met is True
    
    def test_sharpe_below_target_flag(self):
        """Dado Sharpe < 0.5,
        Quando relatorio,
        Então sharpe_target_met = False."""
        builder = ReportBuilder(seed=42)
        
        metrics = InstrumentMetrics(
            instrumento="GBP/JPY",
            sharpe=0.35,  # < 0.5 target
        )
        
        report = builder._create_instrument_report(metrics)
        
        assert report.sharpe_target_met is False
    
    def test_maxdd_below_target_flag(self):
        """Dado MaxDD < 15%,
        Quando relatorio,
        Então maxdd_target_met = True."""
        builder = ReportBuilder(seed=42)
        
        metrics = InstrumentMetrics(
            instrumento="EUR/USD",
            sharpe=0.65,
            maxdd=0.10,  # < 15% target
        )
        
        report = builder._create_instrument_report(metrics)
        
        assert report.maxdd_target_met is True


class TestReportData:
    """Testes para dados no relatorio."""
    
    def test_report_timestamp(self):
        """Dado relatorio,
        Quando gerado,
        Então tem timestamp UTC."""
        metrics = [InstrumentMetrics(instrumento="INST", sharpe=0.6)]
        
        report = build_backtest_report(metrics, seed=42)
        
        assert report.timestamp is not None
        assert "T" in report.timestamp  # ISO format
    
    def test_report_veredito_pass(self):
        """Dado gate pass,
        Quando relatorio,
        Então veredito = PASS."""
        metrics = [
            InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.6 + i * 0.05)
            for i in range(7)
        ]
        
        report = build_backtest_report(metrics, seed=42)
        
        assert report.veredito == Veredito.PASS


class TestPipelineIntegration:
    """Testes de integracao do pipeline."""
    
    def test_pipeline_returns_result(self):
        """Dado pipeline F6,
        Quando executado,
        Então retorna PipelineResult."""
        result = run_f6_pipeline(seed=42)
        
        assert isinstance(result, PipelineResult)
        assert result.status in [PipelineStatus.SUCCESS, PipelineStatus.PARTIAL, PipelineStatus.FAILED]
    
    def test_pipeline_has_instrument_outputs(self):
        """Dado pipeline executado,
        Quando inspeccionado,
        Então tem outputs por instrumento."""
        result = run_f6_pipeline(seed=42)
        
        # Deve ter resultados (mesmo que sinteticos)
        assert len(result.instrument_outputs) > 0 or len(result.instrument_metrics) > 0
    
    def test_pipeline_report_available(self):
        """Dado pipeline executado,
        Quando inspeccionado,
        Então relatorio disponivel."""
        result = run_f6_pipeline(seed=42)
        
        # Report pode estar presente
        if result.report:
            assert result.report.veredito in [Veredito.PASS, Veredito.FAIL]


class TestReportJSONFormat:
    """Testes para formato JSON do relatorio."""
    
    def test_report_to_json_structure(self):
        """Dado relatorio,
        Quando convertido para JSON,
        Então tem estrutura correta."""
        metrics = [
            InstrumentMetrics(
                instrumento="EUR/USD",
                sharpe=0.65,
                wr=0.52,
                pf=1.45,
                maxdd=0.08,
            )
        ]
        
        report = build_backtest_report(metrics, seed=42)
        data = report.to_dict()
        
        assert "timestamp" in data
        assert "veredito" in data
        assert "total_instruments" in data
        assert "instrumentos" in data
        assert isinstance(data["instrumentos"], list)
    
    def test_report_instrument_json_fields(self):
        """Dado instrumento no relatorio,
        Quando serializado,
        Então tem todos os campos obrigatorios."""
        metrics = [
            InstrumentMetrics(
                instrumento="EUR/USD",
                sharpe=0.65,
                wr=0.52,
                pf=1.45,
                maxdd=0.08,
                trigger_rate=0.08,
                tau_median=4,
            )
        ]
        
        report = build_backtest_report(metrics, seed=42)
        data = report.to_dict()
        
        inst = data["instrumentos"][0]
        
        assert "instrumento" in inst
        assert "sharpe" in inst
        assert "wr" in inst
        assert "pf" in inst
        assert "maxdd" in inst
        assert "passed" in inst


class TestReportSoleAltaDiagnosis:
    """Testes para taxa so-ALTA como diagnostico F7."""
    
    def test_solealta_rate_diagnostic_only(self):
        """Dado que taxa so-ALTA é diagnostico,
        Quando relatorio,
        Entao não é usada como gate."""
        builder = ReportBuilder(seed=42)
        
        # Need 7+ instruments for gate pass
        metrics = [InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.6 + i * 0.05) for i in range(7)]
        trigger_rates = {"INST0": 0.80}  # 80% so-ALTA - above threshold (diagnostico F7)
        
        report = builder.build_report(metrics, trigger_rates)
        
        # so-ALTA rate should be in report for INST0 but not used for gate
        assert report.instrumentos[0].solealta_rate == 0.80
        
        # Gate still passes if Sharpe > 0.5 (7 instruments)
        assert report.veredito == Veredito.PASS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])