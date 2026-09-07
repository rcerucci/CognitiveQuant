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
    
    def _calculate_tr_series(self) -> List[tuple]:
        """Calcula TR para todas as barras, excluindo weekend_fill.

        Retorna lista de (tr_value, orig_index) para mapear o índice original.
        """
        tr_values = []
        prev_close = None

        for i, bar in enumerate(self.bars):
            # weekend_fill NÃO conta como TR observado
            if self._is_weekend_fill(bar):
                prev_close = bar.close  # Atualizar prev_close mas não calcular TR
                continue

            tr = self._calculate_TR(bar, prev_close)
            tr_values.append((tr, i))
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

        # Resolve o índice original → índice na série sem weekend_fill.
        # Nunca IndexError: se o índice original não for encontrado
        # (ex.: weekend_fill na posição target), usa o último TR válido.
        if self.index < 0:
            # default: última barra válida
            current_tr = tr_series[-1][0]
        else:
            mapped = None
            for tr_val, orig_idx in tr_series:
                if orig_idx == self.index:
                    mapped = tr_val
                    break
            if mapped is None:
                # A barra actual é weekend_fill ou não tem TR;
                # usa o último TR calculado (barra mais recente com TR)
                current_tr = tr_series[-1][0]
            else:
                current_tr = mapped
        
        # Calcula média móvel de 20 TRs
        window_trs = [t[0] for t in tr_series[-self.TR_WINDOW:]]
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