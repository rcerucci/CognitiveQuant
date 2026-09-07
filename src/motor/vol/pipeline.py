"""Pipeline F4: GARCH → Z → percentil.

Orquestra a sequência conforme spec §3.7-3.8:
1. Verificar F3 PASS
2. Estimar GARCH(1,1) com fallback
3. Calcular Z-score condicional
4. Calcular percentil empírico de |Z|

Input: F3PipelineResult (PASS com μ_t)
Output: F4PipelineResult (in-memory) - σ, ω/α/β, fonte, Z_t, percentil_z

Reference: Espec F4 §3.7-3.8
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field
import math
import numpy as np

from motor.regime.pipeline import F3PipelineResult, F3Status


class F4Status(str, Enum):
    """Status final do pipeline F4."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class F4PipelineResult:
    """Resultado completo do pipeline F4."""
    status: F4Status
    garch_sigma: Optional[float] = None
    omega: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    source: Optional[str] = None  # "garch" or "fallback"
    z_t: Optional[float] = None
    percentil_z: Optional[float] = None  # P_t ∈ [0, 1]
    reason: Optional[str] = None
    metrics: dict = field(default_factory=dict)


class F4Pipeline:
    """Pipeline F4 para GARCH + Z + percentil."""

    GARCH_WINDOW = 200  # r_{t-199:t}
    FALLBACK_N = 20     # √(∑ r² / 20)
    PERCENTIL_WINDOW = 200

    def __init__(
        self,
        f3_result: F3PipelineResult,
        X_t: float,
        r_t: float,
        returns_history: List[float],
        z_history: List[float],
        seed: int = 42,
    ):
        """Inicializa o pipeline F4.

        Args:
            f3_result: Resultado do pipeline F3 (deve ter status PASS)
            X_t: Preço/log-preço atual
            r_t: Retorno atual
            returns_history: Série histórica de retornos (r_{t-199:t})
            z_history: Histórico de |Z| para percentil (200 valores)
            seed: Seed para reprodutibilidade
        """
        self.f3_result = f3_result
        self.X_t = X_t
        self.r_t = r_t
        self.returns_history = returns_history
        self.z_history = z_history
        self.seed = seed

    def _check_f3_pass(self) -> bool:
        """Verifica se F3 resultou em PASS."""
        return self.f3_result.status == F3Status.PASS

    def run(self) -> F4PipelineResult:
        """Executa o pipeline F4.

        Ordem:
        1. Verificar F3 PASS
        2. Estimar GARCH → σ_t (ou fallback)
        3. Calcular Z_t
        4. Calcular percentil_z

        Returns:
            F4PipelineResult com garch_sigma, Z_t, percentil_z, fonte
        """
        # Step 1: Verificar F3 PASS
        if not self._check_f3_pass():
            return F4PipelineResult(
                status=F4Status.NEUTRO,
                reason="F3 did not pass",
                metrics={"f3_status": str(self.f3_result.status)}
            )

        # Import components (lazy import to avoid circular)
        from motor.vol.garch import estimate_garch_with_fallback, GARCHStatus
        from motor.vol.zscore import calculate_zscore, ZScoreStatus
        from motor.vol.percentil import calculate_percentil_z, PercentilStatus

        # Step 2: Estimar GARCH com fallback
        garch_result = estimate_garch_with_fallback(self.returns_history, seed=self.seed)

        if garch_result.status == GARCHStatus.NEUTRO:
            # GARCH failed and fallback also failed
            return F4PipelineResult(
                status=F4Status.NEUTRO,
                reason=garch_result.reason or "garch_fallback_failed",
                metrics={"garch_status": str(garch_result.status)}
            )

        # Step 3: Calcular Z-score
        garch_sigma = garch_result.garch_sigma
        if garch_sigma is None:
            return F4PipelineResult(
                status=F4Status.NEUTRO,
                reason="garch_sigma_none",
                metrics={"garch_source": garch_result.source}
            )

        zscore_result = calculate_zscore(
            self.r_t,
            garch_sigma
        )

        if zscore_result.status == ZScoreStatus.NEUTRO:
            return F4PipelineResult(
                status=F4Status.NEUTRO,
                reason=zscore_result.reason or "zscore_failed",
                metrics={
                    "garch_source": garch_result.source,
                    "garch_sigma": garch_result.garch_sigma
                }
            )

        # Step 4: Calcular percentil de |Z|
        # Need to build |Z| history including current Z
        z_history_extended = list(self.z_history) + [abs(zscore_result.z_t)]

        percentil_result = calculate_percentil_z(
            zscore_result.z_t,
            z_history_extended,
            window_size=self.PERCENTIL_WINDOW
        )

        if percentil_result.status == PercentilStatus.NEUTRO:
            return F4PipelineResult(
                status=F4Status.NEUTRO,
                reason=percentil_result.reason or "percentil_failed",
                metrics={
                    "garch_source": garch_result.source,
                    "z_t": zscore_result.z_t
                }
            )

        # Build final result
        return F4PipelineResult(
            status=F4Status.PASS,
            garch_sigma=garch_result.garch_sigma,
            omega=garch_result.omega,
            alpha=garch_result.alpha,
            beta=garch_result.beta,
            source=garch_result.source,
            z_t=zscore_result.z_t,
            percentil_z=percentil_result.percentil_z,
            metrics={
                "garch_source": garch_result.source,
                "garch_sigma": garch_result.garch_sigma,
                "z_t": zscore_result.z_t,
                "percentil_z": percentil_result.percentil_z,
            }
        )


def run_f4_pipeline(
    f3_result: F3PipelineResult,
    X_t: float,
    r_t: float,
    returns_history: List[float],
    z_history: List[float],
    seed: int = 42,
) -> F4PipelineResult:
    """Executa o pipeline F4.

    Args:
        f3_result: Resultado do pipeline F3
        X_t: Preço/log-preço atual
        r_t: Retorno atual
        returns_history: Série histórica de retornos
        z_history: Histórico de |Z| para percentil
        seed: Seed para reprodutibilidade

    Returns:
        F4PipelineResult in-memory com garch_sigma, Z_t, percentil_z, fonte
    """
    pipeline = F4Pipeline(f3_result, X_t, r_t, returns_history, z_history, seed)
    return pipeline.run()