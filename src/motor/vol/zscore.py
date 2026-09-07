"""Z-score condicional cálculo.

Z_t = r_t / σ_t^GARCH

Input: r_t (log-return), σ_t (garch ou fallback)
Output: Z_t (float)

Reference: Espec F4 §3.7a
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional
from dataclasses import dataclass


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


def calculate_zscore(r_t: float, sigma_t: float) -> ZScoreResult:
    """Calcula Z-score condicional.

    Args:
        r_t: Log-retorno atual (log(P_t/P_{t-1}))
        sigma_t: Volatilidade (garch ou fallback)

    Returns:
        ZScoreResult com Z_t = r_t / σ_t

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

    # Check for valid r_t (None or non-finite)
    if r_t is None or not math.isfinite(r_t):
        return ZScoreResult(
            status=ZScoreStatus.NEUTRO,
            reason="invalid_r_t_not_finite",
        )

    # Calculate Z-score: Z_t = r_t / sigma_t
    z_t = r_t / sigma_t

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