"""Motor de volatilidade F4 - GARCH + Z + percentil.

Módulo responsável por:
- Estimar volatilidade condicional GARCH(1,1)
- Calcular Z-score condicional
- Calcular percentil empírico de |Z|

Input: F3 PASS (μ_t, X_t, r_t)
Saída: ResultadoF4 (in-memory) - garch_sigma, Z_t, percentil_z, fonte
"""

__version__ = "0.1.0"

from motor.vol.garch import (
    GARCHResult,
    GARCHStatus,
    estimate_garch,
    estimate_garch_with_fallback,
)

from motor.vol.zscore import (
    ZScoreResult,
    ZScoreStatus,
    calculate_zscore,
)

from motor.vol.percentil import (
    PercentilResult,
    PercentilStatus,
    calculate_percentil_z,
)

from motor.vol.pipeline import (
    F4Pipeline,
    F4PipelineResult,
    F4Status,
    run_f4_pipeline,
)

__all__ = [
    # GARCH
    "GARCHResult",
    "GARCHStatus",
    "estimate_garch",
    "estimate_garch_with_fallback",
    # Z-score
    "ZScoreResult",
    "ZScoreStatus",
    "calculate_zscore",
    # Percentil
    "PercentilResult",
    "PercentilStatus",
    "calculate_percentil_z",
    # Pipeline
    "F4Pipeline",
    "F4PipelineResult",
    "F4Status",
    "run_f4_pipeline",
]