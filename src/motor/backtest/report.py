"""Relatório e gate 7/10 para backtest motor-only (US5).

Gate >= 7/10 Sharpe > 0.5 e relatório JSON serializable in-memory.

Spec F6 §10.1 - US5, T021
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

import numpy as np

from motor.backtest.metrics import (
    InstrumentMetrics,
    GateResult,
    MetricsCalculator,
    check_gate,
)
from motor.backtest import (
    TARGET_SHARPE,
    TARGET_WR,
    TARGET_PF,
    TARGET_MAXDD,
    TARGET_TRIGGER_RATE_MIN,
    TARGET_TRIGGER_RATE_MAX,
    TARGET_TAU_MEDIAN_MIN,
    TARGET_TAU_MEDIAN_MAX,
    SHARPE_GATE_THRESHOLD,
    SHARPE_GATE_MIN_INSTRUMENTS,
)

logger = logging.getLogger(__name__)


class Veredito(str, Enum):
    """Veredito do gate."""
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class InstrumentReport:
    """Relatório para um instrumento."""
    instrumento: str
    sharpe: Optional[float] = None
    wr: Optional[float] = None
    pf: Optional[float] = None
    maxdd: Optional[float] = None
    trigger_rate: Optional[float] = None
    tau_median: Optional[int] = None
    
    # Flags vs alvos
    sharpe_target_met: bool = False
    wr_target_met: bool = False
    pf_target_met: bool = False
    maxdd_target_met: bool = True  # MaxDD < 15%
    trigger_rate_target_met: bool = False
    tau_median_target_met: bool = False
    
    # Taxa so-ALTA (diagnóstico F7, não gate F6)
    solealta_rate: Optional[float] = None
    
    # Pass/Fail individual
    passed: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class BacktestReport:
    """Relatório completo do backtest motor-only."""
    timestamp: str
    instrumentos: List[InstrumentReport] = field(default_factory=list)
    gate_result: Optional[GateResult] = None
    veredito: Veredito = Veredito.FAIL
    total_instruments: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "timestamp": self.timestamp,
            "veredito": self.veredito.value,
            "total_instruments": self.total_instruments,
            "gate_result": {
                "pass_count": self.gate_result.pass_count if self.gate_result else 0,
                "fail_count": self.gate_result.fail_count if self.gate_result else 0,
                "total": self.gate_result.total_instruments if self.gate_result else 0,
                "passed": self.gate_result.passed if self.gate_result else False,
            } if self.gate_result else None,
            "instrumentos": [asdict(inst) for inst in self.instrumentos],
        }
    
    def to_json(self) -> str:
        """Converte para JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


class ReportBuilder:
    """Construtor de relatórios para backtest motor-only."""
    
    # Target thresholds from spec §10.1
    TARGET_SHARPE = 0.5
    TARGET_WR = 0.45
    TARGET_PF = 1.3
    TARGET_MAXDD = 0.15
    TARGET_TRIGGER_RATE_MIN = 0.05
    TARGET_TRIGGER_RATE_MAX = 0.15
    TARGET_TAU_MEDIAN_MIN = 3
    TARGET_TAU_MEDIAN_MAX = 8
    
    def __init__(self, seed: int = 42):
        """Inicializa o construtor."""
        self.seed = seed
        np.random.seed(seed)
    
    def _create_instrument_report(self, metrics: InstrumentMetrics) -> InstrumentReport:
        """Cria relatório para um instrumento."""
        report = InstrumentReport(
            instrumento=metrics.instrumento,
            sharpe=metrics.sharpe,
            wr=metrics.wr,
            pf=metrics.pf,
            maxdd=metrics.maxdd,
            trigger_rate=metrics.trigger_rate,
            tau_median=metrics.tau_median,
        )
        
        # Verificar met targets
        report.sharpe_target_met = metrics.sharpe is not None and metrics.sharpe > self.TARGET_SHARPE
        report.wr_target_met = metrics.wr is not None and metrics.wr > self.TARGET_WR
        report.pf_target_met = metrics.pf is not None and metrics.pf > self.TARGET_PF
        report.maxdd_target_met = metrics.maxdd is not None and metrics.maxdd < self.TARGET_MAXDD
        report.trigger_rate_target_met = (
            metrics.trigger_rate is not None and
            metrics.trigger_rate >= self.TARGET_TRIGGER_RATE_MIN and
            metrics.trigger_rate <= self.TARGET_TRIGGER_RATE_MAX
        )
        report.tau_median_target_met = (
            metrics.tau_median is not None and
            metrics.tau_median >= self.TARGET_TAU_MEDIAN_MIN and
            metrics.tau_median <= self.TARGET_TAU_MEDIAN_MAX
        )
        
        # Pass/Fail individual baseado em Sharpe (primary gate)
        report.passed = report.sharpe_target_met
        
        # Racso para pass
        if not report.sharpe_target_met and metrics.sharpe:
            report.reasons.append(f"Sharpe {metrics.sharpe:.3f} <= {self.TARGET_SHARPE}")
        if metrics.sharpe is None:
            report.reasons.append("Sharpe não calculado")
        
        return report
    
    def build_report(
        self,
        metrics_list: List[InstrumentMetrics],
        trigger_rates: Optional[Dict[str, float]] = None,
    ) -> BacktestReport:
        """Constrói relatório completo.
        
        Args:
            metrics_list: Lista de metricas por instrumento
            trigger_rates: Opcional - taxa de triggers so-ALTA por instrumento (diagnóstico F7)
            
        Returns:
            BacktestReport completo
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Criar relatório por instrumento
        instrument_reports = [
            self._create_instrument_report(m) for m in metrics_list
        ]
        
        # Adicionar taxa so-ALTA se fornecido
        if trigger_rates:
            for report in instrument_reports:
                report.solealta_rate = trigger_rates.get(report.instrumento)
        
        # Verificar gate
        gate_result = check_gate(metrics_list)
        
        # Determinar veredito global
        veredito = Veredito.PASS if gate_result.passed else Veredito.FAIL
        
        return BacktestReport(
            timestamp=timestamp,
            instrumentos=instrument_reports,
            gate_result=gate_result,
            veredito=veredito,
            total_instruments=len(metrics_list),
        )


def build_backtest_report(
    metrics_list: List[InstrumentMetrics],
    trigger_rates: Optional[Dict[str, float]] = None,
    seed: int = 42,
) -> BacktestReport:
    """Funcao de conveniencia para construir relatório.
    
    Args:
        metrics_list: Lista de metricas por instrumento
        trigger_rates: Taxa de triggers so-ALTA (opcional)
        seed: Seed para reprodutibilidade
        
    Returns:
        BacktestReport
    """
    builder = ReportBuilder(seed=seed)
    return builder.build_report(metrics_list, trigger_rates)


def evaluate_gate(metrics_list: List[InstrumentMetrics]) -> GateResult:
    """Avalia gate 7/10 Sharpe > 0.5.
    
    Args:
        metrics_list: Lista de metricas
        
    Returns:
        GateResult com pass/fail
    """
    return check_gate(metrics_list)