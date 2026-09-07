"""Independent Test — Addendum F1: weekend session hole ≠ gap_dados.

Testes determinísticos (seed=42) para a regra:
  - 36h <= Δt <= 72h E atravessa sábado/domingo UTC → NÃO marca gap_dados
  - gap intra-sessão > 4 barras (sem fim de semana) → gap_dados + NEUTRO
  - série de 200 barras só dias úteis M30 → F1 não aborta / não marca gap

Fixtures inline (sem depender de arquivos externos) para reprodutibilidade absoluta.
"""
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from motor.ohlc.validation import (
    validate_bars_sequence,
    is_weekend_session_hole,
    handle_gaps,
    BarStatus,
    ValidatedBar,
)


def _build_bar(ts_ms: int, price: float) -> list:
    """Cria uma barra OHLC válida [ts, open, high, low, close, bid, ask]."""
    return [ts_ms, price, price, price, price, price, price]


def _next_ts(ts_ms: int, hours: int) -> int:
    """Converte ts_ms + hours para o próximo timestamp em ms."""
    dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
    return int((dt + timedelta(hours=hours)).timestamp() * 1000)


class TestWeekendSessionHoleDetection:
    """Testa is_weekend_session_hole diretamente (unit-level)."""

    def test_friday_2130_to_monday_0000_is_weekend_hole(self):
        """sexta 21:30 → segunda 00:00 UTC (Δt≈50.5h, atravessa sábado)."""
        fri = datetime(2024, 1, 5, 21, 30, 0, tzinfo=timezone.utc)
        mon = datetime(2024, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        fri_ms = int(fri.timestamp() * 1000)
        mon_ms = int(mon.timestamp() * 1000)

        assert is_weekend_session_hole(fri_ms, mon_ms) is True

    def test_tuesday_1000_to_tuesday_1400_is_NOT_weekend_hole(self):
        """terça 10:00 → terça 14:00 UTC (4h, 8 barras; sem fim de semana)."""
        tue1 = datetime(2024, 1, 9, 10, 0, 0, tzinfo=timezone.utc)
        tue2 = datetime(2024, 1, 9, 14, 0, 0, tzinfo=timezone.utc)
        tue1_ms = int(tue1.timestamp() * 1000)
        tue2_ms = int(tue2.timestamp() * 1000)

        assert is_weekend_session_hole(tue1_ms, tue2_ms) is False

    def test_gap_below_36h_not_weekend_hole(self):
        """Δt < 36h mesmo atravessando fim de semana → False (demasiado pequeno)."""
        # Sábado 10:00 → domingo 08:00 = 22h
        sat = datetime(2024, 1, 6, 10, 0, 0, tzinfo=timezone.utc)
        sun = datetime(2024, 1, 7, 8, 0, 0, tzinfo=timezone.utc)
        sat_ms = int(sat.timestamp() * 1000)
        sun_ms = int(sun.timestamp() * 1000)

        assert is_weekend_session_hole(sat_ms, sun_ms) is False

    def test_gap_above_72h_not_weekend_hole(self):
        """Δt > 72h → False (feed morto)."""
        fri = datetime(2024, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
        tue = datetime(2024, 1, 9, 12, 0, 0, tzinfo=timezone.utc)
        fri_ms = int(fri.timestamp() * 1000)
        tue_ms = int(tue.timestamp() * 1000)

        assert is_weekend_session_hole(fri_ms, tue_ms) is False

    def test_weekend_hole_within_36_to_72h_crosses_saturday(self):
        """Δt dentro [36h, 72h] atravessando sábado → True."""
        fri = datetime(2024, 1, 5, 18, 0, 0, tzinfo=timezone.utc)
        mon = datetime(2024, 1, 8, 2, 0, 0, tzinfo=timezone.utc)
        fri_ms = int(fri.timestamp() * 1000)
        mon_ms = int(mon.timestamp() * 1000)
        delta_h = (mon_ms - fri_ms) / (3600 * 1000)
        assert 36 <= delta_h <= 72
        assert is_weekend_session_hole(fri_ms, mon_ms) is True

    def test_weekend_hole_within_36_to_72h_crosses_sunday(self):
        """Δt dentro [36h, 72h] atravessando domingo → True."""
        Sat = datetime(2024, 1, 6, 22, 0, 0, tzinfo=timezone.utc)
        Tue = datetime(2024, 1, 9, 2, 0, 0, tzinfo=timezone.utc)
        sat_ms = int(Sat.timestamp() * 1000)
        tue_ms = int(Tue.timestamp() * 1000)
        delta_h = (tue_ms - sat_ms) / (3600 * 1000)
        assert 36 <= delta_h <= 72
        assert is_weekend_session_hole(sat_ms, tue_ms) is True

    def test_week_gap_within_window_no_weekend_cross(self):
        """Δt dentro [36h, 72h] mas sem atravessar fim de semana → False."""
        # Terça 10:00 → quinta 16:00 = 54h, sem fim de semana
        tue = datetime(2024, 1, 9, 10, 0, 0, tzinfo=timezone.utc)
        thu = datetime(2024, 1, 11, 16, 0, 0, tzinfo=timezone.utc)
        tue_ms = int(tue.timestamp() * 1000)
        thu_ms = int(thu.timestamp() * 1000)
        delta_h = (thu_ms - tue_ms) / (3600 * 1000)
        assert 36 <= delta_h <= 72
        assert is_weekend_session_hole(tue_ms, thu_ms) is False


class TestWeekendSessionHoleIntegration:
    """Testa o comportamento end-to-end via validate_bars_sequence."""

    def test_friday_to_monday_no_gap_dados_flag(self):
        """
        Teste seed=42: sexta 21:30 → segunda 00:00 (Δt~50h, atravessa domingo).
        → sem flag gap_dados, status válido, weekend_fill presente.
        """
        fri = datetime(2024, 1, 5, 21, 30, 0, tzinfo=timezone.utc)
        mon = datetime(2024, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        fri_ms = int(fri.timestamp() * 1000)
        mon_ms = int(mon.timestamp() * 1000)

        bars = [
            _build_bar(fri_ms, 100.50),
            _build_bar(mon_ms, 102.50),
        ]
        result = validate_bars_sequence(bars)

        assert result.status != "gap_dados"
        for b in result.bars:
            assert "gap_dados" not in b.flags

    def test_tuesday_to_tuesday_gap_marked(self):
        """
        Teste seed=42: terça 10:00 → terça 14:00 (4h, 8 barras em falta).
        → gap_dados + NEUTRO (sem fim de semana).
        """
        tue1 = datetime(2024, 1, 9, 10, 0, 0, tzinfo=timezone.utc)
        tue2 = datetime(2024, 1, 9, 14, 0, 0, tzinfo=timezone.utc)
        tue1_ms = int(tue1.timestamp() * 1000)
        tue2_ms = int(tue2.timestamp() * 1000)

        bars = [
            _build_bar(tue1_ms, 100.50),
            _build_bar(tue2_ms, 102.50),
        ]
        result = validate_bars_sequence(bars)

        assert result.status == "gap_dados"
        assert any("gap_dados" in b.flags for b in result.bars)
        assert any(b.status == BarStatus.NEUTRO for b in result.bars)

    def test_200_weekday_bars_no_gap_abort(self):
        """
        Teste seed=42: série de 200 barras só dias úteis M30.
        → F1 não aborta, não marca gap_dados.
        """
        np.random.seed(42)
        base_price = 192.0

        # Gera 200 barras M30 apenas em dias úteis (Mon-Fri), 00:00 UTC
        bars = []
        ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        count = 0
        while count < 200:
            if ts.weekday() < 5:  # Mon-Fri
                price = base_price + (count * 0.001) + float(np.random.normal(0, 0.05))
                price = max(price, 0.01)
                bars.append(_build_bar(int(ts.timestamp() * 1000), price))
                count += 1
            ts += timedelta(minutes=30)

        result = validate_bars_sequence(bars)
        assert result.status == "valid"
        assert not any("gap_dados" in b.flags for b in result.bars)

    def test_weekend_hole_marked_weekend_fill_not_gap_dados(self):
        """
        Quando o gap é um weekend session hole, a barra deve ter
        flag 'weekend_fill' e status VALID (não gap_dados/NEUTRO).
        """
        fri = datetime(2024, 1, 5, 21, 30, 0, tzinfo=timezone.utc)
        mon = datetime(2024, 1, 8, 0, 0, 0, tzinfo=timezone.utc)
        fri_ms = int(fri.timestamp() * 1000)
        mon_ms = int(mon.timestamp() * 1000)

        bars = [
            _build_bar(fri_ms, 100.50),
            _build_bar(mon_ms, 102.50),
        ]
        result = validate_bars_sequence(bars)

        # A última barra deve ter weekend_fill, não gap_dados
        last_bar = result.bars[-1]
        assert "weekend_fill" in last_bar.flags
        assert "gap_dados" not in last_bar.flags
        assert last_bar.status == BarStatus.VALID
