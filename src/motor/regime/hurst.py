"""Cálculo do coeficiente de Hurst via R/S (Regime F3).

Implementa Hurst R/S com janela 200 e sub-tamanhos 8/16/32/64/128
para classificação de regime conforme spec §3.4.

T027 (hotfix 003b): Hurst via DFA Peng em X_t como diagnóstico.
- H é apenas métrica de contexto, NÃO é hard-gate de PASS/NEUTRO
- H > 0.55 NÃO gera tendência
- Se hurst estiver None (warm-up < 200), continua para OU/bootstrap

Largos (R/S pre-003b - mantidos para referência):
- H < 0.45 → REVERSÃO
- 0.45 ≤ H ≤ 0.55 → NEUTRO
- H > 0.55 → NEUTRO

Nota: O gate de PASS agora é: θ̂>0 ∧ IC_low>0 ∧ τ≤20 (T030)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import numpy as np


class RegimeType(str, Enum):
    """Tipo de regime classificado pelo Hurst."""
    REVERSAL = "REVERSAL"
    NEUTRAL = "NEUTRO"


class HurstStatus(str, Enum):
    """Status do cálculo do Hurst."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class HurstResult:
    """Resultado do cálculo do Hurst R/S.
    
    T027: H é diagnóstico, não hard-gate de PASS/NEUTRO.
    O status PASS apenas indica que H foi calculado com sucesso
    e o regime foi classificado (REVERSAL ou NEUTRO).
    """
    status: HurstStatus
    hurst: Optional[float] = None
    regime: Optional[RegimeType] = None
    window_size: int = 200
    sub_sizes: List[int] = None
    
    def __post_init__(self):
        if self.sub_sizes is None:
            self.sub_sizes = [8, 16, 32, 64, 128]


class HurstCalculator:
    """Calculadora de Hurst R/S."""
    
    WINDOW_SIZE = 200
    SUB_SIZES = [8, 16, 32, 64, 128]
    H_REVERSAL = 0.45
    H_TREND = 0.55
    
    def __init__(self, series: List[float], window_size: int = None, sub_sizes: List[int] = None):
        """Inicializa o calculador.
        
        Args:
            series: Série de preços X_t (log-price)
            window_size: Tamanho da janela (default 200)
            sub_sizes: Sub-tamanhos para cálculo R/S
        """
        self.series = np.array(series, dtype=np.float64)
        self.window_size = window_size or self.WINDOW_SIZE
        self.sub_sizes = sub_sizes or self.SUB_SIZES
    
    def _rescaled_range(self, data: np.ndarray, sub_size: int) -> float:
        """Calcula o R/S para um sub-tamanho.
        
        Args:
            data: Dados de entrada
            sub_size: Tamanho do sub-janela
            
        Returns:
            R/S value normalizado
        """
        if sub_size >= len(data):
            sub_size = len(data) - 1
        
        if sub_size < 2:
            return 1.0
        
        # Dividir em blocos do tamanho sub_size
        n_blocks = len(data) // sub_size
        if n_blocks == 0:
            return 1.0
        
        rs_values = []
        
        for i in range(n_blocks):
            block = data[i * sub_size:(i + 1) * sub_size]
            if len(block) < 2:
                continue
            
            # Tendência (mean-adjusted series)
            mean_val = np.mean(block)
            adjusted = block - mean_val
            
            # Acumulado
            cumulative = np.cumsum(adjusted)
            
            # R e S
            r = np.max(cumulative) - np.min(cumulative)
            s = np.std(block, ddof=0)
            
            if s > 0:
                rs_values.append(r / s)
        
        if not rs_values:
            return 1.0
        
        return np.mean(rs_values)
    
    def calculate(self) -> HurstResult:
        """Calcula o coeficiente de Hurst.
        
        T027: H é diagnóstico - não hard-gate.
        O status PASS indica apenas que o cálculo foi bem-sucedido.
        
        Returns:
            HurstResult com status, H e regime
        """
        n = len(self.series)
        
        # Warm-up check
        if n < self.window_size:
            return HurstResult(
                status=HurstStatus.NEUTRO,
                hurst=None,
                regime=None,
                window_size=self.window_size,
                sub_sizes=self.sub_sizes
            )
        
        # Extrair janela final
        data = self.series[-self.window_size:]
        
        # Calcular R/S para cada sub-tamanho
        rs_values = []
        log_sizes = []
        
        for sub_size in self.sub_sizes:
            if sub_size < 2:
                continue
            rs = self._rescaled_range(data, sub_size)
            if rs > 0:
                rs_values.append(np.log(rs))
                log_sizes.append(np.log(sub_size))
        
        if len(rs_values) < 2:
            return HurstResult(
                status=HurstStatus.NEUTRO,
                hurst=None,
                regime=None,
                window_size=self.window_size,
                sub_sizes=self.sub_sizes
            )
        
        # Regressão log-log: log(R/S) = H * log(n) + C
        rs_values = np.array(rs_values)
        log_sizes = np.array(log_sizes)
        
        # Ajuste linear
        coeffs = np.polyfit(log_sizes, rs_values, 1)
        hurst = coeffs[0]
        
        # T027: H é diagnóstico - NÃO hard-gate
        # Apenas classificar o regime para informação
        # O gate de PASS agora é baseado em θ, IC_low e τ (spec 003b)
        if hurst < self.H_REVERSAL:
            regime = RegimeType.REVERSAL
            # Status PASS indica que H foi calculado (diagnostic only)
        elif hurst <= self.H_TREND:
            regime = None  # NEUTRO
        else:
            regime = None  # NEUTRO (H > 0.55 não gera tendência - T027)
        
        return HurstResult(
            status=HurstStatus.PASS,  # PASS apenas indica sucesso no cálculo
            hurst=float(hurst),
            regime=regime,
            window_size=self.window_size,
            sub_sizes=self.sub_sizes
        )


def calculate_hurst(series: List[float], window_size: int = 200, sub_sizes: List[int] = None) -> HurstResult:
    """Calcula o coeficiente de Hurst R/S.
    
    T027 (hotfix 003b): H é diagnóstico, não hard-gate de PASS/NEUTRO.
    O resultado indica apenas a classificação do regime (REVERSAL/NEUTRO).
    
    Args:
        series: Série de preços X_t (log-price)
        window_size: Tamanho da janela (default 200)
        sub_sizes: Sub-tamanhos para cálculo R/S
        
    Returns:
        HurstResult com status, H e regime
    """
    calculator = HurstCalculator(series, window_size, sub_sizes)
    return calculator.calculate()