"""Motor de filtros de qualidade (F2)."""

# Importar somente os módulos principais, não as classes para evitar circular imports
from motor.filters.spread import FilterSpread, FilterSpreadResult
from motor.filters.adf import FilterADF, FilterADFResult
from motor.filters.tr import FilterTR, FilterTRResult
from motor.filters.parkinson import FilterParkinson, FilterParkinsonResult
from motor.filters.pipeline import Pipeline, PipelineResult

# Definir FilterStatus como o do spread (primeiro na ordem de execução)
from motor.filters.spread import FilterStatus as _FilterStatus

__all__ = [
    "FilterSpread",
    "FilterSpreadResult",
    "FilterStatus",
    "FilterADF",
    "FilterADFResult",
    "FilterTR",
    "FilterTRResult",
    "FilterParkinson",
    "FilterParkinsonResult",
    "Pipeline",
    "PipelineResult",
]

# Alias para compatibilidade
FilterStatus = _FilterStatus