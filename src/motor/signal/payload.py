"""Payload JSON do motor (§3.11) - US4.

Implementa a estrutura de saída in-memory serializável JSON.

Reference: Espec F5 §3.11, US4
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json


@dataclass
class SinalQuantitativo:
    """Sinal quantitativo do motor."""
    direcao: str  # LONG, SHORT, NEUTRO
    forca: float  # [0, 1]
    confianca: str  # ALTA, MÉDIA, NEUTRO
    z_score: Optional[float] = None
    percentil_z: Optional[float] = None
    hurst: Optional[float] = None
    regime: Optional[str] = None
    meia_vida_barras: Optional[float] = None
    meia_vida_minutos: Optional[float] = None
    validade_ate: Optional[str] = None


@dataclass
class EstatisticasModelo:
    """Estatísticas do modelo."""
    mu_t: Optional[float] = None
    theta: Optional[float] = None
    garch_sigma: Optional[float] = None
    omega: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    cv_theta: Optional[float] = None


@dataclass
class RiscosEstatisticos:
    """Riscos estatísticos do sinal."""
    forca_penalizada: bool = False
    cv_theta_alto: bool = False
    reversao_confirmada: bool = False
    skewness_extrema: bool = False


@dataclass
class CalibracaoAdaptativa:
    """Calibração adaptativa (placeholder para futuro)."""
    threshold_adaptativo: Optional[float] = None
    trigger_rate_2sem: Optional[float] = None


@dataclass  
class PayloadMotor:
    """Payload JSON do motor conforme §3.11.
    
    Estrutura in-memory serializável para saída da Camada 1.
    """
    # Header
    versao_protocolo: str = "F5.0"
    timestamp_geracao: str = ""  # UTC ISO format
    origem: str = "motor"
    
    # Instrument context
    instrumento: str = ""
    timeframe: str = "M30"
    
    # Signal
    sinal_quantitativo: SinalQuantitativo = field(default_factory=lambda: SinalQuantitativo(
        direcao="NEUTRO",
        forca=0.0,
        confianca="NEUTRO"
    ))
    
    # Statistics
    estatisticas_modelo: EstatisticasModelo = field(default_factory=EstatisticasModelo)
    
    # Filters & Context
    filtros_passados: List[str] = field(default_factory=list)
    candle_contexto: Dict[str, Any] = field(default_factory=dict)
    evidencias: List[str] = field(default_factory=list)
    
    # Risks
    riscos_estatisticos: RiscosEstatisticos = field(default_factory=RiscosEstatisticos)
    
    # Calibration (placeholder)
    calibracao_adaptativa: CalibracaoAdaptativa = field(default_factory=CalibracaoAdaptativa)
    
    def __post_init__(self):
        """Inicializa timestamp."""
        if not self.timestamp_geracao:
            self.timestamp_geracao = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "versao_protocolo": self.versao_protocolo,
            "timestamp_geracao": self.timestamp_geracao,
            "origem": self.origem,
            "instrumento": self.instrumento,
            "timeframe": self.timeframe,
            "sinal_quantitativo": {
                "direcao": self.sinal_quantitativo.direcao,
                "forca": self.sinal_quantitativo.forca,
                "confianca": self.sinal_quantitativo.confianca,
                "z_score": self.sinal_quantitativo.z_score,
                "percentil_z": self.sinal_quantitativo.percentil_z,
                "hurst": self.sinal_quantitativo.hurst,
                "regime": self.sinal_quantitativo.regime,
                "meia_vida_barras": self.sinal_quantitativo.meia_vida_barras,
                "meia_vida_minutos": self.sinal_quantitativo.meia_vida_minutos,
                "validade_ate": self.sinal_quantitativo.validade_ate,
            },
            "estatisticas_modelo": {
                "mu_t": self.estatisticas_modelo.mu_t,
                "theta": self.estatisticas_modelo.theta,
                "garch_sigma": self.estatisticas_modelo.garch_sigma,
                "omega": self.estatisticas_modelo.omega,
                "alpha": self.estatisticas_modelo.alpha,
                "beta": self.estatisticas_modelo.beta,
                "cv_theta": self.estatisticas_modelo.cv_theta,
            },
            "filtros_passados": self.filtros_passados,
            "candle_contexto": self.candle_contexto,
            "evidencias": self.evidencias,
            "riscos_estatisticos": {
                "forca_penalizada": self.riscos_estatisticos.forca_penalizada,
                "cv_theta_alto": self.riscos_estatisticos.cv_theta_alto,
                "reversao_confirmada": self.riscos_estatisticos.reversao_confirmada,
                "skewness_extrema": self.riscos_estatisticos.skewness_extrema,
            },
            "calibracao_adaptativa": {
                "threshold_adaptativo": self.calibracao_adaptativa.threshold_adaptativo,
                "trigger_rate_2sem": self.calibracao_adaptativa.trigger_rate_2sem,
            },
        }
    
    def to_json(self) -> str:
        """Converte para JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)


def criar_payload_neutro(
    instrumento: str = "",
    candle_contexto: Optional[Dict[str, Any]] = None,
    filtros_passados: Optional[List[str]] = None,
    evidencias: Optional[List[str]] = None,
    skewness_extrema: bool = False,
) -> PayloadMotor:
    """Cria payload NEUTRO conforme spec (8.6 ou falha de confirmação).
    
    Args:
        instrumento: Símbolo do instrumento
        candle_contexto: Contexto da barra
        filtros_passados: Lista de filtros que passaram
        evidencias: Evidências do sinal
        skewness_extrema: Flag para skewnes extrema (8.6)
        
    Returns:
        PayloadMotor com direcao/confianca = NEUTRO
    """
    return PayloadMotor(
        versao_protocolo="F5.0",
        timestamp_geracao="",  # Will be set in __post_init__
        origem="motor",
        instrumento=instrumento,
        timeframe="M30",
        sinal_quantitativo=SinalQuantitativo(
            direcao="NEUTRO",
            forca=0.0,
            confianca="NEUTRO",
        ),
        estatisticas_modelo=EstatisticasModelo(),
        filtros_passados=filtros_passados or [],
        candle_contexto=candle_contexto or {},
        evidencias=evidencias or ["Neutro - skewness extrema ou falha de confirmação"],
        riscos_estatisticos=RiscosEstatisticos(
            skewness_extrema=skewness_extrema  # Flag para 8.6
        ),
        calibracao_adaptativa=CalibracaoAdaptativa(),
    )


def montar_payload(
    direcao: str,
    forca: float,
    confianca: str,
    instrumento: str,
    z_score: Optional[float] = None,
    percentil_z: Optional[float] = None,
    hurst: Optional[float] = None,
    regime: Optional[str] = None,
    tau: Optional[float] = None,
    mu: Optional[float] = None,
    theta: Optional[float] = None,
    garch_sigma: Optional[float] = None,
    omega: Optional[float] = None,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    cv_theta: Optional[float] = None,
    candle_contexto: Optional[Dict[str, Any]] = None,
    filtros_passados: Optional[List[str]] = None,
    evidencias: Optional[List[str]] = None,
    forca_penalizada: bool = False,
    cv_theta_alto: bool = False,
    reversao_confirmada: bool = False,
    skewness_extrema: bool = False,
) -> PayloadMotor:
    """Monta payload conforme §3.11.
    
    Args:
        direcao: LONG, SHORT, ou NEUTRO
        forca: Força do sinal [0, 1]
        confianca: ALTA, MÉDIA, ou NEUTRO
        instrumento: Símbolo do instrumento
        z_score, percentil_z, hurst, regime: Estatísticas F4/F3
        tau: Meia-vida em barras (F3)
        mu, theta, garch_sigma, omega, alpha, beta, cv_theta: Parâmetros F3/F4
        candle_contexto: Contexto da barra OHLC
        filtros_passados: Lista de filtros que passaram
        evidencias: Evidências do sinal
        forca_penalizada, cv_theta_alto, reversao_confirmada, skewness_extrema: Flags de risco
        
    Returns:
        PayloadMotor in-memory
    """
    # Calcular meia-vida
    meia_vida_barras = tau
    meia_vida_minutos = tau * 30 if tau is not None else None
    
    # Calcular validade
    if meia_vida_minutos is not None:
        validade_ts = datetime.now(timezone.utc).timestamp() * 1000 + meia_vida_minutos * 60 * 1000
        validade_ate = datetime.fromtimestamp(validade_ts / 1000, tz=timezone.utc).isoformat()
    else:
        validade_ate = None
    
    return PayloadMotor(
        versao_protocolo="F5.0",
        timestamp_geracao="",  # Will be set in __post_init__
        origem="motor",
        instrumento=instrumento,
        timeframe="M30",
        sinal_quantitativo=SinalQuantitativo(
            direcao=direcao,
            forca=forca,
            confianca=confianca,
            z_score=z_score,
            percentil_z=percentil_z,
            hurst=hurst,
            regime=regime,
            meia_vida_barras=meia_vida_barras,
            meia_vida_minutos=meia_vida_minutos,
            validade_ate=validade_ate,
        ),
        estatisticas_modelo=EstatisticasModelo(
            mu_t=mu,
            theta=theta,
            garch_sigma=garch_sigma,
            omega=omega,
            alpha=alpha,
            beta=beta,
            cv_theta=cv_theta,
        ),
        filtros_passados=filtros_passados or [],
        candle_contexto=candle_contexto or {},
        evidencias=evidencias or [],
        riscos_estatisticos=RiscosEstatisticos(
            forca_penalizada=forca_penalizada,
            cv_theta_alto=cv_theta_alto,
            reversao_confirmada=reversao_confirmada,
            skewness_extrema=skewness_extrema,
        ),
        calibracao_adaptativa=CalibracaoAdaptativa(),
    )