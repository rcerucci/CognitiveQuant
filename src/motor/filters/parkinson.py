"""Filtro de volatilidade Parkinson (US4).

Filtro que detecta spikes de volatilidade usando a clássica estimação de Parkinson high/low.

Spec: §3.3 / US4

Parkinson clássica:
- usando high/low
- σ_t = sqrt(ln(H_t/L_t)^2)
- σ_n = RMS na janela n com fator 1/(4*ln(2))
- Razão σ_20 / σ_60 ≤ 1.5 para PASS
- Falha → NEUTRO temporário (1 barra) + log "volatility_spike_detected"
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class FilterStatus(str, Enum):
    """Status do resultado do filtro."""
    PASS = "PASS"
    NEUTRO_TEMPORARIO = "NEUTRO_TEMPORARIO"


@dataclass
class FilterParkinsonResult:
    """Resultado do filtro Parkinson."""
    status: FilterStatus
    sigma_20: Optional[float] = None
    sigma_60: Optional[float] = None
    ratio: Optional[float] = None
    threshold: float = 1.5
    reason: Optional[str] = None
    log_message: Optional[str] = None


class FilterParkinson:
    """Filtro de volatilidade Parkinson conforme US4.
    
    - Aplica: σ_20 / σ_60 ≤ 1.5
    - Estimador clássico high/low
    - Warm-up < 60 → NEUTRO automático
    - Falha → NEUTRO temporário (1 barra) + log "volatility_spike_detected"
    """
    
    # Fator Parkinson clássico: 1/(4*ln(2))
    PARKINSON_FACTOR = 1.0 / (4.0 * math.log(2))
    SIGMA_20_WINDOW = 20
    SIGMA_60_WINDOW = 60
    THRESHOLD = 1.5
    
    def __init__(self, bars: List, index: int = -1):
        """Inicializa o filtro.
        
        Args:
            bars: Lista de ValidatedBar (do F1)
            index: Índice da barra atual (default: última)
        """
        self.bars = bars
        self.index = index
    
    def _calculate_parkinson_sigma(self, bars_window: List) -> float:
        """Calcula σ usando estimador de Parkinson clássico.
        
        Fórmula: σ = sqrt(Σ ln(H_t/L_t)^2 / n) * (1/(4*ln(2)))
        
        O estimador de Parkinson mede a volatilidade usando apenas
        high e low, ignorando open e close.
        """
        if len(bars_window) == 0:
            return 0.0
        
        squared_logs = []
        for bar in bars_window:
            if bar.low > 0 and bar.high > 0:
                log_ratio = math.log(bar.high / bar.low)
                squared_logs.append(log_ratio ** 2)
        
        if not squared_logs:
            return 0.0
        
        # Mean squared log ratio
        mean_squared = sum(squared_logs) / len(squared_logs)
        
        # Parkinson estimator
        sigma = math.sqrt(mean_squared) * self.PARKINSON_FACTOR
        
        return sigma
    
    def run(self) -> FilterParkinsonResult:
        """Executa o filtro Parkinson.
        
        Returns:
            FilterParkinsonResult com status, valores e motivos
        """
        n = len(self.bars)
        
        # Warm-up check: precisamos de pelo menos 60 barras
        if n < self.SIGMA_60_WINDOW:
            return FilterParkinsonResult(
                status=FilterStatus.NEUTRO_TEMPORARIO,
                reason="warm_up_infeasible"
            )
        
        # Calcular σ_20 e σ_60
        # Usar as últimas barras
        sigma_20 = self._calculate_parkinson_sigma(self.bars[-self.SIGMA_20_WINDOW:])
        sigma_60 = self._calculate_parkinson_sigma(self.bars[-self.SIGMA_60_WINDOW:])
        
        if sigma_60 > 0:
            ratio = sigma_20 / sigma_60
        else:
            ratio = 0.0
        
        if ratio <= self.THRESHOLD:
            return FilterParkinsonResult(
                status=FilterStatus.PASS,
                sigma_20=sigma_20,
                sigma_60=sigma_60,
                ratio=ratio,
                threshold=self.THRESHOLD
            )
        else:
            return FilterParkinsonResult(
                status=FilterStatus.NEUTRO_TEMPORARIO,
                sigma_20=sigma_20,
                sigma_60=sigma_60,
                ratio=ratio,
                threshold=self.THRESHOLD,
                reason="volatility_spike_detected",
                log_message="volatility_spike_detected"
            )