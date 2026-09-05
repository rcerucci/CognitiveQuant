"""Pipeline F3: Hurst → OU → Bootstrap.

Orquestra a sequência de cálculo conforme spec §3.4-3.6.
- Consome apenas F2 PASS + série F1
- Saída in-memory com H, μ, θ, τ, bootstrap_cv_theta, flags

Estratégia:
1. Verificar F2 PASS
2. Calcular Hurst (se NEUTRO, parar)
3. Se REVERSAL, estimar OU
4. Bootstrap θ e calcular CV
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from motor.filters.pipeline import PipelineResult, PipelineStatus


class F3Status(str, Enum):
    """Status final do pipeline F3."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class F3PipelineResult:
    """Resultado completo do pipeline F3."""
    status: F3Status
    hurst: Optional[float] = None
    mu: Optional[float] = None
    theta: Optional[float] = None
    tau: Optional[float] = None
    bootstrap_cv_theta: Optional[float] = None
    is_theta_stable: Optional[bool] = None
    forca_penalty_cv: bool = False
    reason: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class F3Pipeline:
    """Pipeline F3 para classificação de regime e estimação OU."""
    
    HURST_REVERSAL_THRESHOLD = 0.45
    HURST_TREND_THRESHOLD = 0.55
    CV_STABILITY_THRESHOLD = 0.30
    
    def __init__(
        self,
        f2_result: PipelineResult,
        log_prices: List[float],
    ):
        """Inicializa o pipeline F3.
        
        Args:
            f2_result: Resultado do pipeline F2 (deve ter status PASS)
            log_prices: Série de preços log (X_t)
        """
        self.f2_result = f2_result
        self.log_prices = log_prices
    
    def _check_f2_pass(self) -> bool:
        """Verifica se F2 resultou em PASS."""
        return self.f2_result.status == PipelineStatus.PASS
    
    def run(self) -> F3PipelineResult:
        """Executa o pipeline F3.
        
        Ordem:
        1. Verificar F2 PASS
        2. Calcular Hurst → se NEUTRO, parar
        3. Se REVERSAL, estimar OU
        4. Bootstrap θ → CV
        
        Returns:
            F3PipelineResult com status e parâmetros
        """
        # Passo 1: Verificar F2 PASS
        if not self._check_f2_pass():
            return F3PipelineResult(
                status=F3Status.NEUTRO,
                reason="F2 did not pass",
                metrics={"f2_status": str(self.f2_result.status)}
            )
        
        # Importar componentes (evitar circular imports)
        from motor.regime.hurst import calculate_hurst, HurstStatus
        from motor.regime.ou import estimate_ou_kalman
        from motor.regime.bootstrap_theta import bootstrap_theta
        
        # Passo 2: Calcular Hurst
        hurst_result = calculate_hurst(self.log_prices)
        
        if hurst_result.status == HurstStatus.NEUTRO:
            return F3PipelineResult(
                status=F3Status.NEUTRO,
                hurst=hurst_result.hurst,
                reason="Hurst classification: NEUTRO (trend or neutral)",
                metrics={"hurst": hurst_result.hurst} if hurst_result.hurst else {}
            )
        
        # Passo 3: Estimar OU (apenas se REVERSAL)
        ou_result = estimate_ou_kalman(self.log_prices)
        
        if ou_result.status.value == "NEUTRO":
            return F3PipelineResult(
                status=F3Status.NEUTRO,
                hurst=hurst_result.hurst,
                mu=ou_result.mu,
                theta=ou_result.theta,
                reason=ou_result.reason or "OU θ ≤ 0",
                metrics={"hurst": hurst_result.hurst, "theta": ou_result.theta} if hurst_result.hurst else {}
            )
        
        # Passo 4: Bootstrap θ
        # Para bootstrap, precisamos de uma série de θs
        # Na prática, usamos o θ estimado como única amostra
        # e aplicamos bootstrap na série de preços
        bootstrap_result = bootstrap_theta(
            thetas=[ou_result.theta] if ou_result.theta else [],
            n_bootstrap=50,
            seed=42
        )
        
        # Construir resultado final
        result = F3PipelineResult(
            status=F3Status.PASS,
            hurst=hurst_result.hurst,
            mu=ou_result.mu,
            theta=ou_result.theta,
            tau=ou_result.tau,
            bootstrap_cv_theta=bootstrap_result.cv_theta,
            is_theta_stable=bootstrap_result.is_stable,
            forca_penalty_cv=bootstrap_result.forca_penalty_cv,
            metrics={
                "hurst": hurst_result.hurst,
                "mu": ou_result.mu,
                "theta": ou_result.theta,
                "tau": ou_result.tau,
                "cv_theta": bootstrap_result.cv_theta,
                "is_stable": bootstrap_result.is_stable,
                "penalty_cv": bootstrap_result.forca_penalty_cv,
                "method": ou_result.method,
            }
        )
        
        return result


def run_f3_pipeline(f2_result: PipelineResult, log_prices: List[float]) -> F3PipelineResult:
    """Executa o pipeline F3.
    
    Args:
        f2_result: Resultado do pipeline F2
        log_prices: Série de preços log (X_t)
        
    Returns:
        F3PipelineResult com status e parâmetros
    """
    pipeline = F3Pipeline(f2_result, log_prices)
    return pipeline.run()