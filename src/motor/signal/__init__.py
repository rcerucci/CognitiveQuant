"""Motor de sinal F5 - Confirmação + força + payload.

Módulo responsável por:
- Calcular confirmações de reversão (8.1-8.6)
- Determinar direção e força do sinal
- Classificar confiança (ALTA/MÉDIA/NEUTRO)
- Gerar payload JSON §3.11 in-memory

Input: F4 PASS (Z_t, percentil_z) + F3 (μ, θ, τ, H, regime, forca_penalty_cv) + F1 OHLC

Reference: Espec F5 §3.9-3.11
"""

__version__ = "0.1.0"

from motor.signal.confirmacao import (
    ConfirmacaoResult,
    ConfirmacaoStatus,
    calculate_confirmacao,
    ConfirmacaoMetrics,
    ConfirmacaoDirection,
)

from motor.signal.forca import (
    ForcaResult,
    calcular_forca,
    ForcaStatus,
    Direction,
    Confidence,
)

from motor.signal.thresholds import (
    classificar_confianca,
    ConfidenceLevel,
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

from motor.signal.pipeline import (
    F5Pipeline,
    F5PipelineResult,
    F5Status,
    run_f5_pipeline,
)

__all__ = [
    # Confirmacao
    "ConfirmacaoResult",
    "ConfirmacaoStatus",
    "calculate_confirmacao",
    "ConfirmacaoMetrics",
    "ConfirmacaoDirection",
    # Forca
    "ForcaResult",
    "calcular_forca",
    "ForcaStatus",
    "Direction",
    "Confidence",
    # Thresholds
    "classificar_confianca",
    "ConfidenceLevel",
    # Payload
    "PayloadMotor",
    "SinalQuantitativo",
    "EstatisticasModelo",
    "RiscosEstatisticos",
    "CalibracaoAdaptativa",
    "criar_payload_neutro",
    "montar_payload",
    # Pipeline
    "F5Pipeline",
    "F5PipelineResult",
    "F5Status",
    "run_f5_pipeline",
]