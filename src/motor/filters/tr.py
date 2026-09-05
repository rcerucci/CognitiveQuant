"""Filtro TR anômalo (US3).

Filtro que rejeita quando True Range excede 2.5× a média de 20 barras.

Spec: §3.3 / US3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


class FilterStatus(str, Enum):
    """Status do resultado do filtro."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class FilterTRResult:
    """Resultado do filtro TR."""
    status: FilterStatus
    TR: Optional[float] = None
    TR_ma20: Optional[float] = None
    threshold: Optional[float] = None
    reason: Optional[str] = None


class FilterTR:
    """Filtro TR conforme US3.
    
    - Aplica: TR_t = max(H-L, |H-C_{t-1}|, |L-C_{t-1}|) e TR_t ≤ 2.5 × média(20)
    - weekend_fill do F1: NÃO conta como TR observado
    - Warm-up < 20 → NEUTRO automático
    - Falha → NEUTRO com motivo
    """
    
    TR_WINDOW = 20
    MULTIPLIER = 2.5
    
    def __init__(self, bars: List, index: int = -1):
        """Inicializa o filtro.
        
        Args:
            bars: Lista de ValidatedBar (do F1)
            index: Índice da barra atual (default: última)
        """
        self.bars = bars
        self.index = index
    
    def _is_weekend_fill(self, bar) -> bool:
        """Verifica se a barra é um weekend_fill."""
        return "weekend_fill" in bar.flags if bar.flags else False
    
    def _calculate_TR(self, bar, prev_close: Optional[float]) -> float:
        """Calcula o True Range de uma barra.
        
        TR_t = max(H-L, |H-C_{t-1}|, |L-C_{t-1}|)
        """
        H = bar.high
        L = bar.low
        C = bar.close
        
        range_hl = H - L
        range_hc = abs(H - prev_close) if prev_close is not None else range_hl
        range_lc = abs(L - prev_close) if prev_close is not None else range_hl
        
        return max(range_hl, range_hc, range_lc)
    
    def _calculate_tr_series(self) -> List[float]:
        """Calcula TR para todas as barras, excluindo weekend_fill."""
        tr_values = []
        prev_close = None
        
        for bar in self.bars:
            # weekend_fill NÃO conta como TR observado
            if self._is_weekend_fill(bar):
                prev_close = bar.close  # Atualizar prev_close mas não calcular TR
                continue
            
            tr = self._calculate_TR(bar, prev_close)
            tr_values.append(tr)
            prev_close = bar.close
        
        return tr_values
    
    def run(self) -> FilterTRResult:
        """Executa o filtro TR.
        
        Returns:
            FilterTRResult com status, valores e motivos
        """
        n = len(self.bars)
        
        # Warm-up check: precisamos de pelo menos 20 barras de TR
        tr_series = self._calculate_tr_series()
        if len(tr_series) < self.TR_WINDOW:
            return FilterTRResult(
                status=FilterStatus.NEUTRO,
                reason="warm_up_infeasible"
            )
        
        # Calcula TR da barra atual (índice -1)
        # Precisamos recalcula porque pode ter sido weekend_fill
        current_tr = tr_series[self.index]
        
        # Calcula média móvel de 20 TRs
        window_trs = tr_series[-self.TR_WINDOW:]
        tr_ma20 = sum(window_trs) / len(window_trs)
        
        threshold = self.MULTIPLIER * tr_ma20
        
        if current_tr <= threshold:
            return FilterTRResult(
                status=FilterStatus.PASS,
                TR=current_tr,
                TR_ma20=tr_ma20,
                threshold=threshold
            )
        else:
            return FilterTRResult(
                status=FilterStatus.NEUTRO,
                TR=current_tr,
                TR_ma20=tr_ma20,
                threshold=threshold,
                reason="tr_above_threshold"
            )