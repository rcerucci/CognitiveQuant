"""Pipeline de filtros de qualidade (US5).

Orquestra os filtros na ordem §5.1: Spread → ADF → TR → Vol Parkinson
com short-circuit no primeiro filtro que falha.

Spec: §3.3 / US5 / Addendum ADF r_t
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

from motor.filters.spread import FilterSpread, FilterSpreadResult, FilterStatus as SpreadStatus
from motor.filters.adf import FilterADF, FilterADFResult, FilterStatus as ADFStatus
from motor.filters.tr import FilterTR, FilterTRResult, FilterStatus as TRStatus
from motor.filters.parkinson import FilterParkinson, FilterParkinsonResult, FilterStatus as ParkinsonStatus

class PipelineStatus(str, Enum):
    """Status final do pipeline."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"
    NEUTRO_TEMPORARIO = "NEUTRO_TEMPORARIO"


@dataclass
class PipelineResult:
    """Resultado completo do pipeline de filtros."""
    status: PipelineStatus
    evaluated_filters: List[str] = field(default_factory=list)
    failed_filter: Optional[str] = None
    reason: Optional[str] = None
    log_message: Optional[str] = None
    spread_result: Optional[FilterSpreadResult] = None
    adf_result: Optional[FilterADFResult] = None
    tr_result: Optional[FilterTRResult] = None
    parkinson_result: Optional[FilterParkinsonResult] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """Pipeline de filtros conforme US5.
    
    Ordem: Spread → ADF → TR → Vol Parkinson
    Short-circuit no primeiro filtro que falha.
    
    - Input: ValidatedSeries do F1
    - Output: PipelineResult (status PASS/NEUTRO/NEUTRO_TEMPORARIO, motivos, métricas)
    - gap_dados/NEUTRO F1 → não promove PASS
    """
    
    def __init__(self, bars: List, index: int = -1):
        """Inicializa o pipeline.
        
        Args:
            bars: Lista de ValidatedBar (saída do F1)
            index: Índice da barra atual (default: última)
        """
        self.bars = bars
        self.index = index
    
    def _check_gap_dados(self) -> bool:
        """Verifica se alguma barra tem gap_dados (buraco real).

        weekend_fill sozinho NÃO conta como gap_dados (Addendum F1).
        Se a barra tem 'gap_dados' em flags, é um buraco real independente
        de ter também 'weekend_fill'.
        """
        for bar in self.bars:
            if not bar.flags:
                continue
            if "gap_dados" in bar.flags:
                return True
        return False
    
    def _extract_returns(self) -> List[float]:
        """Extrai a série de retornos r_t = X_t - X_{t-1}.
        
        X_t = ln(P_t) = ln((bid + ask) / 2)
        r_t = X_t - X_{t-1}
        
        Returns:
            Lista de retornos (r_t). Só floats, 199 retornos se houver 200 preços.
        """
        import math
        
        # Calcular log-preços: X_t = ln(P_t)
        X_t = [math.log((bar.bid + bar.ask) / 2.0) for bar in self.bars]
        
        # Calcular retornos: r_t = X_t - X_{t-1} (sem None)
        # Só floats, começa do índice 1
        r_t = [X_t[i] - X_t[i-1] for i in range(1, len(X_t))]
        
        return r_t
    
    def run(self) -> PipelineResult:
        """Executa o pipeline de filtros na ordem §5.1.
        
        Ordem:
        1. Spread (T008) → falha → NEUTRO
        2. ADF (T011) → falha → NEUTRO (agora em r_t, não X_t)
        3. TR (T014) → falha → NEUTRO
        4. Parkinson (T017) → falha → NEUTRO temporário + log
        
        Short-circuit no primeiro que falha.
        
        Returns:
            PipelineResult com status, filtros avaliados e métricas
        """
        n = len(self.bars)
        
        # Check: se houver gap_dados, NÃO promove PASS
        if self._check_gap_dados():
            return PipelineResult(
                status=PipelineStatus.NEUTRO,
                evaluated_filters=["gap_dados_check"],
                failed_filter="gap_dados",
                reason="series_has_gaps",
                metrics={"current_length": n}
            )
        
        # 1. Filtro Spread
        spread_result = FilterSpread(self.bars, self.index).run()
        if spread_result.status == SpreadStatus.NEUTRO:
            return PipelineResult(
                status=PipelineStatus.NEUTRO,
                evaluated_filters=["spread"],
                failed_filter="spread",
                reason=spread_result.reason,
                spread_result=spread_result,
                metrics={"spread": spread_result.spread, "spread_ma20": spread_result.spread_ma20}
            )
        
        # 2. Filtro ADF - Agora usando r_t (retornos) em vez de X_t
        # Extrai a série de retornos r_t
        r_t = self._extract_returns()
        
        # Para ADF, precisamos de 200 retornos
        # Se tiver menos, usar a quantidade disponível como janela
        window = min(len(r_t), 200)
        adf_result = FilterADF(r_t, window=window).run()
        if adf_result.status == "NEUTRO":  # string comparison para compatibilidade
            return PipelineResult(
                status=PipelineStatus.NEUTRO,
                evaluated_filters=["spread", "adf"],
                failed_filter="adf",
                reason=adf_result.reason,
                spread_result=spread_result,
                adf_result=adf_result,
                metrics={"p_value": adf_result.p_value}
            )
        
        # 3. Filtro TR
        tr_result = FilterTR(self.bars, self.index).run()
        if tr_result.status == "NEUTRO":  # string comparison
            return PipelineResult(
                status=PipelineStatus.NEUTRO,
                evaluated_filters=["spread", "adf", "tr"],
                failed_filter="tr",
                reason=tr_result.reason,
                spread_result=spread_result,
                adf_result=adf_result,
                tr_result=tr_result,
                metrics={"TR": tr_result.TR, "TR_ma20": tr_result.TR_ma20}
            )
        
        # 4. Filtro Parkinson
        parkinson_result = FilterParkinson(self.bars, self.index).run()
        if parkinson_result.status == "NEUTRO_TEMPORARIO":
            return PipelineResult(
                status=PipelineStatus.NEUTRO_TEMPORARIO,
                evaluated_filters=["spread", "adf", "tr", "parkinson"],
                failed_filter="parkinson",
                reason=parkinson_result.reason,
                log_message=parkinson_result.log_message,
                spread_result=spread_result,
                adf_result=adf_result,
                tr_result=tr_result,
                parkinson_result=parkinson_result,
                metrics={"sigma_20": parkinson_result.sigma_20, "sigma_60": parkinson_result.sigma_60, "ratio": parkinson_result.ratio}
            )
        
        # Todos passaram
        return PipelineResult(
            status=PipelineStatus.PASS,
            evaluated_filters=["spread", "adf", "tr", "parkinson"],
            spread_result=spread_result,
            adf_result=adf_result,
            tr_result=tr_result,
            parkinson_result=parkinson_result,
            metrics={
                "spread": spread_result.spread,
                "p_value": adf_result.p_value,
                "TR": tr_result.TR,
                "ratio": parkinson_result.ratio
            }
        )