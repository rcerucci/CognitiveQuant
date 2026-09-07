"""Confirmações de reversão (8.1-8.6) - US1.

Implementa:
- 8.1: ACF(1) - soft gate (penalização força se ρ₁ < 0)
- 8.2: Ljung-Box (k=5) - soft gate (penaliza força se p >= 0.05)
- 8.3: CLV (> 0.30) - hard gate
- 8.4: RB (> 0.50 + direção) - hard gate
- 8.5: Shadow > 0.50 (lower p/ LONG, upper p/ SHORT) - hard gate
- 8.6: Skewness extrema (S < -2 ou S > +2) - abort → NEUTRO
- High=Low → NEUTRO (CLV/RB/shadow indefinidos)

Reference: Espec F5 US1, §1.5 (CLV, RB, US, LS)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import numpy as np
from scipy import stats


class ConfirmacaoStatus(str, Enum):
    """Status da confirmação."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


class ConfirmacaoDirection(str, Enum):
    """Direção esperada pela confirmação."""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class ConfirmacaoMetrics:
    """Métricas de confirmação calculadas."""
    rho_1: Optional[float] = None  # ACF(1)
    lb_pvalue: Optional[float] = None  # Ljung-Box p-value
    clv: Optional[float] = None
    rb: Optional[float] = None
    us: Optional[float] = None  # Ums (Chandelier?)
    ls: Optional[float] = None  # Ls
    skewness: Optional[float] = None
    lower_shadow: Optional[float] = None
    upper_shadow: Optional[float] = None
    high_equals_low: bool = False
    # Flags para soft gates (penalizações de força)
    lb_soft_gate: bool = False  # p >= 0.05 → penaliza força ×0.70


@dataclass
class ConfirmacaoResult:
    """Resultado da confirmação."""
    status: ConfirmacaoStatus
    direction: Optional[ConfirmacaoDirection] = None
    metrics: ConfirmacaoMetrics = field(default_factory=ConfirmacaoMetrics)
    reason: Optional[str] = None
    filters_passed: List[str] = field(default_factory=list)


def calculate_acf(series: List[float], lag: int = 1) -> Optional[float]:
    """Calcula ACF(1) de uma série temporal.

    Args:
        series: Série temporal (retornos)
        lag: Lag desejado (padrão: 1)

    Returns:
        Valor ACF ou None se não calculável
    """
    if len(series) < 2:
        return None

    x = np.array(series)
    n = len(x)
    mean = np.mean(x)
    var = np.var(x, ddof=0)

    if var == 0:
        return 0.0

    # ACF(1)
    cov = np.sum((x[:-1] - mean) * (x[1:] - mean)) / n
    return cov / var


def calculate_ljung_box(series: List[float], k: int = 5) -> Optional[float]:
    """Calcula p-value do teste Ljung-Box.

    Args:
        series: Série temporal (resíduos)
        k: Número de lag a testar

    Returns:
        p-value ou None se não calculável
    """
    if len(series) < k + 1:
        return None

    x = np.array(series)
    n = len(x)

    # Calcular autocorrelações
    mean = np.mean(x)
    var = np.var(x, ddof=0)

    if var == 0:
        return 1.0  # Série constante, não há autocorrelação

    # ACF para lags 1 a k
    acf_vars = []
    for lag in range(1, k + 1):
        if n - lag < 1:
            break
        cov = np.sum((x[:(n-lag)] - mean) * (x[lag:] - mean)) / n
        acf_vars.append(cov / var)

    if len(acf_vars) == 0:
        return None

    # Estatística Q
    Q = n * (n + 2) * sum(a**2 / (n - i) for i, a in enumerate(acf_vars, 1))

    # p-value chi-quadrado com k graus de liberdade
    pvalue = 1 - stats.chi2.cdf(Q, k)
    return max(0.0, min(1.0, pvalue))


def calculate_clv(open: float, high: float, low: float, close: float) -> Optional[float]:
    """Calcula Chandelier Exit Value (CLV).

    Fórmula: 2 * (C - L) / (H - L) - 1 = (C - L) / ((H - L) / 2)
    Quando H = L, retorna None

    Args:
        open, high, low, close: Valores OHLC

    Returns:
        CLV normalizado ou None
    """
    if high == low:
        return None

    clv = (close - low) / (high - low)
    return clv


def calculate_rb(open: float, high: float, low: float, close: float) -> Optional[float]:
    """Calcula Relative Balance (RB).

    Fórmula: |Close - Open| / (High - Low)
    Quando H = L, retorna None

    Args:
        open, high, low, close: Valores OHLC

    Returns:
        RB ou None
    """
    if high == low:
        return None

    rb = abs(close - open) / (high - low)
    return rb


def calculate_us_ls(
    open: float, high: float, low: float, close: float, direction: str
) -> tuple[Optional[float], Optional[float]]:
    """Calcula US (Ums) e LS (Ls) conforme §1.5.

    Args:
        open, high, low, close: Valores OHLC
        direction: Direção esperada (LONG ou SHORT)

    Returns:
        (US, LS) - True Range e something else?
    """
    if high == low:
        return None, None

    # US = Upper Shadow, LS = Lower Shadow
    if direction == "LONG":
        us = (high - close) / (high - low) if (high - low) > 0 else 0.0
        ls = (close - low) / (high - low) if (high - low) > 0 else 0.0
    else:  # SHORT
        us = (high - open) / (high - low) if (high - low) > 0 else 0.0
        ls = (low - close) / (high - low) if (high - low) > 0 else 0.0

    return us, ls


def calculate_skewness(returns: List[float]) -> Optional[float]:
    """Calcula skewness da distribuição de retornos.

    Args:
        returns: Lista de retornos

    Returns:
        Skewness ou None
    """
    if len(returns) < 3:
        return None

    return stats.skew(returns)


def calculate_shadows(
    open: float, high: float, low: float, close: float
) -> tuple[Optional[float], Optional[float]]:
    """Calcula lower e upper shadow como proporção do ganho/perda.

    Args:
        open, high, low, close: Valores OHLC

    Returns:
        (lower_shadow, upper_shadow) como proporção
    """
    if high == low:
        return None, None

    body = abs(close - open)
    lower_shadow = (min(open, close) - low) / (high - low)
    upper_shadow = (high - max(open, close)) / (high - low)

    return lower_shadow, upper_shadow


def _format_optional_float(value: Optional[float], name: str) -> str:
    """Formata um valor opcional de float para string."""
    if value is None:
        return f"{name}=None"
    return f"{name}={value:.4f}"


def calculate_confirmacao(
    returns: List[float],
    bar: List[float],  # [timestamp, open, high, low, close, bid, ask]
    direction: str,
    seed: int = 42,
) -> ConfirmacaoResult:
    """Calcula todas as confirmações 8.1-8.6.

    Args:
        returns: Série de retornos
        bar: Barra OHLC [timestamp, open, high, low, close, bid, ask]
        direction: Direção esperada (LONG ou SHORT)
        seed: Seed para reprodutibilidade

    Returns:
        ConfirmacaoResult com status e métricas

    Note:
        - 8.1 (ACF) e 8.2 (Ljung-Box) são soft gates → penalizam força, não bloqueiam
        - 8.3 (CLV), 8.4 (RB), 8.5 (Shadow) são hard gates → bloqueiam se falhar
        - 8.6 (Skewness extrema) é abort → NEUTRO
    """
    np.random.seed(seed)

    metrics = ConfirmacaoMetrics()
    filters_passed = []

    # Verificar High=Low primeiro (edge case que afeta CLV/RB/shadow)
    if len(bar) >= 6:
        high = bar[2]
        low = bar[3]
        if high == low:
            metrics.high_equals_low = True
            return ConfirmacaoResult(
                status=ConfirmacaoStatus.NEUTRO,
                reason="High equals Low - CLV/RB/shadow undefined",
                metrics=metrics,
                filters_passed=[],
            )

    # 8.1: ACF(1) - soft gate (penaliza força se ρ₁ < 0)
    rho_1 = calculate_acf(returns, lag=1)
    metrics.rho_1 = rho_1

    # 8.6: Skewness extrema - abort → NEUTRO (hard abort)
    skewness = calculate_skewness(returns)
    metrics.skewness = skewness

    if skewness is not None:
        if (direction == "LONG" and skewness < -2.0) or (direction == "SHORT" and skewness > 2.0):
            return ConfirmacaoResult(
                status=ConfirmacaoStatus.NEUTRO,
                direction=None,
                metrics=metrics,
                reason=f"Skewness extrema: {skewness:.2f} → NEUTRO (8.6)",
                filters_passed=["8.6_abort"],
            )

    # 8.2: Ljung-Box k=5 - soft gate (penaliza força se p >= 0.05, não bloqueia)
    lb_pvalue = calculate_ljung_box(returns, k=5)
    metrics.lb_pvalue = lb_pvalue

    if lb_pvalue is not None and lb_pvalue >= 0.05:
        # Soft gate: marca para penalização, não bloqueia
        metrics.lb_soft_gate = True
    filters_passed.append("8.2_lb")

    # 8.3: CLV > 0.30 - hard gate
    if len(bar) >= 6:
        open_p, high_p, low_p, close_p = bar[1], bar[2], bar[3], bar[4]
        clv = calculate_clv(open_p, high_p, low_p, close_p)
        metrics.clv = clv

        if clv is None or abs(clv) <= 0.30:
            clv_str = f"{clv:.4f}" if clv is not None else "None"
            return ConfirmacaoResult(
                status=ConfirmacaoStatus.NEUTRO,
                direction=None,
                metrics=metrics,
                reason=f"CLV <= 0.30: {clv_str} (8.3)",
                filters_passed=filters_passed,
            )
        filters_passed.append("8.3_clv")

    # 8.4: RB > 0.50 + direção alinhada - hard gate
    if len(bar) >= 6:
        open_p, high_p, low_p, close_p = bar[1], bar[2], bar[3], bar[4]
        rb = calculate_rb(open_p, high_p, low_p, close_p)
        metrics.rb = rb

        # Verificar direção alinhada
        direction_aligned = False
        if direction == "LONG":
            direction_aligned = close_p > open_p
        else:  # SHORT
            direction_aligned = close_p < open_p

        if rb is None or rb <= 0.50 or not direction_aligned:
            rb_str = f"{rb:.4f}" if rb is not None else "None"
            return ConfirmacaoResult(
                status=ConfirmacaoStatus.NEUTRO,
                direction=None,
                metrics=metrics,
                reason=f"RB <= 0.50 ou direção não alinhada: RB={rb_str} (8.4)",
                filters_passed=filters_passed,
            )
        filters_passed.append("8.4_rb")

    # 8.5: Shadow oposto ao desvio > 0.50 - hard gate
    if len(bar) >= 6:
        open_p, high_p, low_p, close_p = bar[1], bar[2], bar[3], bar[4]
        lower_shadow, upper_shadow = calculate_shadows(open_p, high_p, low_p, close_p)
        metrics.lower_shadow = lower_shadow
        metrics.upper_shadow = upper_shadow

        shadow_ok = False
        if direction == "LONG":
            # Shadow inferior oposto ao desvio
            shadow_ok = lower_shadow is not None and lower_shadow > 0.50
        else:  # SHORT
            # Shadow superior oposto ao desvio
            shadow_ok = upper_shadow is not None and upper_shadow > 0.50

        if not shadow_ok:
            lower_str = f"{lower_shadow:.4f}" if lower_shadow is not None else "None"
            upper_str = f"{upper_shadow:.4f}" if upper_shadow is not None else "None"
            return ConfirmacaoResult(
                status=ConfirmacaoStatus.NEUTRO,
                direction=None,
                metrics=metrics,
                reason=f"Shadow não satisfeito: lower={lower_str}, upper={upper_str} (8.5)",
                filters_passed=filters_passed,
            )
        filters_passed.append("8.5_shadow")

    # Todas as confirmações hard gates passaram
    return ConfirmacaoResult(
        status=ConfirmacaoStatus.PASS,
        direction=ConfirmacaoDirection(direction),
        metrics=metrics,
        reason="Todas as confirmações (8.2-8.5) satisfeitas",
        filters_passed=filters_passed,
    )