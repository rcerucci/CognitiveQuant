"""Cálculo do coeficiente de Hurst via R/S ou DFA (Detrended Fluctuation Analysis).

Implementa Hurst com escalas {8,16,32,64} via DFA como método principal,
com fallback R/S com sub-tamanhos {8,16,32,64,128}.

Para classificação de regime conforme spec §3.4:
- H < 0.45 → REVERSÃO
- 0.45 ≤ H ≤ 0.55 → NEUTRO
- H > 0.55 → NEUTRO
- Histórico < 200 → NEUTRO (warm-up)
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


class HurstMethod(str, Enum):
    """Método usado para calcular Hurst."""
    RS = "r/s"
    DFA = "dfa"


@dataclass
class HurstResult:
    """Resultado do cálculo do Hurst R/S/DFA."""
    status: HurstStatus
    hurst: Optional[float] = None
    regime: Optional[RegimeType] = None
    method: Optional[HurstMethod] = None
    window_size: int = 200
    sub_sizes: Optional[List[int]] = None
    dfa_scales: Optional[List[int]] = None
    
    def __post_init__(self):
        if self.sub_sizes is None:
            self.sub_sizes = [8, 16, 32, 64, 128]
        if self.dfa_scales is None:
            self.dfa_scales = [8, 16, 32, 64]


class HurstCalculator:
    """Calculadora de Hurst via DFA (principal) com fallback R/S."""
    
    WINDOW_SIZE = 200
    # Escalas para DFA (método principal conforme spec)
    DFA_SCALES = [8, 16, 32, 64]
    # Escalas para R/S (fallback)
    RS_SCALES = [8, 16, 32, 64, 128]
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
        self.sub_sizes = sub_sizes if sub_sizes is not None else list(self.RS_SCALES)
    
    def _rescaled_range(self, data: np.ndarray, n_scale: int) -> float:
        """Calcula o R/S (Rescaled Range) para um tamanho de escala.
        
        Args:
            data: Dados de entrada
            n_scale: Tamanho da escala
            
        Returns:
            Valor R/S
        """
        n = len(data)
        if n_scale >= n:
            n_scale = n - 1
        
        if n_scale < 2:
            return 1.0
        
        # Número de blocos
        n_blocks = max(1, n // n_scale)
        
        rs_list = []
        
        for b in range(n_blocks):
            block_start = b * n_scale
            block_end = min((b + 1) * n_scale, n)
            block = data[block_start:block_end]
            
            if len(block) < 2:
                continue
            
            # Média do bloco
            mean_block = np.mean(block)
            
            # Série ajustada (desvios da média)
            adjusted = block - mean_block
            
            # Acumulado (caminho de random walk)
            cumulative = np.cumsum(adjusted)
            
            # R = amplitude do caminho
            R = np.max(cumulative) - np.min(cumulative)
            
            # S = desvio-padrão do bloco
            S = np.std(block, ddof=1)
            
            if S > 1e-10:
                rs_list.append(R / S)
        
        if not rs_list:
            return 1.0
        
        return np.mean(rs_list)
    
    def _calculate_dfa(self, data: np.ndarray, scales: List[int] = None) -> Optional[float]:
        """Calcula Hurst via DFA (Detrended Fluctuation Analysis).
        
        DFA é o método principal conforme spec.
        
        Args:
            data: Série de dados
            scales: Lista de escalas para análise
            
        Returns:
            Estimativa de Hurst via DFA, ou None se falhar
        """
        if scales is None:
            scales = self.DFA_SCALES
        
        # Limpar dados
        data = np.array(data, dtype=np.float64)
        n = len(data)
        
        if n < 2 * max(scales):
            scales = [s for s in scales if s < n // 2]
            if len(scales) < 2:
                return None
        
        # Passo 1: Calcular a série integrada
        # Y(k) = sum_{i=1}^{k} (X_i - mean(X))
        mean_x = np.mean(data)
        y = np.cumsum(data - mean_x)
        
        F_factors = []
        log_scales = []
        
        for s in scales:
            if s <= 0 or s >= n // 2:
                continue
            
            # Dividir a série integrada em blocos de tamanho s
            n_blocks = n // s
            if n_blocks < 2:
                continue
            
            F_s_sum = 0.0
            
            for b in range(n_blocks):
                # Extrair segmento
                start_idx = b * s
                end_idx = (b + 1) * s
                segment = y[start_idx:end_idx]
                
                if len(segment) < 2:
                    continue
                
                # Ajustar tendência (polinômio grau 1 - linha reta)
                x_local = np.arange(len(segment))
                
                # Linear regression
                coeffs = np.polyfit(x_local, segment, 1)
                trend = np.polyval(coeffs, x_local)
                
                # Flutuação após detrending
                detrended = segment - trend
                F_s_sum += np.mean(detrended ** 2)
            
            F_s = np.sqrt(F_s_sum / n_blocks)
            
            if F_s > 1e-10:
                F_factors.append(np.log(F_s))
                log_scales.append(np.log(s))
        
        if len(F_factors) < 2:
            return None
        
        # Regressão: log(F(s)) = H * log(s) + C
        coeffs = np.polyfit(log_scales, F_factors, 1)
        hurst_dfa = coeffs[0]
        
        return hurst_dfa
    
    def _calculate_rs_hurst(self, data: np.ndarray, scales: List[int]) -> Optional[float]:
        """Calcula Hurst usando o método R/S.
        
        Args:
            data: Série de dados
            scales: Lista de escalas para calcular R/S
            
        Returns:
            Estimativa de Hurst
        """
        if len(data) < max(scales) + 1:
            scales = [s for s in scales if s < len(data) // 2]
        
        if len(scales) < 2:
            return None
        
        log_ratios = []
        log_scales = []
        
        for s in scales:
            rs = self._rescaled_range(data, s)
            if rs > 1e-10:
                log_ratios.append(np.log(rs))
                log_scales.append(np.log(s))
        
        if len(log_ratios) < 2:
            return None
        
        # Regressão linear: log(R/S) = H * log(n) + C
        coeffs = np.polyfit(log_scales, log_ratios, 1)
        hurst = coeffs[0]
        
        return hurst
    
    def _classify_regime(self, hurst: float) -> tuple[RegimeType, HurstStatus]:
        """Classifica o regime baseado no Hurst.
        
        Args:
            hurst: Estimativa de Hurst
            
        Returns:
            Tupla (RegimeType, HurstStatus)
        """
        # Normalizar para [0, 1] se necessário
        if hurst < 0.0:
            hurst = 0.01
        elif hurst > 1.0:
            hurst = 0.99
        
        # Classificação conforme spec
        if hurst < self.H_REVERSAL:
            return RegimeType.REVERSAL, HurstStatus.PASS
        elif hurst <= self.H_TREND:
            return None, HurstStatus.NEUTRO
        else:
            return None, HurstStatus.NEUTRO
    
    def calculate(self) -> HurstResult:
        """Calcula o coeficiente de Hurst.
        
        Estratégia conforme spec:
        1. DFA com escalas {8,16,32,64} (método principal)
        2. Se DFA falhar, usar R/S com escalas {8,16,32,64,128}
        
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
                method=None,
                window_size=self.window_size,
                sub_sizes=self.sub_sizes,
                dfa_scales=self.DFA_SCALES
            )
        
        # Extrair janela final
        data = self.series[-self.window_size:].copy()
        
        hurst = None
        method = None
        
        # Priorizar DFA (método principal conforme spec)
        dfa_hurst = self._calculate_dfa(data, self.DFA_SCALES)
        if dfa_hurst is not None:
            # Normalizar para [0, 1] se necessário
            if 0.0 <= dfa_hurst <= 1.0:
                hurst = dfa_hurst
                method = HurstMethod.DFA
            elif dfa_hurst < 0.0:
                hurst = 0.01
                method = HurstMethod.DFA
            elif dfa_hurst > 1.0:
                hurst = 0.99
                method = HurstMethod.DFA
        
        # Fallback para R/S se DFA falhar
        if hurst is None:
            rs_hurst = self._calculate_rs_hurst(data, self.RS_SCALES)
            if rs_hurst is not None:
                # Normalizar se necessário
                if rs_hurst < 0.0:
                    rs_hurst = 0.01
                elif rs_hurst > 1.0:
                    rs_hurst = 0.99
                hurst = rs_hurst
                method = HurstMethod.RS
        
        # Se ainda não conseguiu calcular
        if hurst is None:
            return HurstResult(
                status=HurstStatus.NEUTRO,
                hurst=None,
                regime=None,
                method=None,
                window_size=self.window_size,
                sub_sizes=self.sub_sizes,
                dfa_scales=self.DFA_SCALES
            )
        
        # Classificação de regime
        regime, status = self._classify_regime(hurst)
        
        return HurstResult(
            status=status,
            hurst=float(hurst),
            regime=regime,
            method=method,
            window_size=self.window_size,
            sub_sizes=self.sub_sizes,
            dfa_scales=self.DFA_SCALES
        )


def calculate_hurst(series: List[float], window_size: int = 200, sub_sizes: List[int] = None) -> HurstResult:
    """Calcula o coeficiente de Hurst via DFA (principal) com fallback R/S.
    
    Estratégia conforme spec:
    1. DFA com escalas {8,16,32,64}
    2. R/S com escalas {8,16,32,64,128} como fallback
    
    Args:
        series: Série de preços X_t (log-price)
        window_size: Tamanho da janela (default 200)
        sub_sizes: Sub-tamanhos para cálculo R/S
        
    Returns:
        HurstResult com status, H, regime e método usado
    """
    calculator = HurstCalculator(series, window_size, sub_sizes)
    return calculator.calculate()