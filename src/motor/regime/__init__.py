"""Motor de regime/F3 - Hurst, OU, Bootstrap θ.

Módulo responsável por:
- Calcular Hurst (R/S) para classificar regime
- Estimar processo OU via Kalman com fallback MLE
- Bootstrap IID para medir estabilidade de θ
"""

__version__ = "0.1.0"

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
)

__all__ = [
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
]