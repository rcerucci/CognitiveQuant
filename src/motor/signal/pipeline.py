"""Pipeline F5: confirmação → força → threshold → payload.

Orquestra a sequência conforme spec US5:
1. Verificar F4 PASS
2. Calcular confirmações 8.1-8.6
3. Calcular força e direção
4. Classificar confiança
5. Gerar payload JSON §3.11

Reference: Espec F5 US5
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import numpy as np

from motor.vol.pipeline import F4PipelineResult, F4Status
from motor.regime.pipeline import F3PipelineResult, F3Status
from motor.signal.confirmacao import (
    ConfirmacaoResult,
    ConfirmacaoStatus,
    calculate_confirmacao,
    ConfirmacaoDirection,
)
from motor.signal.forca import (
    ForcaResult,
    Direction,
    Confidence,
    calcular_forca,
    ForcaStatus,
)
from motor.signal.thresholds import (
    ConfidenceLevel,
    classificar_confianca,
)
from motor.signal.payload import (
    PayloadMotor,
    SinalQuantitativo,
    EstatisticasModelo,
    RiscosEstatisticos,
    CalibracaoAdaptativa,
    criar_payload_neutro,
    montar_payload,
)


class F5Status(str, Enum):
    """Status final do pipeline F5."""
    PASS = "PASS"
    NEUTRO = "NEUTRO"


@dataclass
class F5PipelineResult:
    """Resultado completo do pipeline F5."""
    status: F5Status
    payload: Optional[PayloadMotor] = None
    confirmacao: Optional[ConfirmacaoResult] = None
    forca_result: Optional[ForcaResult] = None
    confianca: Optional[ConfidenceLevel] = None
    reason: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class F5Pipeline:
    """Pipeline F5 para confirmação, força e payload."""
    
    def __init__(
        self,
        f4_result: F4PipelineResult,
        f3_result: F3PipelineResult,
        bar: List[float],  # [timestamp, open, high, low, close, bid, ask]
        returns: List[float],
        instrumento: str,
        seed: int = 42,
    ):
        """Inicializa o pipeline F5.
        
        Args:
            f4_result: Resultado do pipeline F4 (deve ter status PASS)
            f3_result: Resultado do pipeline F3
            bar: Barra OHLC [timestamp, open, high, low, close, bid, ask]
            returns: Série de retornos
            instrumento: Símbolo do instrumento
            seed: Seed para reprodutibilidade
        """
        self.f4_result = f4_result
        self.f3_result = f3_result
        self.bar = bar
        self.returns = returns
        self.instrumento = instrumento
        self.seed = seed
    
    def _check_f4_pass(self) -> bool:
        """Verifica se F4 resultou em PASS."""
        return self.f4_result.status == F4Status.PASS
    
    def _get_direction_from_z(self, z_t: float) -> str:
        """Determina direção a partir de Z_t."""
        if z_t < 0:
            return "LONG"
        elif z_t > 0:
            return "SHORT"
        else:
            return "NEUTRO"
    
    def run(self) -> F5PipelineResult:
        """Executa o pipeline F5.
        
        Ordem:
        1. Verificar F4 PASS
        2. Calcular confirmações 8.1-8.6
        3. Calcular força e direção
        4. Classificar confiança
        5. Gerar payload
        
        Returns:
            F5PipelineResult com payload e métricas
        """
        np.random.seed(self.seed)
        
        # Step 1: Verificar F4 PASS
        if not self._check_f4_pass():
            payload = criar_payload_neutro(
                instrumento=self.instrumento,
                candle_contexto={"reason": "F4 não PASS"},
                evidencias=["F4 status: " + str(self.f4_result.status)],
            )
            return F5PipelineResult(
                status=F5Status.NEUTRO,
                payload=payload,
                reason="F4 did not pass",
                metrics={"f4_status": str(self.f4_result.status)},
            )
        
        # Coletar dados de F4 e F3
        z_t = self.f4_result.z_t
        percentil_z = self.f4_result.percentil_z
        
        direction_z = self._get_direction_from_z(z_t) if z_t is not None else "NEUTRO"
        
        # Obter dados de F3
        hurst = self.f3_result.hurst
        theta = self.f3_result.theta
        tau = self.f3_result.tau
        cv_theta = self.f3_result.bootstrap_cv_theta
        forca_penalty_cv = self.f3_result.forca_penalty_cv
        
        # Step 2: Calcular confirmações
        confirmacao = calculate_confirmacao(
            returns=self.returns,
            bar=self.bar,
            direction=direction_z,
            seed=self.seed,
        )
        
        # 8.6 abort ou falha de confirmação → NEUTRO
        if confirmacao.status == ConfirmacaoStatus.NEUTRO:
            payload = criar_payload_neutro(
                instrumento=self.instrumento,
                candle_contexto={
                    "timestamp": self.bar[0] if len(self.bar) > 0 else None,
                    "open": self.bar[1] if len(self.bar) > 1 else None,
                    "high": self.bar[2] if len(self.bar) > 2 else None,
                    "low": self.bar[3] if len(self.bar) > 3 else None,
                    "close": self.bar[4] if len(self.bar) > 4 else None,
                },
                filtros_passados=confirmacao.filters_passed,
                evidencias=[confirmacao.reason or "Confirmação falhou"],
                skewness_extrema="skewness" in str(confirmacao.reason).lower(),
            )
            return F5PipelineResult(
                status=F5Status.NEUTRO,
                payload=payload,
                confirmacao=confirmacao,
                reason=confirmacao.reason,
                metrics={**confirmacao.metrics.__dict__} if confirmacao.metrics else {},
            )
        
        # Step 3: Calcular força
        forca_result = calcular_forca(
            z_t=z_t,
            percentil_z=percentil_z,
            rho_1=confirmacao.metrics.rho_1 if confirmacao.metrics else None,
            clv=confirmacao.metrics.clv if confirmacao.metrics else None,
            rb=confirmacao.metrics.rb if confirmacao.metrics else None,
            skewness=confirmacao.metrics.skewness if confirmacao.metrics else None,
            cv_theta=cv_theta,
            forca_penalty_cv=forca_penalty_cv,
            lb_soft_gate=confirmacao.metrics.lb_soft_gate if confirmacao.metrics else False,
            seed=self.seed,
        )
        
        # Step 4: Classificar confiança
        confianca = classificar_confianca(forca_result.forca)
        
        # Step 5: Gerar payload
        payload = montar_payload(
            direcao=forca_result.direction.value,
            forca=forca_result.forca,
            confianca=confianca.value if confianca != ConfidenceLevel.NEUTRO else "NEUTRO",
            instrumento=self.instrumento,
            z_score=z_t,
            percentil_z=percentil_z,
            hurst=hurst,
            regime=None,  # F3PipelineResult doesn't have regime attribute
            tau=tau,
            mu=self.f3_result.mu,
            theta=theta,
            garch_sigma=self.f4_result.garch_sigma,
            omega=self.f4_result.omega,
            alpha=self.f4_result.alpha,
            beta=self.f4_result.beta,
            cv_theta=cv_theta,
            candle_contexto={
                "timestamp": self.bar[0] if len(self.bar) > 0 else None,
                "open": self.bar[1] if len(self.bar) > 1 else None,
                "high": self.bar[2] if len(self.bar) > 2 else None,
                "low": self.bar[3] if len(self.bar) > 3 else None,
                "close": self.bar[4] if len(self.bar) > 4 else None,
            },
            filtros_passados=confirmacao.filters_passed,
            evidencias=[
                f"ACF(1) = {confirmacao.metrics.rho_1:.4f}" if confirmacao.metrics and confirmacao.metrics.rho_1 is not None else "ACF(1) = N/A",
                f"CLV = {confirmacao.metrics.clv:.4f}" if confirmacao.metrics and confirmacao.metrics.clv is not None else "CLV = N/A",
                f"RB = {confirmacao.metrics.rb:.4f}" if confirmacao.metrics and confirmacao.metrics.rb is not None else "RB = N/A",
            ],
            forca_penalizada=len(forca_result.penalizacoes_aplicadas) > 0,
            cv_theta_alto=cv_theta is not None and cv_theta > 0.30 if cv_theta else False,
            reversao_confirmada=confirmacao.metrics.rho_1 is not None and confirmacao.metrics.rho_1 < 0 if confirmacao.metrics else False,
            skewness_extrema=False,  # 8.6 já foi tratado acima
        )
        
        status = F5Status.PASS if confianca != ConfidenceLevel.NEUTRO else F5Status.NEUTRO
        
        return F5PipelineResult(
            status=status,
            payload=payload,
            confirmacao=confirmacao,
            forca_result=forca_result,
            confianca=confianca,
            reason=f"Pipeline completo: {forca_result.direction.value} com força {forca_result.forca:.2f}",
            metrics={
                "direction": forca_result.direction.value,
                "forca": forca_result.forca,
                "confianca": confianca.value,
                "filtros_passados": confirmacao.filters_passed,
                "penalizacoes": forca_result.penalizacoes_aplicadas,
            },
        )


def run_f5_pipeline(
    f4_result: F4PipelineResult,
    f3_result: F3PipelineResult,
    bar: List[float],
    returns: List[float],
    instrumento: str,
    seed: int = 42,
) -> F5PipelineResult:
    """Executa o pipeline F5.
    
    Args:
        f4_result: Resultado do pipeline F4
        f3_result: Resultado do pipeline F3
        bar: Barra OHLC [timestamp, open, high, low, close, bid, ask]
        returns: Série de retornos
        instrumento: Símbolo do instrumento
        seed: Seed para reprodutibilidade
        
    Returns:
        F5PipelineResult com payload in-memory
    """
    pipeline = F5Pipeline(f4_result, f3_result, bar, returns, instrumento, seed)
    return pipeline.run()