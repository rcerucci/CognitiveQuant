"""Calculo de metricas §10.1 para backtest motor-only (US4).

Sharpe (equity diario, Rf=0, * sqrt(252)), WR, PF, MaxDD, taxa triggers, mediana tau.

Spec F6 §10.1 - US4, T018
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class InstrumentMetrics:
    """Metricas para um instrumento.
    
    Sharpe = equity diario, Rf=0, * sqrt(252)
    WR = Win Rate
    PF = Profit Factor
    MaxDD = Max Drawdown
    taxa_triggers = % barras com trigger F6
    tau_median = mediana dos valores de tau
    """
    instrumento: str
    sharpe: Optional[float] = None
    wr: Optional[float] = None
    pf: Optional[float] = None
    maxdd: Optional[float] = None
    trigger_rate: Optional[float] = None
    tau_median: Optional[int] = None
    num_trades: int = 0
    num_wins: int = 0
    total_return: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    tau_values: List[int] = field(default_factory=list)
    triggers_count: int = 0
    total_bars: int = 0
    sharpes_vs_target: Dict[str, bool] = field(default_factory=dict)


@dataclass
class GateResult:
    """Resultado do gate 7/10."""
    pass_count: int
    fail_count: int
    total_instruments: int
    passed: bool
    details: List[Dict[str, Any]] = field(default_factory=list)


class MetricsCalculator:
    """Calculadora de metricas para backtest motor-only."""
    
    # Constantes do spec F6 §10.1
    SHARPE_RISK_FREE_RATE = 0.0
    SHARPE_ANNUALIZATION = math.sqrt(252)  # sqrt(252)
    
    # Thresholds para trigger F6
    FORCE_THRESHOLD = 0.60  # ALTA or MEDIA
    
    def __init__(self, seed: int = 42):
        """Inicializa o calculador."""
        self.seed = seed
        np.random.seed(seed)
    
    def _extract_daily_equity(self, equity_curve: List[float], timestamps: List[int]) -> List[float]:
        """Extrai equity diario da curva de equity.
        
        Pega o ultimo equity de cada dia.
        """
        if not equity_curve or not timestamps:
            return []
        
        # Agrupar por data
        daily_equity = {}
        for eq, ts in zip(equity_curve, timestamps):
            date = self._timestamp_to_date(ts)
            daily_equity[date] = eq
        
        # Ordenar por data e retornar equity diario
        sorted_dates = sorted(daily_equity.keys())
        return [daily_equity[d] for d in sorted_dates]
    
    def _timestamp_to_date(self, ts: int) -> str:
        """Converte timestamp para data UTC."""
        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    
    def calculate_sharpe(self, daily_equity: List[float]) -> float:
        """Calcula Sharpe de equity diario.
        
        Sharpe = sqrt(252) * mean(daily_returns) / std(daily_returns)
        Onde daily_returns = diff(equity) / equity[:-1]
        
        Args:
            daily_equity: Serie de equity diario
            
        Returns:
            Sharpe annualizado
        """
        if len(daily_equity) < 2:
            return 0.0
        
        equity_array = np.array(daily_equity)
        
        # Calcular retornos diarios
        returns = np.diff(equity_array) / equity_array[:-1]
        
        if len(returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
        
        if std_return == 0:
            return 0.0 if mean_return == 0 else float('inf')
        
        daily_sharpe = (mean_return - self.SHARPE_RISK_FREE_RATE) / std_return
        annualized_sharpe = daily_sharpe * self.SHARPE_ANNUALIZATION
        
        return float(annualized_sharpe)
    
    def calculate_wr(self, num_wins: int, num_losses: int) -> float:
        """Calcula Win Rate.
        
        WR = num_wins / (num_wins + num_losses)
        """
        total = num_wins + num_losses
        if total == 0:
            return 0.0
        return num_wins / total
    
    def calculate_pf(self, num_wins: int, num_losses: int, gross_wins: float, gross_losses: float) -> float:
        """Calcula Profit Factor.
        
        PF = gross_wins / gross_losses
        """
        if gross_losses == 0:
            return float('inf') if gross_wins > 0 else 0.0
        return gross_wins / gross_losses
    
    def calculate_maxdd(self, equity_curve: List[float]) -> float:
        """Calcula Max Drawdown.
        
        MaxDD = max(peak - equity) / peak
        """
        if not equity_curve:
            return 0.0
        
        equity_array = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_array)
        drawdowns = (peak - equity_array) / peak
        
        return float(np.max(drawdowns))
    
    def calculate_trigger_rate(self, triggers_count: int, total_bars: int) -> float:
        """Calcula taxa de triggers.
        
        taxa_triggers = triggers_count / total_bars
        """
        if total_bars == 0:
            return 0.0
        return triggers_count / total_bars
    
    def calculate_tau_median(self, tau_values: List[int]) -> int:
        """Calcula mediana dos valores de tau."""
        if not tau_values:
            return 0
        return int(np.median(tau_values))
    
    def compute_metrics(
        self,
        instrumento: str,
        equity_curve: List[float],
        timestamps: List[int],
        trades: List[Any],  # List[Trade]
        triggers_count: int,
        total_bars: int,
    ) -> InstrumentMetrics:
        """Computa todas as metricas para um instrumento.
        
        Args:
            instrumento: Símbolo do instrumento
            equity_curve: Curva de equity
            timestamps: Timestamps das barras
            trades: Lista de trades
            triggers_count: Numero de triggers F6
            total_bars: Total de barras no backtest
            
        Returns:
            InstrumentMetrics complete
        """
        # Extrair equity diario
        daily_equity = self._extract_daily_equity(equity_curve, timestamps)
        
        # Calcular Sharpe
        sharpe = self.calculate_sharpe(daily_equity)
        
        # Contar trades
        num_trades = len(trades)
        num_wins = sum(1 for t in trades if t.retorno and t.retorno > 0)
        num_losses = num_trades - num_wins
        
        # Calcular WR
        wr = self.calculate_wr(num_wins, num_losses)
        
        # Calcular PF
        gross_wins = sum(t.retorno for t in trades if t.retorno and t.retorno > 0)
        gross_losses = abs(sum(t.retorno for t in trades if t.retorno and t.retorno < 0))
        pf = self.calculate_pf(num_wins, num_losses, gross_wins, gross_losses)
        
        # Calcular MaxDD
        maxdd = self.calculate_maxdd(equity_curve)
        
        # Calcular taxa triggers
        trigger_rate = self.calculate_trigger_rate(triggers_count, total_bars)
        
        # Calcular tau median
        tau_values = [t.tau for t in trades if t.tau]
        tau_median = self.calculate_tau_median(tau_values)
        
        # Total return
        total_return = equity_curve[-1] - equity_curve[0] if equity_curve else 0.0
        
        return InstrumentMetrics(
            instrumento=instrumento,
            sharpe=sharpe,
            wr=wr,
            pf=pf,
            maxdd=maxdd,
            trigger_rate=trigger_rate,
            tau_median=tau_median,
            num_trades=num_trades,
            num_wins=num_wins,
            total_return=total_return,
            equity_curve=equity_curve,
            daily_returns=daily_equity,
            tau_values=tau_values,
            triggers_count=triggers_count,
            total_bars=total_bars,
        )


def run_metrics(
    equity_curve: List[float],
    timestamps: List[int],
    trades: List[Any],
    triggers_count: int,
    total_bars: int,
    seed: int = 42,
) -> InstrumentMetrics:
    """Funcao de conveniencia para calcular metricas.
    
    Args:
        equity_curve: Curva de equity
        timestamps: Timestamps
        trades: Lista de trades
        triggers_count: Numero de triggers
        total_bars: Total de barras
        seed: Seed para reprodutibilidade
        
    Returns:
        InstrumentMetrics
    """
    calculator = MetricsCalculator(seed=seed)
    return calculator.compute_metrics(
        instrumento="unknown",
        equity_curve=equity_curve,
        timestamps=timestamps,
        trades=trades,
        triggers_count=triggers_count,
        total_bars=total_bars,
    )


def check_gate(results: List[InstrumentMetrics]) -> GateResult:
    """Verifica gate 7/10 Sharpe > 0.5.
    
    Args:
        results: Lista de metricas por instrumento
        
    Returns:
        GateResult com pass/fail
    """
    sharpes = [m.sharpe for m in results if m.sharpe is not None]
    
    pass_count = sum(1 for s in sharpes if s > 0.5)
    fail_count = len(sharpes) - pass_count
    
    passed = pass_count >= 7
    
    details = [
        {
            "instrumento": m.instrumento,
            "sharpe": m.sharpe,
            "passed": m.sharpe is not None and m.sharpe > 0.5,
        }
        for m in results
    ]
    
    return GateResult(
        pass_count=pass_count,
        fail_count=fail_count,
        total_instruments=len(results),
        passed=passed,
        details=details,
    )


def calculate_sharpe_from_equity(equity: List[float], risk_free: float = 0.0) -> float:
    """Calcula Sharpe a partir de uma serie de equity.
    
    Usa retornos de equity diario, Rf=0, sqrt(252).
    
    Args:
        equity: Serie de valores de equity (diario)
        risk_free: Taxa livre de risco (default 0)
        
    Returns:
        Sharpe annualizado
    """
    if len(equity) < 2:
        return 0.0
    
    returns = np.diff(equity) / np.array(equity[:-1])
    
    if len(returns) == 0:
        return 0.0
    
    mean_return = np.mean(returns)
    std_return = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
    
    if std_return == 0:
        return 0.0
    
    daily_sharpe = (mean_return - risk_free) / std_return
    annualized_sharpe = daily_sharpe * math.sqrt(252)
    
    return annualized_sharpe