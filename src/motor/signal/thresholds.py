"""Classificação de confiança (US3).

Implementa:
- ALTA: força >= 0.75
- MÉDIA: 0.60 <= força < 0.75
- NEUTRO: força < 0.60

Reference: Espec F5 US3, limiares fixos 0.75/0.60
"""

from __future__ import annotations

from enum import Enum
from typing import Optional


class ConfidenceLevel(str, Enum):
    """Nível de confiança do sinal."""
    ALTA = "ALTA"
    MEDIA = "MÉDIA"
    NEUTRO = "NEUTRO"


def classificar_confianca(forca: float) -> ConfidenceLevel:
    """Classifica a força em nível de confiança.
    
    Args:
        forca: Força do sinal (0 a 1)
        
    Returns:
        ConfidenceLevel: ALTA, MÉDIA ou NEUTRO
        
    Regras (limiares fixos):
        - força >= 0.75 → ALTA
        - 0.60 <= força < 0.75 → MÉDIA
        - força < 0.60 → NEUTRO
    """
    if forca >= 0.75:
        return ConfidenceLevel.ALTA
    elif forca >= 0.60:
        return ConfidenceLevel.MEDIA
    else:
        return ConfidenceLevel.NEUTRO


def get_threshold_bounds() -> dict:
    """Retorna os limites de threshold fixos.
    
    Returns:
        dict com 'alta' e 'media' thresholds
    """
    return {
        "alta": 0.75,
        "media": 0.60,
    }