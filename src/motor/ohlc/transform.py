"""Transformação OHLC → mid → log → retorno conforme especificação F1.

Módulo responsável por:
- Calcular P_t = (Bid_t + Ask_t) / 2 (mid-price)
- Calcular X_t = ln(P_t) (log-price)
- Calcular r_t = X_t - X_{t-1} (log-return)

Saída in-memory conforme spec.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from motor.ohlc.validation import ValidatedSeries, ValidatedBar


@dataclass
class TransformResult:
    """Resultado da transformação mid → log → retorno."""
    timestamps: list[int]
    P_t: list[float]  # Mid-price
    X_t: list[float]  # Log-price
    r_t: list[float]  # Log-returns (exclui primeiro elemento)
    
    @property
    def count(self) -> int:
        """Número de pontos na série transformada."""
        return len(self.timestamps)
    
    @property
    def return_count(self) -> int:
        """Número de retornos calculados (exclui primeiro)."""
        return len(self.r_t)


def calculate_mid_price(bid: float, ask: float) -> float:
    """Calcula o preço médio (mid-price).
    
    P_t = (Bid_t + Ask_t) / 2
    
    Args:
        bid: Preço de compra
        ask: Preço de venda
        
    Returns:
        Mid-price P_t
    """
    return (bid + ask) / 2.0


def calculate_log_price(P_t: float) -> float:
    """Calcula o preço logarítmico.
    
    X_t = ln(P_t)
    
    Args:
        P_t: Mid-price
        
    Returns:
        Log-price X_t
        
    Raises:
        ValueError: Se P_t <= 0 (ln indefinido)
    """
    if P_t <= 0:
        raise ValueError("P_t must be positive for log calculation")
    return math.log(P_t)


def calculate_log_return(X_t: float, X_t_minus_1: float) -> float:
    """Calcula o retorno logarítmico.
    
    r_t = X_t - X_{t-1}
    
    Args:
        X_t: Log-price no tempo t
        X_t_minus_1: Log-price no tempo t-1
        
    Returns:
        Log-return r_t
    """
    return X_t - X_t_minus_1


def transform_to_returns(series: ValidatedSeries) -> TransformResult:
    """Transforma série validada para P_t, X_t, r_t.
    
    Processo:
    1. P_t = (Bid_t + Ask_t) / 2
    2. X_t = ln(P_t)
    3. r_t = X_t - X_{t-1} (para t >= 1)
    
    Args:
        series: Série temporal de barras validadas
        
    Returns:
        TransformResult com timestamps, P_t, X_t, r_t
        
    Raises:
        ValueError: Se P_t <= 0 em qualquer ponto
    """
    if not series.bars:
        return TransformResult(timestamps=[], P_t=[], X_t=[], r_t=[])
    
    timestamps = []
    P_t_list = []
    X_t_list = []
    r_t_list = []
    
    X_t_minus_1 = None
    
    for bar in series.bars:
        # Calcular mid-price
        P_t = calculate_mid_price(bar.bid, bar.ask)
        
        # Verificar se P_t > 0
        if P_t <= 0:
            raise ValueError(f"P_t <= 0 for bar at timestamp {bar.timestamp}")
        
        # Calcular log-price
        X_t = calculate_log_price(P_t)
        
        # Calcular log-return (não para o primeiro barramento)
        r_t = None
        if X_t_minus_1 is not None:
            r_t = calculate_log_return(X_t, X_t_minus_1)
        
        # Armazenar resultados
        timestamps.append(bar.timestamp)
        P_t_list.append(P_t)
        X_t_list.append(X_t)
        
        if r_t is not None:
            r_t_list.append(r_t)
        
        X_t_minus_1 = X_t
    
    return TransformResult(
        timestamps=timestamps,
        P_t=P_t_list,
        X_t=X_t_list,
        r_t=r_t_list
    )


def transform_to_returns_dict(series: ValidatedSeries) -> dict:
    """Transforma série validada para dicionário com P_t, X_t, r_t.
    
    Versão que retorna dict para compatibilidade com API anterior.
    
    Args:
        series: Série temporal de barras validadas
        
    Returns:
        Dicionário com 'valid', 'timestamps', 'P_t', 'X_t', 'r_t'
    """
    result = transform_to_returns(series)
    
    return {
        "valid": True,
        "timestamps": result.timestamps,
        "P_t": result.P_t,
        "X_t": result.X_t,
        "r_t": result.r_t
    }