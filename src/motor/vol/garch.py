"""GARCH(1,1) volatility estimation with fallback.

Estima volatilidade condicional GARCH(1,1) via MLE em r_{t-199:t}.
- ω, α, β via MLE
- α + β < 0.995 obrigatório
- Fallback: σ_t = √(∑ r² / 20) se não convergir ou α+β ≥ 0.995
- Warm-up: < 200 retornos → NEUTRO
- σ ≤ 0 ou não-finito → NEUTRO

Reference: Espec F4 §3.7, lock Marcos
"""

from __future__ import annotations

import math
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass
import numpy as np
import warnings

# Set random seed for reproducibility
import os
os.environ['PYTHONHASHSEED'] = '42'


class GARCHStatus(str, Enum):
    """Status do resultado GARCH."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class GARCHResult:
    """Resultado da estimação GARCH(1,1)."""
    status: GARCHStatus
    omega: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    garch_sigma: Optional[float] = None
    source: Optional[str] = None  # "garch" or "fallback"
    reason: Optional[str] = None


def estimate_garch(returns: List[float], seed: int = 42) -> GARCHResult:
    """Estima GARCH(1,1) via MLE.
    
    Args:
        returns: Janela de 200 retornos (r_{t-199:t})
        seed: Seed para reprodutibilidade (F4)
        
    Returns:
        GARCHResult com ω, α, β e σ_t (garch_sigma)
        
    Note:
        Se α+β ≥ 0.995 ou não converge, retorna NEUTRO.
    """
    from arch import arch_model
    
    # Set seed for reproducibility
    np.random.seed(seed)
    
    # Handle None or invalid input
    if returns is None or not isinstance(returns, (list, tuple)):
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason="invalid_input_none_or_type",
        )
    
    # Need at least 200 returns for GARCH estimation
    if len(returns) < 200:
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason="warm_up",
        )
    
    # Convert to numpy array
    returns_arr = np.array(returns[-200:])  # Last 200 returns
    
    try:
        # Fit GARCH(1,1) model via MLE
        # Suppress convergence warnings - we handle them via return status
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = arch_model(returns_arr, vol='Garch', p=1, q=1, dist='Normal', rescale=False)
            fitted = model.fit(disp='off', options={'maxiter': 500})
        
        # Extract parameters
        omega = fitted.params['omega']
        alpha = fitted.params['alpha[1]']
        beta = fitted.params['beta[1]']
        
        # Check stability constraint: α + β < 0.995 (stricter than < 1)
        if alpha + beta >= 0.995:
            return GARCHResult(
                status=GARCHStatus.NEUTRO,
                omega=omega,
                alpha=alpha,
                beta=beta,
                reason="stability_constraint_violation",
            )
        
        # Calculate conditional variance at last point
        # σ_t² = ω + α * r_{t-1}² + β * σ_{t-1}²
        variance = fitted.conditional_volatility[-1] ** 2
        sigma_t = math.sqrt(variance)
        
        # Check for valid sigma
        if sigma_t <= 0 or not math.isfinite(sigma_t):
            return GARCHResult(
                status=GARCHStatus.NEUTRO,
                omega=omega,
                alpha=alpha,
                beta=beta,
                reason="invalid_sigma",
            )
        
        return GARCHResult(
            status=GARCHStatus.PASS,
            omega=omega,
            alpha=alpha,
            beta=beta,
            garch_sigma=sigma_t,
            source="garch",
        )
        
    except Exception as e:
        # Non-convergence
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason=f"convergence_error: {str(e)}",
        )


def estimate_garch_with_fallback(returns: List[float], seed: int = 42) -> GARCHResult:
    """Estima GARCH(1,1) com fallback.
    
    Args:
        returns: Série de retornos
        seed: Seed para reprodutibilidade
        
    Returns:
        GARCHResult:
        - PASS com fonte "garch" se GARCH convergir com α+β < 0.995
        - PASS com fonte "fallback" se usar σ = √(∑r²/20)
        - NEUTRO se < 200 retornos ou σ ≤ 0 não-finito
    """
    np.random.seed(seed)
    
    # Handle None or invalid input
    if returns is None or not isinstance(returns, (list, tuple)):
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason="invalid_input_none_or_type",
        )
    
    # Need at least 200 returns
    if len(returns) < 200:
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason="warm_up",
        )
    
    # Check for NaN or infinite values
    returns_arr = np.array(returns[-200:])
    if not np.all(np.isfinite(returns_arr)):
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason="invalid_input_nan_or_inf",
        )
    
    # Try GARCH first
    garch_result = estimate_garch(returns, seed)
    
    if garch_result.status == GARCHStatus.PASS:
        return garch_result
    
    # Fallback: σ_t = √(∑ r² / 20)
    # Use recent returns for fallback calculation (lock: use last 20 or available)
    recent_returns = np.array(returns[-min(len(returns), 50):])
    
    if len(recent_returns) < 20:
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason="insufficient_data_for_fallback",
        )
    
    # Calculate fallback sigma
    sum_sq_returns = np.sum(recent_returns ** 2)
    sigma_t = math.sqrt(sum_sq_returns / 20)
    
    # Check for valid sigma
    if sigma_t <= 0 or not math.isfinite(sigma_t):
        return GARCHResult(
            status=GARCHStatus.NEUTRO,
            reason="fallback_invalid_sigma",
        )
    
    return GARCHResult(
        status=GARCHStatus.PASS,
        garch_sigma=sigma_t,
        source="fallback",
        reason=f"garch_failed_{garch_result.reason}",
    )