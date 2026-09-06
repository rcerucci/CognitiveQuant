"""Motor de regime/F3 - Hurst, OU, Bootstrap θ.

Módulo responsável por:
- Calcular Hurst (R/S) para classificar regime
- Estimar processo OU via Kalman com fallback MLE
- Moving Block Bootstrap para medir estabilidade de θ
- Pipeline completo com gate θ̂>0 ∧ IC_low>0 ∧ IC_low<θ̂ ∧ 1≤τ≤20 ∧ ADF(X_t) p<0.05 (003b)

T027-T033 (hotfix 003b): Gate de regime baseado em θ̂, IC_low, τ, ADF(X_t)
"""

__version__ = "0.1.0"

# Constante K = 20 barras M30 (lock Marcos 003b)
K_HALF_LIFE_BARS = 20

from motor.regime.hurst import (
    calculate_hurst,
    HurstResult,
    HurstStatus,
    RegimeType,
)

from motor.regime.ou import (
    estimate_ou_kalman,
    estimate_ou_mle,
    OUEstimationResult,
    OUStatus,
)

from motor.regime.bootstrap_theta import (
    bootstrap_theta,
    BootstrapResult,
    BootstrapStatus,
)

from motor.regime.pipeline import (
    F3Pipeline,
    F3PipelineResult,
    F3Status,
    K_HALF_LIFE_BARS as PIPELINE_K_HALF_LIFE_BARS,
)

__all__ = [
    # Constantes
    "K_HALF_LIFE_BARS",
    # Hurst
    "calculate_hurst",
    "HurstResult",
    "HurstStatus",
    "RegimeType",
    # OU
    "estimate_ou_kalman",
    "estimate_ou_mle",
    "OUEstimationResult",
    "OUStatus",
    # Bootstrap
    "bootstrap_theta",
    "BootstrapResult",
    "BootstrapStatus",
    # Pipeline
    "F3Pipeline",
    "F3PipelineResult",
    "F3Status",
    "PIPELINE_K_HALF_LIFE_BARS",
]