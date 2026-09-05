"""Filtro de spread anômalo (US1).

Filtro de qualidade que rejeita barras com spread acima de 2× a média de 20 barras.

Spec: §3.3 / US1
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class FilterStatus(str, Enum):
    """Status do resultado do filtro."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class FilterSpreadResult:
    """Resultado do filtro de spread."""
    status: FilterStatus
    spread: Optional[float] = None
    spread_ma20: Optional[float] = None
    threshold: Optional[float] = None
    reason: Optional[str] = None


class FilterSpread:
    """Filtro de spread conforme US1.
    
    - Aplica: Ask_t - Bid_t ≤ 2 × média(20)
    - Warm-up < 20 → NEUTRO automático
    - Falha → NEUTRO com motivo
    """
    
    SPREAD_WINDOW = 20
    MULTIPLIER = 2.0
    
    def __init__(self, bars: List, index: int = -1):
        """Inicializa o filtro.
        
        Args:
            bars: Lista de ValidatedBar (do F1)
            index: Índice da barra atual (default: última)
        """
        self.bars = bars
        self.index = index
    
    def _calculate_spreads(self) -> List[float]:
        """Calcula spread para cada barra."""
        spreads = []
        for bar in self.bars:
            # bar é ValidatedBar com bid, ask
            spread = bar.ask - bar.bid
            spreads.append(spread)
        return spreads
    
    def _calculate_ma20(self, values: List[float]) -> float:
        """Calcula média móvel de 20 valores."""
        if len(values) < self.SPREAD_WINDOW:
            return 0.0
        window = values[-self.SPREAD_WINDOW:]
        return sum(window) / len(window)
    
    def run(self) -> FilterSpreadResult:
        """Executa o filtro de spread.
        
        Returns:
            FilterSpreadResult com status, valores e motivos
        """
        n = len(self.bars)
        
        # Warm-up check: precisamos de pelo menos 20 barras para calcular média
        if n < self.SPREAD_WINDOW:
            return FilterSpreadResult(
                status=FilterStatus.NEUTRO,
                reason="warm_up_infeasible"
            )
        
        # Calcula spreads
        spreads = self._calculate_spreads()
        current_spread = spreads[self.index]
        ma20 = self._calculate_ma20(spreads)
        
        threshold = self.MULTIPLIER * ma20
        
        if current_spread <= threshold:
            return FilterSpreadResult(
                status=FilterStatus.PASS,
                spread=current_spread,
                spread_ma20=ma20,
                threshold=threshold
            )
        else:
            return FilterSpreadResult(
                status=FilterStatus.NEUTRO,
                spread=current_spread,
                spread_ma20=ma20,
                threshold=threshold,
                reason="spread_above_threshold"
            )