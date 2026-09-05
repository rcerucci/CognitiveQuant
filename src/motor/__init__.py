"""Motor quantitativo - validacao OHLC + transform + filtros."""

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
]