"""Percentil empírico de |Z|.

P_t = percentileofscore(|Z_t|, 200, method='mean')

Reference: Espec F4 §3.7b, lock Marcos: método 'mean'
"""

from __future__ import annotations

import math
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
import numpy as np
from scipy.stats import percentileofscore


class PercentilStatus(str, Enum):
    """Status do resultado percentil."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class PercentilResult:
    """Resultado do cálculo do percentil."""
    status: PercentilStatus
    percentil_z: Optional[float] = None  # P_t ∈ [0, 1]
    reason: Optional[str] = None


def calculate_percentil_z(z_value: float, z_history: List[float], window_size: int = 200) -> PercentilResult:
    """Calcula percentil empírico de |Z|.
    
    Args:
        z_value: Valor Z atual (Z_t)
        z_history: Histórico de |Z| (janela 200)
        window_size: Tamanho da janela (default 200)
        
    Returns:
        PercentilResult com P_t = percentileofscore(|Z|, 200, method='mean')
        
    Note:
        P_t ∈ [0, 1]; P_t alto não causa NEUTRO (não é filtro)
    """
    # Check for valid z_value
    if z_value is None or not math.isfinite(z_value):
        return PercentilResult(
            status=PercentilStatus.NEUTRO,
            reason="invalid_z_value",
        )
    
    # Check for valid history
    if not z_history or len(z_history) == 0:
        return PercentilResult(
            status=PercentilStatus.NEUTRO,
            reason="empty_history",
        )
    
    # Take absolute value of Z
    abs_z = abs(z_value)
    
    # Convert history to absolute values if needed (should be |Z| history)
    abs_z_history = [abs(z) for z in z_history]
    
    # Use percentileofscore with method='mean' (lock Marcos)
    # In scipy 1.17+, the parameter is 'kind'
    try:
        p_t = percentileofscore(abs_z_history, abs_z, kind='mean')
        
        # percentileofscore returns 0-100, convert to 0-1
        p_t_normalized = p_t / 100.0
        
        # Ensure P_t is in [0, 1]
        if not (0 <= p_t_normalized <= 1):
            return PercentilResult(
                status=PercentilStatus.NEUTRO,
                reason="percentil_out_of_range",
            )
        
        if not math.isfinite(p_t_normalized):
            return PercentilResult(
                status=PercentilStatus.NEUTRO,
                reason="percentil_not_finite",
            )
        
        return PercentilResult(
            status=PercentilStatus.PASS,
            percentil_z=p_t_normalized,
        )
        
    except Exception as e:
        return PercentilResult(
            status=PercentilStatus.NEUTRO,
            reason=f"percentil_error: {str(e)}",
        )