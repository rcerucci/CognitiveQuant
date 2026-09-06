"""Filtro ADF de estacionariedade (US2).

Filtro que exige ADF com p < 0.05 na janela de retornos r_{t-199:t} (lags=5).
Adicionado addendum 2026-09-06: ADF em r_t (não em X_t).

Spec: §3.3 / US2 / Addendum ADF r_t
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

from statsmodels.tsa.stattools import adfuller


class FilterStatus(str, Enum):
    """Status do resultado do filtro."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class FilterADFResult:
    """Resultado do filtro ADF."""
    status: FilterStatus
    p_value: Optional[float] = None
    threshold: Optional[float] = None
    reason: Optional[str] = None
    lag: int = 5
    window: int = 200  # r_{t-199:t} = 200 pontos


class FilterADF:
    """Filtro ADF de estacionariedade conforme US2 (addendum 2026-09-06).
    
    - Aplica: ADF em r_{t-199:t} com lags=5
    - Condição de passagem: p < 0.05
    - Warm-up < 200 → NEUTRO automático
    - Falha → NEUTRO com motivo
    - Sem r na 1ª barra → NEUTRO/skip
    """
    
    def __init__(self, r_t: List[float], window: int = 200, lag: int = 5, threshold: float = 0.05):
        """Inicializa o filtro.
        
        Args:
            r_t: Série de retornos (r_t = X_t - X_{t-1})
            window: Janela para ADF (default: 200)
            lag: Número de lags no teste ADF (default: 5)
            threshold: Threshold p-value para passagem (default: 0.05)
        """
        self.r_t = r_t
        self.window = window
        self.lag = lag
        self.threshold = threshold
    
    def run(self) -> FilterADFResult:
        """Executa o filtro ADF.
        
        Returns:
            FilterADFResult com status, p-value e motivos
        """
        n = len(self.r_t)
        
        # Warm-up check: precisamos de pelo menos 200 pontos de retorno
        if n < self.window:
            return FilterADFResult(
                status=FilterStatus.NEUTRO,
                reason="warm_up_infeasible",
                lag=self.lag,
                window=self.window
            )
        
        # Obter a janela r_{t-199:t} (últimos 200 pontos)
        r_window = self.r_t[-self.window:]
        
        # Verifica se temos retornos válidos (não None)
        if not r_window or r_window[-1] is None:
            return FilterADFResult(
                status=FilterStatus.NEUTRO,
                reason="no_return_available",
                lag=self.lag,
                window=self.window
            )
        
        try:
            # Executar teste ADF
            # O parameter maxlag especifica o número máximo de lags
            result = adfuller(r_window, maxlag=self.lag)
            p_value = result[1]
            
            if p_value < self.threshold:
                return FilterADFResult(
                    status=FilterStatus.PASS,
                    p_value=p_value,
                    threshold=self.threshold,
                    lag=self.lag,
                    window=self.window
                )
            else:
                return FilterADFResult(
                    status=FilterStatus.NEUTRO,
                    p_value=p_value,
                    threshold=self.threshold,
                    reason="p_value_above_threshold",
                    lag=self.lag,
                    window=self.window
                )
        except Exception as e:
            return FilterADFResult(
                status=FilterStatus.NEUTRO,
                reason=f"adf_error: {str(e)}",
                lag=self.lag,
                window=self.window
            )