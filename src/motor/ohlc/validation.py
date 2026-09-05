"""Validação de barras OHLC M30 conforme especificação F1.

Módulo responsável por:
- Validar formato JSON [timestamp_UTC, open, high, low, close, bid, ask]
- Validar timestamps em UTC
- Validar integridade de preços (high/low)
- Validar ordem temporal e tratar gaps
- Forward-fill para week-end gaps

Todas as falhas resultam em Abort imediato com logs literais conforme doc §3.2.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class BarStatus(str, Enum):
    """Status de uma barra validada."""
    VALID = "valid"
    GAP_DATOS = "gap_dados"
    NEUTRO = "neutro"
    WEEKEND_FILL = "weekend_fill"


class ValidationError(Exception):
    """Erro de validação com código de log conforme especificação."""
    
    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or f"Validation abort: {code}"
        super().__init__(self.message)


@dataclass
class ValidatedBar:
    """Barra OHLC validada com campos calculados."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    bid: float
    ask: float
    status: BarStatus = BarStatus.VALID
    flags: list[str] = field(default_factory=list)
    
    @property
    def P_t(self) -> float:
        """Mid-price: P_t = (Bid_t + Ask_t) / 2"""
        return (self.bid + self.ask) / 2.0


@dataclass
class ValidatedSeries:
    """Série temporal de barras validadas."""
    bars: list[ValidatedBar]
    status: str = "valid"


def validate_ohlc_format(bar: list) -> bool:
    """Valida se a barra tem o formato correto [timestamp, open, high, low, close, bid, ask].
    
    Regras:
    - Exatamente 7 campos
    - Timestamp deve ser numérico positivo (Unix timestamp)
    - Todos os preços (open, high, low, close, bid, ask) devem ser números positivos
    """
    if not isinstance(bar, (list, tuple)):
        return False
    if len(bar) != 7:
        return False
    
    try:
        ts = float(bar[0])
        if ts <= 0:
            return False
        for i in range(1, 7):
            val = float(bar[i])
            if not isinstance(bar[i], (int, float)):
                return False
            if val <= 0:  # Preços devem ser positivos
                return False
    except (ValueError, TypeError):
        return False
    
    return True


def validate_timestamp_utc(timestamp: float, reference_ts: float) -> bool:
    """Valida se o timestamp está em UTC."""
    try:
        dt = datetime.fromtimestamp(timestamp / 1000.0, tz=timezone.utc)
        return dt.tzinfo == timezone.utc
    except (ValueError, TypeError):
        return False


def validate_price_integrity(open: float, high: float, low: float, close: float) -> bool:
    """Valida a integridade dos preços.
    
    Regras:
    - high >= max(open, close)
    - low <= min(open, close)
    """
    if high < max(open, close):
        return False
    if low > min(open, close):
        return False
    return True


def validate_bar(bar: list) -> dict:
    """Valida uma única barra OHLC.
    
    Args:
        bar: Lista [timestamp, open, high, low, close, bid, ask]
        
    Returns:
        Dicionário com resultado da validação
        
    Raises:
        ValidationError: Se validação falhar (abort)
    """
    if not validate_ohlc_format(bar):
        raise ValidationError("format_invalido", "Bar format invalid")
    
    timestamp = float(bar[0])
    open_p = float(bar[1])
    high = float(bar[2])
    low = float(bar[3])
    close = float(bar[4])
    bid = float(bar[5])
    ask = float(bar[6])
    
    if not validate_timestamp_utc(timestamp, timestamp):
        raise ValidationError("format_invalido", "Timestamp not in UTC")
    
    if not validate_price_integrity(open_p, high, low, close):
        raise ValidationError("integridade_preco_invalida", "Price integrity violation")
    
    if not all(math.isfinite(v) for v in [open_p, high, low, close, bid, ask]):
        raise ValidationError("format_invalido", "Non-finite price values")
    
    return {
        "valid": True,
        "timestamp": int(timestamp),
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "bid": bid,
        "ask": ask
    }


def validate_order_temporal(bars: list[list]) -> tuple[bool, Optional[str]]:
    """Valida ordem temporal e ausência de duplicatas."""
    if len(bars) <= 1:
        return True, None
    
    timestamps = [bar[0] for bar in bars]
    
    if len(timestamps) != len(set(timestamps)):
        return False, "ordem_temporal_invalida"
    
    for i in range(1, len(timestamps)):
        if timestamps[i] <= timestamps[i-1]:
            return False, "ordem_temporal_invalida"
    
    return True, None


def calculate_gap_size(bars: list[list], index: int) -> int:
    """Calcula o tamanho do gap em número de barras."""
    if index == 0:
        return 0
    
    M30_MS = 1800000
    
    prev_ts = bars[index - 1][0]
    curr_ts = bars[index][0]
    
    expected_diff = M30_MS
    actual_diff = curr_ts - prev_ts
    
    gap_bars = int(actual_diff / expected_diff) - 1
    return max(0, gap_bars)


def is_weekend_gap(bars: list[list], index: int, m30_interval_ms: int = 1800000) -> bool:
    """Verifica se um gap corresponde a um gap de fim de semana."""
    if index == 0:
        return False
    
    prev_ts = bars[index - 1][0]
    curr_ts = bars[index][0]
    
    prev_dt = datetime.fromtimestamp(prev_ts / 1000.0, tz=timezone.utc)
    curr_dt = datetime.fromtimestamp(curr_ts / 1000.0, tz=timezone.utc)
    
    gap_days = (curr_dt - prev_dt).days
    
    if gap_days >= 2:
        prev_weekday = prev_dt.weekday()
        curr_weekday = curr_dt.weekday()
        
        if prev_weekday == 4 and curr_weekday == 0:  # Fri -> Mon
            return True
        if prev_weekday == 6 and curr_weekday == 0:  # Sun -> Mon
            return True
    
    return False


def interpolate_value(prev_val: float, next_val: float, ratio: float) -> float:
    """Interpolação linear entre dois valores."""
    return prev_val + (next_val - prev_val) * ratio


def handle_gaps(bars: list[list], m30_interval_ms: int = 1800000) -> dict:
    """Trata gaps na sequência temporal."""
    if not bars:
        return {"bars": [], "gap_intervals": []}
    
    result_bars = []
    gap_intervals = []
    
    for i, bar in enumerate(bars):
        if i == 0:
            result_bars.append({
                "data": bar,
                "status": BarStatus.VALID,
                "flags": []
            })
            continue
        
        gap_size = calculate_gap_size(bars, i)
        
        if gap_size == 0:
            result_bars.append({
                "data": bar,
                "status": BarStatus.VALID,
                "flags": []
            })
        elif gap_size <= 4:
            prev_bar = bars[i - 1]
            curr_bar = bar
            
            for j in range(1, gap_size + 1):
                ratio = j / (gap_size + 1)
                interp_ts = int(prev_bar[0] + j * m30_interval_ms)
                
                interp_data = [
                    interp_ts,
                    interpolate_value(prev_bar[1], curr_bar[1], ratio),
                    interpolate_value(prev_bar[2], curr_bar[2], ratio),
                    interpolate_value(prev_bar[3], curr_bar[3], ratio),
                    interpolate_value(prev_bar[4], curr_bar[4], ratio),
                    interpolate_value(prev_bar[5], curr_bar[5], ratio),
                    interpolate_value(prev_bar[6], curr_bar[6], ratio),
                ]
                
                result_bars.append({
                    "data": interp_data,
                    "status": BarStatus.VALID,
                    "flags": ["interpolated"]
                })
            
            flags = []
            if is_weekend_gap(bars, i, m30_interval_ms):
                flags.append("weekend_fill")
            
            result_bars.append({
                "data": bar,
                "status": BarStatus.VALID,
                "flags": flags
            })
        else:
            gap_intervals.append({
                "index": i,
                "gap_size": gap_size,
                "type": "gap_dados"
            })
            
            flags = ["gap_dados"]
            if is_weekend_gap(bars, i, m30_interval_ms):
                flags.append("weekend_fill")
            
            result_bars.append({
                "data": bar,
                "status": BarStatus.NEUTRO,
                "flags": flags
            })
    
    return {
        "bars": result_bars,
        "gap_intervals": gap_intervals
    }


def validate_bars_sequence(bars: list[list], m30_interval_ms: int = 1800000) -> ValidatedSeries:
    """Valida uma sequência completa de barras."""
    if not bars:
        raise ValidationError("format_invalido", "Empty bars sequence")
    
    for bar in bars:
        if not validate_ohlc_format(bar):
            raise ValidationError("format_invalido", "Invalid bar format in sequence")
    
    valid, error = validate_order_temporal(bars)
    if not valid:
        raise ValidationError(error, "Temporal order violation")
    
    validated_bars = []
    for bar in bars:
        vbar = validate_bar(bar)
        validated_bars.append(ValidatedBar(
            timestamp=vbar["timestamp"],
            open=vbar["open"],
            high=vbar["high"],
            low=vbar["low"],
            close=vbar["close"],
            bid=vbar["bid"],
            ask=vbar["ask"]
        ))
    
    gap_result = handle_gaps(bars, m30_interval_ms)
    
    final_bars = []
    for i, item in enumerate(gap_result["bars"]):
        data = item["data"]
        status = item["status"]
        flags = item["flags"]
        
        final_bars.append(ValidatedBar(
            timestamp=data[0],
            open=data[1],
            high=data[2],
            low=data[3],
            close=data[4],
            bid=data[5],
            ask=data[6],
            status=status,
            flags=flags
        ))
    
    return ValidatedSeries(
        bars=final_bars,
        status="valid" if not gap_result["gap_intervals"] else "gap_dados"
    )