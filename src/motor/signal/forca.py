"""Direção e força do sinal (US2).

Implementa:
- Direção: LONG (Z_t < 0) / SHORT (Z_t > 0) / NEUTRO
- Força bruta: 0.35×P_t + 0.25×max(ρ₁,0) + 0.25×|CLV| + 0.15×RB
- Penalizações: skew → CV_θ → ACF (ρ₁ < 0)
- Piso: 0.18
- Round: 2 casas decimais

Reference: Espec F5 §3.10, US2
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List
from dataclasses import dataclass, field


class Direction(str, Enum):
    """Direção do sinal."""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRO = "NEUTRO"


class Confidence(str, Enum):
    """Nível de confiança (será classificado por thresholds)."""
    ALTA = "ALTA"
    MEDIA = "MÉDIA"
    NEUTRO = "NEUTRO"


class ForcaStatus(str, Enum):
    """Status do cálculo de força."""
    CALCULADA = "CALCULADA"
    NEUTRO = "NEUTRO"


@dataclass
class ForcaResult:
    """Resultado do cálculo de força."""
    status: ForcaStatus
    direction: Direction
    forca: float  # Em [0, 1] após penalizações
    forca_bruta: Optional[float] = None  # Antes das penalizações
    penalizacoes_aplicadas: List[str] = field(default_factory=list)
    rho_1: Optional[float] = None
    cv_theta: Optional[float] = None
    skewness: Optional[float] = None
    reason: Optional[str] = None


def calcular_forca(
    z_t: Optional[float],
    percentil_z: Optional[float],  # P_t
    rho_1: Optional[float],
    clv: Optional[float],
    rb: Optional[float],
    skewness: Optional[float],
    cv_theta: Optional[float],
    forca_penalty_cv: bool = False,
    seed: int = 42,
) -> ForcaResult:
    """Calcula força e direção do sinal.
    
    Fórmula da força bruta:
        Força = 0.35×P_t + 0.25×max(ρ₁,0) + 0.25×|CLV| + 0.15×RB
    
    Penalizações (ordem):
        1. |Skewness| suave (1 < |S| < 2): ×0.70
        2. CV_θ > 0.30: ×0.80
        3. ρ₁ < 0 (reversão): ×0.70
    
    Args:
        z_t: Z-score condicional
        percentil_z: Percentil de Z (|Z|)
        rho_1: ACF(1)
        clv: Chandelier Exit Value
        rb: Relative Balance
        skewness: Skewness da distribuição
        cv_theta: Coefficient of variation de θ
        forca_penalty_cv: Flag de penalização CV do F3
        seed: Seed para reprodutibilidade
        
    Returns:
        ForcaResult com direção, força e penalizações
    """
    import numpy as np
    np.random.seed(seed)
    
    # Determinar direção
    if z_t is not None:
        if z_t < 0:
            direction = Direction.LONG
        elif z_t > 0:
            direction = Direction.SHORT
        else:
            direction = Direction.NEUTRO
    else:
        direction = Direction.NEUTRO
    
    # Calcular força bruta
    # max(ρ₁, 0) - ACF negativo não conta no termo positivo (penaliza depois)
    if clv is None:
        clv = 0.0
    if rb is None:
        rb = 0.0
    if percentil_z is None:
        percentil_z = 0.0
    
    rho_1_positive = max(rho_1, 0) if rho_1 is not None else 0.0
    
    forca_bruta = (
        0.35 * percentil_z +
        0.25 * rho_1_positive +
        0.25 * abs(clv) +
        0.15 * rb
    )
    
    # Aplicar penalizações
    penalizacoes = []
    forca = forca_bruta
    
    # 1. Penalização de skewness (1 < |S| < 2) → ×0.70
    if skewness is not None:
        if 1.0 < abs(skewness) < 2.0:
            forca *= 0.70
            penalizacoes.append("skewness")
    
    # 2. Penalização CV_θ > 0.30 → ×0.80
    # Nota: forca_penalty_cv é SINÓNIMO de cv_theta > 0.30 (FR-007 F3)
    # Apenas uma penalização ×0.80, não duas
    cv_alto_aplicado = False
    if cv_theta is not None and cv_theta > 0.30:
        forca *= 0.80
        penalizacoes.append("cv_theta")
        cv_alto_aplicado = True
    elif forca_penalty_cv:
        # Flag estabilizado mas CV não foi passado como valor > 0.30
        # Ainda assim aplicar penalização
        forca *= 0.80
        penalizacoes.append("cv_theta")
    
    # 4. Penalização ACF negativo (reversão) → ×0.70
    if rho_1 is not None and rho_1 < 0:
        forca *= 0.70
        penalizacoes.append("acf_neg")
    
    # Aplicar piso 0.18
    forca = max(forca, 0.18)
    
    # Arredondar para 2 casas decimais
    forca = round(forca, 2)
    
    return ForcaResult(
        status=ForcaStatus.CALCULADA,
        direction=direction,
        forca=forca,
        forca_bruta=forca_bruta,
        penalizacoes_aplicadas=penalizacoes,
        rho_1=rho_1,
        cv_theta=cv_theta,
        skewness=skewness,
        reason=f"Força calculada e penalizada para {direction.value}",
    )