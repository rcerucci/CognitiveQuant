"""Z-score condicional cálculo.

Z_t = (X_t - μ_t) / σ_t^GARCH

Input: X_t (log-price), μ_t (F3), σ_t (garch ou fallback)
Output: Z_t (float)

Reference: Espec F4 §3.7a
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import numpy as np


class ZScoreStatus(str, Enum):
    """Status do resultado Z-score."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class ZScoreResult:
    """Resultado do cálculo de Z-score."""
    status: ZScoreStatus
    z_t: Optional[float] = None
    reason: Optional[str] = None


def calculate_zscore(X_t: float, mu_t: float, sigma_t: float) -> ZScoreResult:
    """Calcula Z-score condicional.
    
    Args:
        X_t: Preço/log-preço atual
        mu_t: Média condicional (F3)
        sigma_t: Volatilidade (garch ou fallback)
        
    Returns:
        ZScoreResult com Z_t = (X_t - μ_t) / σ_t
        
    Note:
        Se σ_t ≤ 0 ou não-finito → NEUTRO (lock Marcos)
    """
    # Check for valid sigma (None, zero, negative, or non-finite)
    if sigma_t is None:
        return ZScoreResult(
            status=ZScoreStatus.NEUTRO,
            reason="invalid_sigma_null",
        )
    
    if sigma_t <= 0:
        return ZScoreResult(
            status=ZScoreStatus.NEUTRO,
            reason="invalid_sigma_non_positive",
        )
    
    if not math.isfinite(sigma_t):
        return ZScoreResult(
            status=ZScoreStatus.NEUTRO,
            reason="invalid_sigma_not_finite",
        )
    
    # Check for valid mu (None or non-finite)
    if mu_t is None or not math.isfinite(mu_t):
        return ZScoreResult(
            status=ZScoreStatus.NEUTRO,
            reason="invalid_mu_not_finite",
        )
    
    # Check for valid X (None or non-finite)
    if X_t is None or not math.isfinite(X_t):
        return ZScoreResult(
            status=ZScoreStatus.NEUTRO,
            reason="invalid_X_t_not_finite",
        )
    
    # Calculate Z-score
    z_t = (X_t - mu_t) / sigma_t
    
    # Check for valid result
    if not math.isfinite(z_t):
        return ZScoreResult(
            status=ZScoreStatus.NEUTRO,
            reason="z_non_finite",
        )
    
    return ZScoreResult(
        status=ZScoreStatus.PASS,
        z_t=z_t,
    )