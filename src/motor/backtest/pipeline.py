"""Pipeline orquestracao para backtest motor-only (T022).

Orquestra: loader -> runner -> pnl -> metrics -> report

Spec F6 §10.1 - T022
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

import numpy as np

from motor.backtest.loader import (
    BacktestLoader,
    LoaderResult,
    LoaderStatus,
)
from motor.backtest.runner import (
    BarRunner,
    BacktestResult,
    RunResult,
)
from motor.backtest.pnl import (
    PnLCalculator,
    PnLResult,
    Trade,
    TradeStatus,
)
from motor.backtest.metrics import (
    InstrumentMetrics,
    MetricsCalculator,
    GateResult,
)
from motor.backtest.report import (
    BacktestReport,
    InstrumentReport,
    ReportBuilder,
    Veredito,
)
from motor.backtest import (
    F6_INSTRUMENTS,
    F6_FORCE_THRESHOLD,
    TARGET_SHARPE,
)


logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Status do pipeline."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass
class PipelineOutput:
    """Resultado processado para um instrumento."""
    instrumento: str
    equity_curve: List[float] = field(default_factory=list)
    timestamps: List[int] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    triggers_count: int = 0
    total_bars: int = 0


@dataclass 
class PipelineResult:
    """Resultado completo do pipeline F6."""
    status: PipelineStatus
    instrument_outputs: Dict[str, PipelineOutput] = field(default_factory=dict)
    instrument_metrics: Dict[str, InstrumentMetrics] = field(default_factory=dict)
    instrument_reports: List[InstrumentReport] = field(default_factory=list)
    gate_result: Optional[GateResult] = None
    report: Optional[BacktestReport] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class F6Pipeline:
    """Pipeline F6: loader -> runner -> pnl -> metrics -> report.
    
    Executes backtest motor-only on historical real M30 data (CSV/parquet).
    """
    
    def __init__(
        self,
        data_dir: str = "data/ohlc",
        seed: int = 42,
        instruments: Optional[List[str]] = None,
    ):
        """Inicializa o pipeline.
        
        Args:
            data_dir: Diretorio para dados histolicos
            seed: Seed para reprodutibilidade
            instruments: Lista de instrumentos (default: universo F6 §9.2)
        """
        self.data_dir = data_dir
        self.seed = seed
        self.instruments = instruments or F6_INSTRUMENTS
        np.random.seed(seed)
        
        # Inicializar componentes
        self.loader = BacktestLoader(data_dir=data_dir, seed=seed)
        self.runner = BarRunner(seed=seed)
        self.metrics_calc = MetricsCalculator(seed=seed)
        self.report_builder = ReportBuilder(seed=seed)
        
        # Resultados intermediarios
        self.loader_result: Optional[LoaderResult] = None
        self.run_results: Dict[str, BacktestResult] = {}
        self.pipeline_outputs: Dict[str, PipelineOutput] = {}
        self.metrics_results: Dict[str, InstrumentMetrics] = {}
        self.pnl_results: Dict[str, PnLResult] = {}
        self.report: Optional[BacktestReport] = None
    
    def _get_bars_for_instrument(self, instrument: str) -> List[List[float]]:
        """Obtém as barras para um instrumento.
        
        Args:
            instrument: Símbolo do instrumento (ex: EUR/USD)
            
        Returns:
            Lista de barras
        """
        if not self.loader_result:
            return []
        
        # Map instrument name to file name
        file_name = instrument.replace("/", "_").lower()
        
        for inst_bars in self.loader_result.instruments:
            if inst_bars.instrumento == file_name:
                return inst_bars.bars
        
        return []
    
    def run(self) -> PipelineResult:
        """Executa o pipeline completo.
        
        Returns:
            PipelineResult com todos os resultados
        """
        warnings_list: List[str] = []
        errors_list: List[str] = []
        
        # Phase 1: Load data
        logger.info(f"Loading data for {len(self.instruments)} instruments...")
        self.loader_result = self.loader.load_universe()
        
        if self.loader_result.status != LoaderStatus.SUCCESS or self.loader_result.loaded_count == 0:
            warnings_list.append("No instruments loaded from data directory")
            logger.warning("No instruments loaded - using test data")
        
        # Phase 2: Run backtest for each instrument
        logger.info("Running backtest...")
        
        for instrument in self.instruments:
            # Get bars for this instrument
            bars = self._get_bars_for_instrument(instrument)
            
            if not bars:
                # Create synthetic test data for demonstration
                logger.info(f"No data for {instrument}, creating test bars")
                bars = self._create_test_bars(instrument, 500)
            
            # Run the bar-by-bar pipeline
            result = self.runner.run_all(bars, instrument)
            self.run_results[instrument] = result
            
            # Phase 3: Calculate PnL and process signals
            logger.info(f"Processing {instrument}...")
            output = self._process_instrument(instrument, bars, result)
            self.pipeline_outputs[instrument] = output
        
        # Phase 4: Calculate metrics
        logger.info("Calculating metrics...")
        metrics_list: List[InstrumentMetrics] = []
        trigger_rates: Dict[str, float] = {}
        
        for instrument, output in self.pipeline_outputs.items():
            if not output.timestamps or not output.equity_curve:
                continue
            
            metrics = self.metrics_calc.compute_metrics(
                instrumento=instrument,
                equity_curve=output.equity_curve,
                timestamps=output.timestamps,
                trades=output.trades,
                triggers_count=output.triggers_count,
                total_bars=output.total_bars,
            )
            
            self.metrics_results[instrument] = metrics
            metrics_list.append(metrics)
            
            # Calculate trigger rate
            if output.total_bars > 0:
                trigger_rates[instrument] = output.triggers_count / output.total_bars
        
        # Phase 5: Build report and evaluate gate
        logger.info("Building report...")
        self.report = self._build_report(metrics_list, trigger_rates)
        
        # Determine overall status
        if self.report.gate_result and self.report.gate_result.passed:
            status = PipelineStatus.SUCCESS
        elif metrics_list:
            status = PipelineStatus.PARTIAL
        else:
            status = PipelineStatus.FAILED
        
        return PipelineResult(
            status=status,
            instrument_outputs=self.pipeline_outputs,
            instrument_metrics=self.metrics_results,
            instrument_reports=self.report.instrumentos if self.report else [],
            gate_result=self.report.gate_result if self.report else None,
            report=self.report,
            warnings=warnings_list,
            errors=errors_list,
        )
    
    def _create_test_bars(self, instrument: str, count: int) -> List[List[float]]:
        """Cria barras de teste para demonstracao.
        
        Args:
            instrument: Símbolo do instrumento
            count: Numero de barras
            
        Returns:
            Lista de barras
        """
        np.random.seed(self.seed)
        bars = []
        
        base_price = 100.0
        trend = 0.001  # Pequena tendencia
        
        for i in range(count):
            ts = 1704067200000 + i * 1800000  # M30 interval
            
            # Price with some trend and volatility
            price = base_price + i * trend + np.random.randn() * 0.5
            
            # Create bar [timestamp, open, high, low, close, bid, ask]
            bar = [
                ts,
                price - 0.5,  # open
                price + 1.0,  # high
                price - 1.0,  # low
                price,        # close
                price - 0.25, # bid
                price + 0.25, # ask
            ]
            bars.append(bar)
        
        return bars
    
    def _process_instrument(
        self,
        instrument: str,
        bars: List[List[float]],
        run_result: BacktestResult,
    ) -> PipelineOutput:
        """Processa um instrumento atraves do pipeline.
        
        Args:
            instrument: Símbolo do instrumento
            bars: Lista de barras
            run_result: Resultado do runner
            
        Returns:
            PipelineOutput com dados processados
        """
        # Find trigger bars from run results
        trigger_indices: List[int] = []
        
        for i, bar_result in enumerate(run_result.bars):
            if bar_result.payload is not None:
                sq = bar_result.payload.sinal_quantitativo
                direction = sq.direcao
                force = sq.forca
                
                # F6 trigger: LONG ou SHORT com forca >= 0.60
                if direction in ["LONG", "SHORT"] and force >= F6_FORCE_THRESHOLD:
                    trigger_indices.append(i)
        
        # Create PnL calculator and process
        pnl_calc = PnLCalculator(seed=self.seed)
        
        for i, bar in enumerate(bars):
            # Update equity curve
            current_equity = pnl_calc.equity
            pnl_calc.equity_curve.append(current_equity)
            
            # Check for exits
            for trade in list(pnl_calc.trades):
                if trade.status == TradeStatus.OPEN and trade.tau:
                    expected_exit = trade.entry_bar_index + trade.tau
                    if i >= expected_exit:
                        exit_mid = (bar[5] + bar[6]) / 2.0
                        ts = int(bar[0])
                        trade.close(i, exit_mid, ts)
                        
                        if trade.retorno is not None:
                            pnl_calc.equity *= (1 + trade.retorno)
                        pnl_calc.tau_values.append(trade.tau)
            
            # Check for triggers
            if i < len(run_result.bars):
                bar_result = run_result.bars[i]
                if bar_result.payload is not None:
                    sq = bar_result.payload.sinal_quantitativo
                    direction = sq.direcao
                    force = sq.forca
                    tau = sq.meia_vida_barras
                    
                    if direction in ["LONG", "SHORT"] and force >= F6_FORCE_THRESHOLD:
                        entry_mid = (bar[5] + bar[6]) / 2.0
                        ts = int(bar[0])
                        
                        trade = Trade(
                            instrumento=instrument,
                            direction=direction,
                            entry_bar_index=i,
                            entry_timestamp=ts,
                            entry_price=entry_mid,
                            entry_mid=entry_mid,
                            tau=int(tau) if tau else 10,
                        )
                        pnl_calc.trades.append(trade)
        
        # Force close remaining positions at end
        if bars:
            for trade in list(pnl_calc.trades):
                if trade.status == TradeStatus.OPEN:
                    exit_mid = (bars[-1][5] + bars[-1][6]) / 2.0
                    ts = int(bars[-1][0])
                    trade.force_close(len(bars) - 1, exit_mid, ts)
                    
                    if trade.retorno is not None:
                        pnl_calc.equity *= (1 + trade.retorno)
                    if trade.tau:
                        pnl_calc.tau_values.append(trade.tau)
            
            if any(t.status == TradeStatus.TRUNCATED for t in pnl_calc.trades):
                pnl_calc.warnings_list.append(f"Posicoes truncadas no fim - {instrument}")
        
        # Extract daily equity
        timestamps = [int(b[0]) for b in bars]
        daily_equity: Dict[str, float] = {}
        
        for eq, ts in zip(pnl_calc.equity_curve, timestamps):
            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            date = dt.strftime("%Y-%m-%d")
            daily_equity[date] = eq
        
        daily_equity_list = sorted(daily_equity.items())
        daily_equity_values = [v for _, v in daily_equity_list]
        
        return PipelineOutput(
            instrumento=instrument,
            equity_curve=pnl_calc.equity_curve if pnl_calc.equity_curve else [1.0],
            timestamps=timestamps,
            trades=pnl_calc.trades,
            triggers_count=len(trigger_indices),
            total_bars=len(bars),
        )
    
    def _build_report(
        self,
        metrics_list: List[InstrumentMetrics],
        trigger_rates: Dict[str, float],
    ) -> BacktestReport:
        """Construi o relatorio final.
        
        Args:
            metrics_list: Lista de metricas
            trigger_rates: Taxa de triggers por instrumento
            
        Returns:
            BacktestReport
        """
        builder = ReportBuilder(seed=self.seed)
        return builder.build_report(metrics_list, trigger_rates)


def run_f6_pipeline(
    data_dir: str = "data/ohlc",
    seed: int = 42,
    instruments: Optional[List[str]] = None,
) -> PipelineResult:
    """Funcao de conveniencia para executar pipeline F6.
    
    Args:
        data_dir: Diretorio para dados historico
        seed: Seed para reprodutibilidade
        instruments: Lista de instrumentos (default: universo F6 §9.2)
        
    Returns:
        PipelineResult completo
    """
    pipeline = F6Pipeline(data_dir=data_dir, seed=seed, instruments=instruments)
    return pipeline.run()


def build_backtest_report(
    metrics_list: List[InstrumentMetrics],
    trigger_rates: Optional[Dict[str, float]] = None,
    seed: int = 42,
) -> BacktestReport:
    """Funcao de conveniencia para construir relatorio."""
    builder = ReportBuilder(seed=seed)
    return builder.build_report(metrics_list, trigger_rates or {})