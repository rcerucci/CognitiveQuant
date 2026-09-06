"""CLI para backtest motor-only F6 (T030).

Comando: f6-backtest --data-dir data/ohlc --out reports/f6_backtest.json
Run offline → data/ohlc/ → reports/

Spec F6 §10.1 - US6, T028-T032
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Canonical files for the 10 instruments §9.2
CANONICAL_FILES = [
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

from motor.backtest.loader import BacktestLoader, LoaderStatus
from motor.backtest.pipeline import F6Pipeline, PipelineResult, PipelineStatus
from motor.backtest.report import (
    BacktestReport,
    InstrumentReport,
    ReportBuilder,
    Veredito,
    GateResult,
)
from motor.backtest.metrics import InstrumentMetrics
from motor.backtest import (
    F6_INSTRUMENTS,
    F6_FORCE_THRESHOLD,
    TARGET_SHARPE,
)


class OfflineRunError(Exception):
    """Erro para run offline falhando."""
    pass


def check_canonical_files(data_dir: str, required_files: List[str]) -> Dict[str, Any]:
    """Verifica se os arquivos canônicos existem no diretório.
    
    Args:
        data_dir: Diretório de dados
        required_files: Lista de nomes de arquivos obrigatórios
        
    Returns:
        Dict com 'found', 'missing', 'sufficient'
    """
    found = []
    missing = []
    
    for fname in required_files:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            found.append(fname)
        else:
            missing.append(fname)
    
    return {
        "found": found,
        "missing": missing,
        "sufficient": len(missing) == 0,
    }


def check_empty_data_dir(data_dir: str) -> bool:
    """Verifica se o diretório está vazio ou só contém .gitkeep.
    
    Args:
        data_dir: Diretório de dados
        
    Returns:
        True se vazio/só .gitkeep, False caso contrário
    """
    if not os.path.exists(data_dir):
        return True
    
    entries = os.listdir(data_dir)
    # Filter out .gitkeep
    non_gitkeep = [e for e in entries if e != '.gitkeep']
    
    return len(non_gitkeep) == 0


def count_loaded_instruments(loader_result) -> int:
    """Conta quantos instrumentos foram carregados com sucesso."""
    if loader_result is None:
        return 0
    return loader_result.loaded_count


def get_sufficient_instruments_count(metrics_results: Dict[str, InstrumentMetrics]) -> int:
    """Conta instrumentos com dados suficientes para avaliar o gate.
    
    Instrumento é considerado INSUFICIENTE se:
    - Sharpe é None
    - Não houve trades
    - Série muito curta
    """
    count = 0
    for metrics in metrics_results.values():
        # Instrumento é suficiente se tiver Sharpe calculado e pelo menos 1 trade
        if metrics.sharpe is not None and metrics.num_trades > 0:
            count += 1
    return count


def save_report(report: BacktestReport, output_path: str) -> None:
    """Salva o relatório em JSON.
    
    Args:
        report: BacktestReport to save
        output_path: Path to save the report
    """
    # Ensure directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2, default=str)


def run_offline(data_dir: str, output_path: str, seed: int = 42) -> int:
    """Executa o run offline F6.
    
    Args:
        data_dir: Diretório com dados OHLC
        output_path: Caminho para salvar o relatório
        seed: Seed para reprodutibilidade
        
    Returns:
        0 se PASS, 1 se FAIL
    """
    logger.info(f"Iniciando run offline F6")
    logger.info(f"Data dir: {data_dir}")
    logger.info(f"Output path: {output_path}")
    
    # Step 1: Check if data directory is empty or only .gitkeep
    if check_empty_data_dir(data_dir):
        logger.error(f"Data directory empty or only .gitkeep: {data_dir}")
        raise OfflineRunError("Data directory empty or only .gitkeep - cannot run backtest")
    
    # Step 2: Initialize pipeline
    pipeline = F6Pipeline(data_dir=data_dir, seed=seed)
    
    # Step 3: Load data to check instruments
    logger.info("Loading data...")
    loader_result = pipeline.loader.load_universe()
    
    # Step 4: Check if we have enough instruments loaded
    loaded_count = count_loaded_instruments(loader_result)
    logger.info(f"Loaded {loaded_count} instruments from {data_dir}")
    
    # Step 5: Run the pipeline
    logger.info("Running backtest pipeline...")
    result = pipeline.run()
    
    # Step 6: Check if we have sufficient instruments for gate evaluation
    metrics_results = result.instrument_metrics
    sufficient_count = get_sufficient_instruments_count(metrics_results)
    
    logger.info(f"Sufficient instruments for gate: {sufficient_count}/10")
    
    # Step 7: Build report
    from motor.backtest.report import build_backtest_report
    metrics_list = list(metrics_results.values())
    
    # Calculate trigger rates for solo-ALTA diagnostic
    trigger_rates = {}
    for instrument, output in result.instrument_outputs.items():
        if output.total_bars > 0:
            trigger_rates[instrument] = output.triggers_count / output.total_bars
    
    report = build_backtest_report(metrics_list, trigger_rates, seed=seed)
    
    # Step 8: Save report
    save_report(report, output_path)
    logger.info(f"Report saved to: {output_path}")
    
    # Step 9: Determine exit code based on gate
    if report.gate_result and report.gate_result.passed:
        logger.info(f"GATE PASSED: {report.gate_result.pass_count}/10 instruments with Sharpe > 0.5")
        return 0
    else:
        logger.warning(f"GATE FAILED: {report.gate_result.pass_count if report.gate_result else 0}/10 instruments with Sharpe > 0.5")
        return 1


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Backtest motor-only F6 - Run offline on historical data"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/ohlc",
        help="Directory with historical OHLC data (default: data/ohlc)"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="reports/f6_backtest.json",
        help="Output path for the report JSON (default: reports/f6_backtest.json)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    
    args = parser.parse_args()
    
    try:
        exit_code = run_offline(
            data_dir=args.data_dir,
            output_path=args.out,
            seed=args.seed
        )
        sys.exit(exit_code)
    except OfflineRunError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()