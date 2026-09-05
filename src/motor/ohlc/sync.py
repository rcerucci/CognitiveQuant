"""Sincronização multi-instrumento conforme especificação F1."""

from typing import Optional
from motor.ohlc.validation import ValidatedBar, BarStatus


class SyncResult:
    """Resultado da sincronizacao multi-instrumento."""
    
    def __init__(self, timestamps: list, instruments: dict, status: str = "valid"):
        self.timestamps = timestamps
        self.instruments = instruments
        self.status = status


def sync_instruments(instruments: dict) -> SyncResult:
    """Normaliza múltiplos instrumentos à mesma grade de timestamps."""
    if not instruments:
        return SyncResult(timestamps=[], instruments={})
    
    all_timestamps = set()
    for symbol, bars in instruments.items():
        for bar in bars:
            if bar and len(bar) >= 7:
                all_timestamps.add(bar[0])
    
    sorted_timestamps = sorted(all_timestamps)
    
    if not sorted_timestamps:
        return SyncResult(timestamps=[], instruments={})
    
    instrument_bars = {}
    for symbol, bars in instruments.items():
        ts_to_bar = {}
        for bar in bars:
            if bar and len(bar) >= 7:
                ts_to_bar[bar[0]] = bar
        instrument_bars[symbol] = ts_to_bar
    
    result_instruments = {}
    has_gaps = False
    
    for symbol, ts_to_bar in instrument_bars.items():
        aligned_bars = []
        prev_bar = None
        
        for ts in sorted_timestamps:
            if ts in ts_to_bar:
                bar_data = ts_to_bar[ts]
                aligned_bars.append(ValidatedBar(
                    timestamp=ts,
                    open=bar_data[1],
                    high=bar_data[2],
                    low=bar_data[3],
                    close=bar_data[4],
                    bid=bar_data[5],
                    ask=bar_data[6],
                    status=BarStatus.VALID,
                    flags=[]
                ))
                prev_bar = bar_data
            else:
                if prev_bar is not None:
                    interp_bar = _interpolate_missing_bar(prev_bar, ts, 0.5)
                    aligned_bars.append(interp_bar)
                    has_gaps = True
                else:
                    next_bar = None
                    for next_ts in sorted_timestamps:
                        if next_ts in ts_to_bar:
                            next_bar = ts_to_bar[next_ts]
                            break
                    
                    if next_bar:
                        aligned_bars.append(ValidatedBar(
                            timestamp=ts,
                            open=next_bar[1],
                            high=next_bar[2],
                            low=next_bar[3],
                            close=next_bar[4],
                            bid=next_bar[5],
                            ask=next_bar[6],
                            status=BarStatus.VALID,
                            flags=["forward_filled"]
                        ))
                    else:
                        has_gaps = True
        
        result_instruments[symbol] = aligned_bars
    
    status = "gap_dados" if has_gaps else "valid"
    
    return SyncResult(
        timestamps=sorted_timestamps,
        instruments=result_instruments,
        status=status
    )


def _interpolate_missing_bar(prev_bar: list, timestamp: int, ratio: float = 0.5) -> ValidatedBar:
    """Interpola uma barra faltante entre o bar anterior."""
    return ValidatedBar(
        timestamp=timestamp,
        open=prev_bar[1],
        high=prev_bar[2],
        low=prev_bar[3],
        close=prev_bar[4],
        bid=prev_bar[5],
        ask=prev_bar[6],
        status=BarStatus.VALID,
        flags=["interpolated"]
    )