"""Runner barra-a-barra F1→F5 para backtest motor-only (US1).

Pure Python runner - no TA, no MCP, no executor.
Consumes F1→F5 APIs in-memory.

Spec F6 §10.1 - US1, T013
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import logging
import warnings

import numpy as np

# Import F1-F5 APIs
from motor.ohlc.validation import validate_bars_sequence, ValidationError, ValidatedBar
from motor.filters.pipeline import Pipeline, PipelineStatus
from motor.regime.pipeline import F3Pipeline, F3Status
from motor.vol.pipeline import F4Pipeline, F4Status
from motor.signal.pipeline import F5Pipeline, F5Status
from motor.signal.payload import PayloadMotor, criar_payload_neutro

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class RunnerStatus(str, Enum):
    """Status do runner."""
    SUCCESS = "SUCCESS"
    ABORT = "ABORT"
    NEUTRAL = "NEUTRAL"
    SKIPPED = "SKIPPED"


class SignalDirection(str, Enum):
    """Direção do sinal."""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRO = "NEUTRO"


@dataclass
class RunResult:
    """Resultado de uma execução de barra."""
    timestamp: int
    payload: Optional[PayloadMotor] = None
    f1_validated: bool = False
    f2_status: str = "NEUTRO"
    f3_status: str = "NEUTRO"
    f4_status: str = "NEUTRO"
    f5_status: str = "NEUTRO"
    has_position: bool = False
    position_direction: str = ""
    bar_index: int = -1
    reason: str = ""


@dataclass
class BacktestResult:
    """Resultado completo do backtest motor-only."""
    instrumento: str
    bars: List[RunResult] = field(default_factory=list)
    status: RunnerStatus = RunnerStatus.SUCCESS
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class BarRunner:
    """Runner para backtest motor-only.
    
    Executa o pipeline F1→F5 barra a barra:
    1. Validação F1 (OHLC)
    2. Filtros F2
    3. Regime F3
    4. Volatilidade F4
    5. Sinal F5
    
    Não importa TA, MCP, nem executor.
    """
    
    def __init__(self, seed: int = 42, instrumento: str = ""):
        """Inicializa o runner.
        
        Args:
            seed: Seed para reprodutibilidade
            instrumento: Símbolo do instrumento
        """
        self.seed = seed
        self.instrumento = instrumento
        np.random.seed(seed)
        # Track window for rolling calculations
        self.validated_bars: List[ValidatedBar] = []
        self.returns_history: List[float] = []
        self.z_history: List[float] = []
        
    def _init_validated_bars(self, all_bars: List[List[float]]) -> List[ValidatedBar]:
        """Valida todas as barras uma vez via F1."""
        try:
            validated_series = validate_bars_sequence(all_bars)
            return validated_series.bars
        except ValidationError as e:
            logger.error(f"F1 validation failed: {e.code}")
            return []
    
    def run_bar(
        self,
        bar: ValidatedBar,
        bar_index: int,
    ) -> RunResult:
        """Executa uma única barra através do pipeline F1→F5.
        
        Args:
            bar: Barra validada (ValidatedBar)
            bar_index: Índice desta barra
            
        Returns:
            RunResult com resultado da execução
        """
        timestamp = bar.timestamp
        
        # F1: Já validado acima - usar validated_bars
        if bar.status.value == "gap_dados":
            return RunResult(
                timestamp=timestamp,
                f1_validated=False,
                bar_index=bar_index,
                reason="F1 validation: gap_dados",
            )
        
        # F2: Pipeline de filtros
        window_start = max(0, bar_index - 199)  # 200 bars window
        filter_bars = self.validated_bars[window_start:bar_index + 1]
        
        if len(filter_bars) < 2:
            # Not enough data for filters
            return RunResult(
                timestamp=timestamp,
                payload=None,
                f1_validated=True,
                f2_status="NEUTRO",
                bar_index=bar_index,
                reason="Not enough data for F2 filters",
            )
        
        # Calculate relative index within the window
        relative_index = bar_index - window_start
        
        try:
            filter_pipeline = Pipeline(filter_bars, index=relative_index)
            f2_result = filter_pipeline.run()
        except Exception as e:
            logger.warning(f"F2 filter error at bar {bar_index}: {e}")
            return RunResult(
                timestamp=timestamp,
                payload=None,
                f1_validated=True,
                f2_status="NEUTRO",
                bar_index=bar_index,
                reason=f"F2 filter error: {str(e)}",
            )
        
        if f2_result.status != PipelineStatus.PASS:
            return RunResult(
                timestamp=timestamp,
                payload=None,
                f1_validated=True,
                f2_status=f2_result.status.value,
                bar_index=bar_index,
                reason=f2_result.reason or "F2 filter failed",
            )
        
        # F3: Pipeline regime (Hurst → OU → Bootstrap)
        # Need log prices series
        try:
            X_t_series = []
            for b in filter_bars:
                mid = b.P_t  # (bid + ask) / 2
                X_t_series.append(np.log(mid))
            
            f3_pipeline = F3Pipeline(f2_result, X_t_series)
            f3_result = f3_pipeline.run()
        except Exception as e:
            logger.warning(f"F3 regime error at bar {bar_index}: {e}")
            return RunResult(
                timestamp=timestamp,
                payload=None,
                f1_validated=True,
                f2_status="PASS",
                f3_status="NEUTRAL",
                bar_index=bar_index,
                reason=f"F3 regime error: {str(e)}",
            )
        
        if f3_result.status != F3Status.PASS:
            # F3 NEUTRAL means signal direction is NEUTRAL
            # We still need to create a neutro payload
            payload = criar_payload_neutro(
                instrumento=self.instrumento,
                candle_contexto={
                    "timestamp": bar.timestamp,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                },
            )
            return RunResult(
                timestamp=timestamp,
                payload=payload,
                f1_validated=True,
                f2_status="PASS",
                f3_status=f3_result.status.value,
                f5_status="NEUTRAL",
                bar_index=bar_index,
                reason=f3_result.reason or "F3 NEUTRAL",
            )
        
        # F4: Pipeline volatilidade
        # 201 precos -> 200 retornos (GARCH)
        returns_start = max(0, bar_index - 200)
        returns_bars = self.validated_bars[returns_start:bar_index + 1]

        z_history_for_f4 = self.z_history[-199:] if len(self.z_history) > 199 else self.z_history

        try:
            returns = []
            for i in range(1, len(returns_bars)):
                b1 = returns_bars[i-1]
                b2 = returns_bars[i]
                mid1 = b1.P_t
                mid2 = b2.P_t
                if mid1 > 0:
                    returns.append(np.log(mid2 / mid1))
                else:
                    returns.append(0.0)

            X_t = bar.P_t
            r_t = returns[-1] if returns else 0.0
            returns_for_garch = returns[-200:] if len(returns) >= 200 else []

            f4_pipeline = F4Pipeline(
                f3_result=f3_result,
                X_t=X_t,
                r_t=r_t,
                returns_history=returns_for_garch,
                z_history=z_history_for_f4,
                seed=self.seed,
            )
            f4_result = f4_pipeline.run()
            
            # After F4 PASS, append z_t to z_history (cap at 200)
            # Only append real z_t values, never tau or fake zeros
            if f4_result.status == F4Status.PASS and f4_result.z_t is not None:
                self.z_history.append(f4_result.z_t)
                if len(self.z_history) > 200:
                    self.z_history = self.z_history[-200:]
        except Exception as e:
            logger.warning(f"F4 vol error at bar {bar_index}: {e}")
            return RunResult(
                timestamp=timestamp,
                payload=None,
                f1_validated=True,
                f2_status="PASS",
                f3_status="PASS",
                f4_status="NEUTRAL",
                bar_index=bar_index,
                reason=f"F4 vol error: {str(e)}",
            )
        
        if f4_result.status != F4Status.PASS:
            # F4 NEUTRAL - still create neutro payload
            payload = criar_payload_neutro(
                instrumento=self.instrumento,
                candle_contexto={
                    "timestamp": bar.timestamp,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                },
                evidencias=[f"F4 status: {f4_result.status.value}"],
            )
            return RunResult(
                timestamp=timestamp,
                payload=payload,
                f1_validated=True,
                f2_status="PASS",
                f3_status="PASS",
                f4_status=f4_result.status.value,
                f5_status="NEUTRAL",
                bar_index=bar_index,
                reason=f4_result.reason or "F4 NEUTRAL",
            )
        
        # F5: Pipeline sinal
        try:
            # Prepare return history (log returns)
            log_returns = []
            for i in range(1, len(filter_bars)):
                mid_prev = filter_bars[i-1].P_t
                mid_curr = filter_bars[i].P_t
                if mid_prev > 0:
                    log_returns.append(np.log(mid_curr / mid_prev))
            log_returns = log_returns[-200:] if len(log_returns) > 200 else log_returns
            
            # Convert ValidatedBar to list for F5Pipeline (expects List[float])
            bar_as_list = [
                bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.bid, bar.ask
            ]
            
            f5_pipeline = F5Pipeline(
                f4_result=f4_result,
                f3_result=f3_result,
                bar=bar_as_list,
                returns=log_returns,
                instrumento=self.instrumento,
                seed=self.seed,
            )
            f5_result = f5_pipeline.run()
        except Exception as e:
            logger.warning(f"F5 signal error at bar {bar_index}: {e}")
            return RunResult(
                timestamp=timestamp,
                payload=None,
                f1_validated=True,
                f2_status="PASS",
                f3_status="PASS",
                f4_status="PASS",
                f5_status="NEUTRAL",
                bar_index=bar_index,
                reason=f"F5 signal error: {str(e)}",
            )
        
        return RunResult(
            timestamp=timestamp,
            payload=f5_result.payload,
            f1_validated=True,
            f2_status=f2_result.status.value,
            f3_status=f3_result.status.value,
            f4_status=f4_result.status.value,
            f5_status=f5_result.status.value,
            bar_index=bar_index,
            reason=f5_result.reason or "",
        )
    
    def run_all(
        self,
        bars: List[List[float]],
        instrumento: str,
    ) -> BacktestResult:
        """Executa todas as barras do backtest.
        
        Args:
            bars: Lista de barras OHLC
            instrumento: Símbolo do instrumento
            
        Returns:
            BacktestResult com todos os resultados
        """
        results = []
        warnings_list = []
        errors_list = []
        
        self.instrumento = instrumento
        
        # F1: Validar todas as barras uma vez
        self.validated_bars = self._init_validated_bars(bars)
        
        if not self.validated_bars:
            return BacktestResult(
                instrumento=instrumento,
                bars=[],
                status=RunnerStatus.ABORT,
                warnings=[],
                errors=["F1 validation failed for all bars"],
            )
        
        # Process each bar
        for i, bar in enumerate(self.validated_bars):
            result = self.run_bar(bar, i)
            results.append(result)
            
            if result.reason and "error" in result.reason.lower():
                warnings_list.append(f"Bar {i}: {result.reason}")
        
        return BacktestResult(
            instrumento=instrumento,
            bars=results,
            status=RunnerStatus.SUCCESS,
            warnings=warnings_list,
            errors=errors_list,
        )


def run_backtest(
    bars: List[List[float]],
    instrumento: str,
    seed: int = 42,
) -> BacktestResult:
    """Função de conveniência para executar backtest.
    
    Args:
        bars: Lista de barras OHLC
        instrumento: Símbolo do instrumento
        seed: Seed para reprodutibilidade
        
    Returns:
        BacktestResult com resultados
    """
    runner = BarRunner(seed=seed)
    return runner.run_all(bars, instrumento)


def run_f6_pipeline(
    bars: List[List[float]],
    instrumento: str,
    seed: int = 42,
) -> List[RunResult]:
    """Executa o pipeline F6 e retorna resultados por barra.
    
    Args:
        bars: Lista de barras OHLC
        instrumento: Símbolo do instrumento
        seed: Seed para reprodutibilidade
        
    Returns:
        Lista de RunResult
    """
    result = run_backtest(bars, instrumento, seed)
    return result.bars