"""Independent Test — F2 weekend_fill não dispara series_has_gaps; TR index alinhado.

Testes seed=42 para as correções no pipeline F2:
1) Janela 200 com um furo Fri→Mon (~50h, atravessa fim de semana) → _check_gap_dados() == False
2) Mesmo + furo terça intra-sessão (gap_dados) → _check_gap_dados() == True
3) FilterTR 200 barras, 5 weekend_fill, index=199 → não rebenta
4) Testes ohlc de weekend continuam verdes
"""
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from motor.ohlc.validation import validate_bars_sequence
from motor.filters.pipeline import Pipeline
from motor.filters.tr import FilterTR, FilterStatus as TRStatus


def _build_bar(ts_ms: int, price: float) -> list:
    """Cria uma barra OHLC válida [ts, open, high, low, close, bid, ask]."""
    return [ts_ms, price, price, price, price, price, price]


def _make_weekday_series(count, start_dt, seed=42):
    """Gera `count` barras M30 apenas em dias úteis (Mon-Fri).

    Quando encontra fim de semana, pula para segunda-feira 00:00 UTC seguinte.
    O gap resultante (Fri→Mon) dura ~48-54h e atravessa Sat/Sun.
    """
    np.random.seed(seed)
    bars = []
    ts = start_dt
    price = 100.0
    while len(bars) < count:
        if ts.weekday() < 5:  # Mon-Fri
            price += float(np.random.normal(0, 0.1))
            price = max(price, 0.01)
            bars.append(_build_bar(int(ts.timestamp() * 1000), price))
            ts += timedelta(minutes=30)
        else:
            # Pula para segunda-feira 00:00 UTC
            ts = ts + timedelta(days=(7 - ts.weekday()))
            ts = ts.replace(hour=0, minute=0, second=0, microsecond=0)
    return bars

class TestF2CheckGapDatosIgnoresWeekendFill:
    """Tests que weekend_fill não dispara series_has_gaps no pipeline F2."""

    def test_window_200_with_one_friday_monday_gap_no_gap_dados(self):
        """Janela 200 com um furo Fri→Mon (~50h, atravessa fim de semana).

        Começa em sexta-feira de tarde para garantir que 200 barras
        de dias úteis cruazam pelo menos um fim de semana.
        → _check_gap_dados() must be False; series status != gap_dados.
        """
        # Começa em sexta-feira 5 de janeiro de 2024, 10:00 UTC
        # 200 M30 bars = 100h = ~4.2 weekdays
        # Começando sexta 10:00, dura até ~terça da próxima semana
        # → cruza um fim de semana (Fri→Mon)
        start = datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
        bars = _make_weekday_series(200, start, seed=42)
        series = validate_bars_sequence(bars)

        # Verifica que o gap de fim de semana foi marcado como weekend_fill
        weekend_bars = [b for b in series.bars if b.flags and "weekend_fill" in b.flags]
        gap_bars = [b for b in series.bars if b.flags and "gap_dados" in b.flags]

        assert len(weekend_bars) >= 1, "Deve ter pelo menos um weekend_fill"
        assert len(gap_bars) == 0, "Nenhuma barra deve ter gap_dados"

        pipeline = Pipeline(series.bars)
        assert pipeline._check_gap_dados() is False
        assert series.status != "gap_dados"

    def test_window_200_with_friday_monday_and_tuesday_gap_has_gap_dados(self):
        """Mesma janela + um furo intra-sessão (gap_dados real).

        → _check_gap_dados() must be True.
        """
        start = datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc)

        # Gera 205 barras de dias úteis, mas pula 8 intervalos M30
        # no índice 10 (terça-feira de manhã) para criar gap_dados
        np.random.seed(42)
        bars = []
        ts = start
        price = 100.0
        bar_idx = 0
        while len(bars) < 205:
            if ts.weekday() < 5:
                price += float(np.random.normal(0, 0.1))
                price = max(price, 0.01)
                bars.append(_build_bar(int(ts.timestamp() * 1000), price))
                # Injeta gap intra-sessão no índice 10
                if bar_idx == 10:
                    ts += timedelta(minutes=30 * 9)  # pula 8 barras + 1 normal
                else:
                    ts += timedelta(minutes=30)
                bar_idx += 1
            else:
                ts = ts + timedelta(days=(7 - ts.weekday()))
                ts = ts.replace(hour=0, minute=0, second=0, microsecond=0)

        series = validate_bars_sequence(bars)
        pipeline = Pipeline(series.bars)

        gap_bars = [b for b in series.bars if b.flags and "gap_dados" in b.flags]
        assert len(gap_bars) >= 1, "Deve ter gap_dados do buraco intra-sessão"
        assert pipeline._check_gap_dados() is True

    def test_weekend_fill_bars_do_not_set_status_gap_dados(self):
        """Barras weekend_fill têm status VALID, não gap_dados."""
        fri = datetime(2024, 1, 5, 21, 30, 0, tzinfo=timezone.utc)
        mon = datetime(2024, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        fri_ms = int(fri.timestamp() * 1000)
        mon_ms = int(mon.timestamp() * 1000)

        bars = [
            _build_bar(fri_ms, 100.50),
            _build_bar(mon_ms, 102.50),
        ]
        series = validate_bars_sequence(bars)
        pipeline = Pipeline(series.bars)

        assert series.status != "gap_dados"
        assert pipeline._check_gap_dados() is False


class TestF2FilterTRWeekendFillSafe:
    """Tests que FilterTR não rebenta com weekend_fill e index alinhado."""

    def test_tr_with_weekend_fills_index_199_no_error(self):
        """FilterTR 200 barras com weekend_fills, index=199 → não rebenta."""
        # Começa sexta-feira para garantir um fim de semana no meio
        start = datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
        bars = _make_weekday_series(200, start, seed=42)
        series = validate_bars_sequence(bars)
        validated = series.bars

        weekend_fills = [b for b in validated if b.flags and "weekend_fill" in b.flags]
        assert len(weekend_fills) >= 1, f"Deve ter weekend_fills (tem {len(weekend_fills)})"

        # Executa FilterTR com index=199 (última barra)
        tr_filter = FilterTR(validated, index=199)
        result = tr_filter.run()

        assert result is not None
        assert result.status in (TRStatus.PASS, TRStatus.NEUTRO)
        assert result.TR is not None
        assert result.TR_ma20 is not None

    def test_tr_with_weekend_fill_at_index_position(self):
        """Se a barra na posição do índice for weekend_fill,
        TR usa o último valor válido — sem IndexError."""
        # Gera 200 barras de dias úteis começando sexta-feira
        start = datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
        bars = _make_weekday_series(200, start, seed=42)
        series = validate_bars_sequence(bars)
        validated = series.bars

        # Encontra o último weekend_fill na lista
        wf_indices = [i for i, b in enumerate(validated) if b.flags and "weekend_fill" in b.flags]
        assert len(wf_indices) >= 1

        # Usa o último weekend_fill como índice
        last_wf_idx = wf_indices[-1]
        tr_filter = FilterTR(validated, index=last_wf_idx)
        result = tr_filter.run()

        assert result is not None
        assert result.status in (TRStatus.PASS, TRStatus.NEUTRO)

    def test_tr_default_index_negative(self):
        """index=-1 (default) usa a última barra válida sem IndexError."""
        start = datetime(2024, 1, 5, 10, 0, 0, tzinfo=timezone.utc)
        bars = _make_weekday_series(205, start, seed=42)
        series = validate_bars_sequence(bars)
        validated = series.bars

        tr_filter = FilterTR(validated)  # index defaults to -1
        result = tr_filter.run()

        assert result is not None
        assert result.status in (TRStatus.PASS, TRStatus.NEUTRO)


class TestOHLCWeekendTestsStillGreen:
    """Confirma que os testes ohlc existentes de weekend continuam verdes."""

    def test_existing_weekend_gap_test_still_passes(self):
        """Reproduz o teste existente de test_ohlc_order_gaps.py."""
        bars = [
            [1704495600000, 100.50, 101.00, 100.25, 100.75, 100.50, 101.00],
            [1704672000000, 102.50, 103.00, 102.25, 102.75, 102.50, 103.00]
        ]
        result = validate_bars_sequence(bars)
        weekend_filled = [b for b in result.bars if "weekend_fill" in b.flags]
        assert len(weekend_filled) >= 1
