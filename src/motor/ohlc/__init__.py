"""Motor OHLC - validacao de barras M30."""

from motor.ohlc.validation import (
    validate_bar,
    validate_bars_sequence,
    validate_timestamp_utc,
    validate_price_integrity,
    validate_order_temporal,
    handle_gaps,
    validate_ohlc_format,
    is_weekend_gap,
    is_weekend_session_hole,
    ValidationError,
    BarStatus,
    ValidatedBar,
    ValidatedSeries,
)

from motor.ohlc.sync import (
    sync_instruments,
    SyncResult,
)

from motor.ohlc.transform import (
    transform_to_returns,
    transform_to_returns_dict,
    TransformResult,
    calculate_mid_price,
    calculate_log_price,
    calculate_log_return,
)

__all__ = [
    # Validation module
    "validate_bar",
    "validate_bars_sequence",
    "validate_timestamp_utc",
    "validate_price_integrity",
    "validate_order_temporal",
    "handle_gaps",
    "validate_ohlc_format",
    "is_weekend_gap",
    "is_weekend_session_hole",
    "ValidationError",
    "BarStatus",
    "ValidatedBar",
    "ValidatedSeries",
    # Sync module
    "sync_instruments",
    "SyncResult",
    # Transform module
    "transform_to_returns",
    "transform_to_returns_dict",
    "TransformResult",
    "calculate_mid_price",
    "calculate_log_price",
    "calculate_log_return",
]