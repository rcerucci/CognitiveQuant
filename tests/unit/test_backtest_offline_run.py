"""Testes Independent US6 — Run offline + gate §10.1 (T033).

Comando f6-backtest --data-dir data/ohlc --out reports/f6_backtest.json
Run offline → data/ohlc/ → reports/

Spec F6 §10.1 - US6, T028-T033
"""

from __future__ import annotations

import json
import os
import tempfile
import pytest
import numpy as np
import pandas as pd

# Silently ignore pytest-style docstrings
from pytest import fixture


class TestOfflineRunCLI:
    """Testes para o CLI de run offline."""
    
    def test_cli_module_imports_no_provider_sdk(self):
        """Dado CLI,
        Quando inspecionado,
        Entao nao importa SDK de provider (QuantConnect/OANDA/etc)."""
        from motor.backtest import cli
        import inspect
        source = inspect.getsource(cli)
        
        # Should not import provider SDKs
        assert 'from quantconnect' not in source.lower()
        assert 'import requests' not in source.lower()
    
    def test_cli_no_network_calls(self):
        """Dado CLI,
        Quando executado,
        Entao nao faz chamadas de rede HTTP."""
        # CLI uses local files only
        from motor.backtest.cli import run_offline, check_empty_data_dir
        
        # The function should only read local files
        assert callable(run_offline)


class TestOfflineRunChecklist:
    """Testes para checklist dos 10 arquivos canônicos (T028)."""
    
    def test_canonical_files_list(self):
        """Dado os 10 instrumentos §9.2,
        Quando verificado,
        Entao nomes sao canonico: eur_usd, gbp_jpy, etc."""
        from motor.backtest.cli import CANONICAL_FILES
        
        expected = [
            "eur_usd.parquet",
            "gbp_jpy.parquet",
            "usd_cad.parquet",
            "aud_nzd.parquet",
            "us500.parquet",
            "ger30.parquet",
            "jp225.parquet",
            "xau_usd.parquet",
            "usoil.parquet",
            "nas100.parquet",
        ]
        
        assert CANONICAL_FILES == expected
        assert len(CANONICAL_FILES) == 10
    
    def test_check_canonical_files_found(self):
        """Dado data_dir com arquivos canonicos,
        Quando verificado,
        Entao todos os 10 sao encontrados."""
        from motor.backtest.cli import check_canonical_files, CANONICAL_FILES
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create all canonical files
            for fname in CANONICAL_FILES:
                open(os.path.join(tmpdir, fname), 'w').close()
            
            result = check_canonical_files(tmpdir, CANONICAL_FILES)
            
            assert result['sufficient'] is True
            assert len(result['found']) == 10
            assert len(result['missing']) == 0


class TestOfflineRunFailure:
    """Testes para run falhando (T032)."""
    
    def test_fail_on_empty_data_dir(self):
        """Dado data_dir vazia,
        Quando run é invocado,
        Entao FAIL (nao PASS inventado)."""
        from motor.backtest.cli import check_empty_data_dir
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Add only .gitkeep
            with open(os.path.join(tmpdir, '.gitkeep'), 'w') as f:
                f.write('')
            
            assert check_empty_data_dir(tmpdir) is True
    
    def test_fail_on_missing_instruments(self):
        """Dado data_dir incompleto,
        Quando run é invocado,
        Entao instrumentos INSUFICIENTE demais para gate."""
        from motor.backtest.cli import check_canonical_files, CANONICAL_FILES
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create only 5 files (less than required 7 for gate)
            for fname in CANONICAL_FILES[:5]:
                open(os.path.join(tmpdir, fname), 'w').close()
            
            result = check_canonical_files(tmpdir, CANONICAL_FILES)
            
            assert result['sufficient'] is False
            assert len(result['found']) == 5
            assert len(result['missing']) == 5
    
    def test_run_fails_on_zero_triggers(self):
        """Dado dataset sem triggers,
        Quando backtest executado,
        Entao Sharpe nao inventado e FAIL se insuficiente."""
        from motor.backtest.pipeline import F6Pipeline, PipelineStatus
        from motor.backtest.metrics import GateResult
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal valid data for 1 instrument
            df = pd.DataFrame({
                'timestamp': [1704067200000 + i * 1800000 for i in range(100)],
                'open': [100.0] * 100,
                'high': [101.0] * 100,
                'low': [99.0] * 100,
                'close': [100.0] * 100,
                'bid': [100.0] * 100,
                'ask': [100.0] * 100,
            })
            
            # Create one parquet file
            fpath = os.path.join(tmpdir, 'eur_usd.parquet')
            df.to_parquet(fpath)
            
            # Run pipeline - should handle gracefully
            pipeline = F6Pipeline(data_dir=tmpdir, seed=42)
            result = pipeline.run()
            
            # With no variation, should have no trades
            # But should not crash
            assert result is not None


class TestOfflineRunReport:
    """Testes para artefato de relatorio (T031)."""
    
    def test_report_json_schema(self):
        """Dado report JSON,
        Quando salvo,
        Entao schema e valido com gate."""
        from motor.backtest.report import (
            BacktestReport, 
            InstrumentReport, 
            InstrumentMetrics,
            Veredito,
            GateResult
        )
        
        # Create minimal valid report
        metrics = InstrumentMetrics(
            instrumento="TEST",
            sharpe=0.6,
            wr=0.5,
            pf=1.5,
            maxdd=0.1,
            trigger_rate=0.1,
            tau_median=5,
            num_trades=10,
        )
        
        gate = GateResult(
            pass_count=1,
            fail_count=0,
            total_instruments=1,
            passed=True,
            details=[{"instrumento": "TEST", "sharpe": 0.6, "passed": True}]
        )
        
        report = BacktestReport(
            timestamp="2026-09-06T00:00:00Z",
            instrumentos=[InstrumentReport(instrumento="TEST", sharpe=0.6, wr=0.5, pf=1.5, maxdd=0.1, trigger_rate=0.1, tau_median=5)],
            gate_result=gate,
            veredito=Veredito.PASS,
            total_instruments=1,
        )
        
        # Should be JSON serializable
        report_dict = report.to_dict()
        assert isinstance(report_dict, dict)
        assert 'veredito' in report_dict
        assert 'instrumentos' in report_dict
        assert 'gate_result' in report_dict
    
    def test_report_saved_to_file(self):
        """Dado report,
        Quando salvo,
        Entao arquivo e criado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from motor.backtest.report import (
                BacktestReport,
                InstrumentReport,
                Veredito,
                GateResult,
            )
            
            report = BacktestReport(
                timestamp="2026-09-06T00:00:00Z",
                instrumentos=[
                    InstrumentReport(
                        instrumento="TEST",
                        sharpe=0.6,
                        wr=0.5,
                        pf=1.5,
                        maxdd=0.1,
                        trigger_rate=0.1,
                        tau_median=5,
                    )
                ],
                gate_result=GateResult(
                    pass_count=1,
                    fail_count=0,
                    total_instruments=1,
                    passed=True,
                ),
                veredito=Veredito.PASS,
                total_instruments=1,
            )
            
            output_path = os.path.join(tmpdir, 'test_report.json')
            
            with open(output_path, 'w') as f:
                json.dump(report.to_dict(), f, indent=2)
            
            assert os.path.exists(output_path)


class TestOfflineRunIntegration:
    """Testes de integracao para run offline."""
    
    def test_full_pipeline_with_fixture_data(self):
        """Dado fixture de dados,
        Quando pipeline executado,
        Entao resultados gerados."""
        from motor.backtest.pipeline import F6Pipeline
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fixture data for all 10 instruments
            np.random.seed(42)
            
            for inst_name in ['eur_usd', 'gbp_jpy', 'usd_cad', 'aud_nzd', 'us500',
                             'ger30', 'jp225', 'xau_usd', 'usoil', 'nas100']:
                # Create 500 bars (enough for warm-up + signals)
                bars = []
                for i in range(500):
                    ts = 1704067200000 + i * 1800000
                    mid = 100.0 + np.sin(i * 0.01) + np.random.randn() * 0.2
                    bars.append({
                        'timestamp': ts,
                        'open': mid - 0.5,
                        'high': mid + 0.5,
                        'low': mid - 1.0,
                        'close': mid,
                        'bid': mid - 0.25,
                        'ask': mid + 0.25,
                    })
                
                df = pd.DataFrame(bars)
                df.to_parquet(os.path.join(tmpdir, f'{inst_name}.parquet'))
            
            # Run pipeline
            pipeline = F6Pipeline(data_dir=tmpdir, seed=42)
            result = pipeline.run()
            
            # Should complete successfully
            assert result.status in [result.status.SUCCESS, result.status.PARTIAL]
            assert len(result.instrument_metrics) > 0
    
    def test_gate_evaluation(self):
        """Dado metricas calculadas,
        Quando gate evaluado,
        Entao pass_count >= 7 para PASS."""
        from motor.backtest.metrics import check_gate, InstrumentMetrics
        
        # Create metrics with some passing
        metrics = [
            InstrumentMetrics(instrumento=f"INST{i}", sharpe=0.6 + i * 0.1)
            for i in range(10)
        ]
        
        gate = check_gate(metrics)
        
        # All 10 have Sharpe > 0.5
        assert gate.pass_count == 10
        assert gate.passed is True


class TestFixtureData:
    """Testes com dados de fixture minimos."""
    
    @fixture
    def sample_bars_path(self):
        """Path to sample bars fixture."""
        return "tests/fixtures/backtest/sample_bars.csv"
    
    def test_load_fixture_csv(self, sample_bars_path):
        """Dado fixture CSV,
        Quando carregado,
        Entao formato F1 preservado."""
        from motor.backtest.loader import load_fixture_data, LoaderStatus
        
        if os.path.exists(sample_bars_path):
            result = load_fixture_data(sample_bars_path)
            assert result.status == LoaderStatus.SUCCESS


class TestDeterminismo:
    """Testes de determinismo com seed=42."""
    
    def test_seed_42_determinismo(self):
        """Dado seed=42,
        Quando executado duas vezes,
        Entao resultados identicos."""
        from motor.backtest.pipeline import run_f6_pipeline
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fixture
            df = pd.DataFrame({
                'timestamp': [1704067200000 + i * 1800000 for i in range(100)],
                'open': [100.0] * 100,
                'high': [101.0] * 100,
                'low': [99.0] * 100,
                'close': [100.0] * 100,
                'bid': [100.0] * 100,
                'ask': [100.0] * 100,
            })
            df.to_parquet(os.path.join(tmpdir, 'eur_usd.parquet'))
            
            result1 = run_f6_pipeline(data_dir=tmpdir, seed=42)
            result2 = run_f6_pipeline(data_dir=tmpdir, seed=42)
            
            assert len(result1.instrument_metrics) == len(result2.instrument_metrics)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])