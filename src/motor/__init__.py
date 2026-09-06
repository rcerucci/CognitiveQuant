"""Motor quantitativo - validacao OHLC + transform + filtros + regime.

Módulo principal que exporta:
- F1: Validação e transformação OHLC
- F2: Filtros de qualidade (spread, ADF, TR, Parkinson)
- F3: Regime (Hurst, OU, Bootstrap θ)
- F4: Volatilidade (GARCH, Z, percentil)
- F5: Sinal (confirmação, força, payload)
"""

__version__ = "0.1.0"

# Importar OHLC (F1)
from motor.ohlc import (
    validate_bar,
    validate_bars_sequence,
    validate_timestamp_utc,
    validate_price_integrity,
    validate_order_temporal,
    handle_gaps,
    validate_ohlc_format,
    ValidationError,
    BarStatus,
    ValidatedBar,
    ValidatedSeries,
    sync_instruments,
    SyncResult,
    transform_to_returns,
    transform_to_returns_dict,
    TransformResult,
    calculate_mid_price,
    calculate_log_price,
    calculate_log_return,
)

# Importar filtros (F2)
from motor.filters import (
    FilterSpread,
    FilterSpreadResult,
    FilterADF,
    FilterADFResult,
    FilterTR,
    FilterTRResult,
    FilterParkinson,
    FilterParkinsonResult,
    Pipeline,
    PipelineResult,
    FilterStatus,
)

# Importar regime (F3)
from motor.regime import (
    calculate_hurst,
    HurstResult,
    HurstStatus,
    RegimeType,
    estimate_ou_kalman,
    estimate_ou_mle,
    OUEstimationResult,
    OUStatus,
    bootstrap_theta,
    BootstrapResult,
    BootstrapStatus,
    F3Pipeline,
    F3PipelineResult,
    F3Status,
)

# Importar vol (F4)
from motor.vol import (
    GARCHResult,
    GARCHStatus,
    estimate_garch,
    estimate_garch_with_fallback,
    ZScoreResult,
    ZScoreStatus,
    calculate_zscore,
    PercentilResult,
    PercentilStatus,
    calculate_percentil_z,
    F4Pipeline,
    F4PipelineResult,
    F4Status,
    run_f4_pipeline,
)

# Importar signal (F5)
from motor.signal import (
    ConfirmacaoResult,
    ConfirmacaoStatus,
    ConfirmacaoDirection,
    calculate_confirmacao,
    ConfirmacaoMetrics,
    Direction,
    Confidence,
    ForcaResult,
    ForcaStatus,
    calcular_forca,
    ConfidenceLevel,
    classificar_confianca,
    PayloadMotor,
    SinalQuantitativo,
    EstatisticasModelo,
    RiscosEstatisticos,
    CalibracaoAdaptativa,
    criar_payload_neutro,
    montar_payload,
    F5Pipeline,
    F5PipelineResult,
    F5Status,
    run_f5_pipeline,
)

__all__ = [
    # OHLC validation (F1)
    "validate_bar",
    "validate_bars_sequence",
    "validate_timestamp_utc",
    "validate_price_integrity",
    "validate_order_temporal",
    "handle_gaps",
    "validate_ohlc_format",
    "ValidationError",
    "BarStatus",
    "ValidatedBar",
    "ValidatedSeries",
    # Sync (F1)
    "sync_instruments",
    "SyncResult",
    # Transform (F1)
    "transform_to_returns",
    "transform_to_returns_dict",
    "TransformResult",
    "calculate_mid_price",
    "calculate_log_price",
    "calculate_log_return",
    # Filters (F2)
    "FilterSpread",
    "FilterSpreadResult",
    "FilterADF",
    "FilterADFResult",
    "FilterTR",
    "FilterTRResult",
    "FilterParkinson",
    "FilterParkinsonResult",
    "Pipeline",
    "PipelineResult",
    "FilterStatus",
    # Regime (F3)
    "calculate_hurst",
    "HurstResult",
    "HurstStatus",
    "RegimeType",
    "estimate_ou_kalman",
    "estimate_ou_mle",
    "OUEstimationResult",
    "OUStatus",
    "bootstrap_theta",
    "BootstrapResult",
    "BootstrapStatus",
    "F3Pipeline",
    "F3PipelineResult",
    "F3Status",
    # Vol (F4)
    "GARCHResult",
    "GARCHStatus",
    "estimate_garch",
    "estimate_garch_with_fallback",
    "ZScoreResult",
    "ZScoreStatus",
    "calculate_zscore",
    "PercentilResult",
    "PercentilStatus",
    "calculate_percentil_z",
    "F4Pipeline",
    "F4PipelineResult",
    "F4Status",
    "run_f4_pipeline",
    # Signal (F5)
    "ConfirmacaoResult",
    "ConfirmacaoStatus",
    "ConfirmacaoDirection",
    "calculate_confirmacao",
    "ConfirmacaoMetrics",
    "Direction",
    "Confidence",
    "ForcaResult",
    "ForcaStatus",
    "calcular_forca",
    "ConfidenceLevel",
    "classificar_confianca",
    "PayloadMotor",
    "SinalQuantitativo",
    "EstatisticasModelo",
    "RiscosEstatisticos",
    "CalibracaoAdaptativa",
    "criar_payload_neutro",
    "montar_payload",
    "F5Pipeline",
    "F5PipelineResult",
    "F5Status",
    "run_f5_pipeline",
]