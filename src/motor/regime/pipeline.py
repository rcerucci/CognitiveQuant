"""Pipeline F3: Hurst → OU → Bootstrap.

Orquestra a sequência de cálculo conforme spec §3.4-3.6.
- Consome apenas F2 PASS + série F1
- Saída in-memory com H, μ, θ, τ, bootstrap_cv_theta, flags

Estratégia (003b hotfix):
1. Verificar F2 PASS
2. Calcular Hurst (sem hard-gate - apenas diagnóstico)
3. Estimar OU (θ, τ)
4. Bootstrap θ → IC_low, CV
5. Gate: θ̂>0 ∧ IC_low>0 ∧ τ≤K
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from motor.filters.pipeline import PipelineResult, PipelineStatus

# Constante K = 20 barras M30 (lock Marcos 003b)
K_HALF_LIFE_BARS = 20


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
    ic_low: Optional[float] = None  # IC inferior (percentil 2.5%)
    reason: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    half_life_bars: int = K_HALF_LIFE_BARS  # K = 20


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
    
    def _check_reversal_gate(self, theta: Optional[float], ic_low: Optional[float], tau: Optional[float]) -> tuple[bool, str]:
        """Verifica gate de reversão conforme 003b: θ̂>0 ∧ IC_low>0 ∧ τ≤K.
        
        Args:
            theta: Estimativa de θ
            ic_low: IC inferior bootstrap (percentil 2.5%)
            tau: Meia-vida = ln(2)/θ
            
        Returns:
            Tupla (elegível, razão)
        """
        # Verificar θ > 0
        if theta is None or theta <= 0:
            return False, "θ ≤ 0 or not finite"
        
        # Verificar IC_low > 0
        if ic_low is None or ic_low <= 0:
            return False, f"IC_low ≤ 0 (ic_low={ic_low})"
        
        # Verificar τ ≤ K (K = 20)
        if tau is None or tau > K_HALF_LIFE_BARS:
            return False, f"τ > K (tau={tau}, K={K_HALF_LIFE_BARS})"
        
        return True, "Reversal gate passed"
    
    def run(self) -> F3PipelineResult:
        """Executa o pipeline F3.
        
        Ordem:
        1. Verificar F2 PASS
        2. Calcular Hurst → diagnóstico (sem hard-gate)
        3. Estimar OU (θ, τ)
        4. Bootstrap θ → IC_low, CV
        5. Gate: θ̂>0 ∧ IC_low>0 ∧ τ≤K
        
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
        
        # Passo 2: Calcular Hurst (diagnóstico apenas - T027)
        hurst_result = calculate_hurst(self.log_prices)
        
        # H é apenas diagnóstico - não hard-gate
        # Se H estiver None (warm-up), continuar → será NEUTRO pelo OU/bootstrap
        hurst_value = hurst_result.hurst
        
        # Passo 3: Estimar OU (apenas se REVERSAL ou warm-up)
        ou_result = estimate_ou_kalman(self.log_prices)
        
        # Se OU retornou NEUTRO, propagar
        if ou_result.status.value == "NEUTRO" or ou_result.theta is None or ou_result.theta <= 0:
            return F3PipelineResult(
                status=F3Status.NEUTRO,
                hurst=hurst_value,
                mu=ou_result.mu,
                theta=ou_result.theta,
                tau=ou_result.tau,
                reason=ou_result.reason or "OU θ ≤ 0",
                metrics={"hurst": hurst_value} if hurst_value else {}
            )
        
        # Passo 4: Bootstrap θ
        # Para bootstrap, precisamos de uma série de θs
        # Usamos o θ estimado como única amostra e aplicamos bootstrap
        bootstrap_result = bootstrap_theta(
            thetas=[ou_result.theta] if ou_result.theta else [],
            n_bootstrap=50,
            seed=42
        )
        
        # Passo 5: Gate de reversão T030: θ̂>0 ∧ IC_low>0 ∧ τ≤K
        theta_hat = ou_result.theta
        ic_low = bootstrap_result.ic_low
        tau = ou_result.tau
        
        gate_pass, gate_reason = self._check_reversal_gate(theta_hat, ic_low, tau)
        
        if not gate_pass:
            return F3PipelineResult(
                status=F3Status.NEUTRO,
                hurst=hurst_value,
                mu=ou_result.mu,
                theta=theta_hat,
                tau=tau,
                bootstrap_cv_theta=bootstrap_result.cv_theta,
                is_theta_stable=bootstrap_result.is_stable,
                forca_penalty_cv=bootstrap_result.forca_penalty_cv,
                ic_low=ic_low,
                reason=f"Gate failed: {gate_reason}",
                metrics={
                    "hurst": hurst_value,
                    "mu": ou_result.mu,
                    "theta": theta_hat,
                    "tau": tau,
                    "cv_theta": bootstrap_result.cv_theta,
                    "ic_low": ic_low,
                    "is_stable": bootstrap_result.is_stable,
                    "penalty_cv": bootstrap_result.forca_penalty_cv,
                    "method": ou_result.method,
                }
            )
        
        # PASS: todos os gates passaram
        return F3PipelineResult(
            status=F3Status.PASS,
            hurst=hurst_value,
            mu=ou_result.mu,
            theta=theta_hat,
            tau=tau,
            bootstrap_cv_theta=bootstrap_result.cv_theta,
            is_theta_stable=bootstrap_result.is_stable,
            forca_penalty_cv=bootstrap_result.forca_penalty_cv,
            ic_low=ic_low,
            reason=None,
            metrics={
                "hurst": hurst_value,
                "mu": ou_result.mu,
                "theta": theta_hat,
                "tau": tau,
                "cv_theta": bootstrap_result.cv_theta,
                "ic_low": ic_low,
                "is_stable": bootstrap_result.is_stable,
                "penalty_cv": bootstrap_result.forca_penalty_cv,
                "method": ou_result.method,
            }
        )


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