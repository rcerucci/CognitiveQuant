"""Independent Test US1: Filtro de spread anômalo."""

import json
import pytest
import math
from pathlib import Path
from motor.filters.spread import FilterSpread, FilterSpreadResult, FilterStatus
from motor.ohlc.validation import ValidatedBar, BarStatus

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/filters/spread.json"


@pytest.fixture
def spread_fixtures():
    """Carrega fixtures de spread."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


@pytest.fixture
def normal_spread_bars():
    """Cria barras de spread normal para testes."""
    bars = []
    for i in range(25):
        ts = 1704067200000 + i * 1800000
        # Spread consistente de 0.4
        bar = ValidatedBar(
            timestamp=ts,
            open=100.0 + i * 0.1,
            high=100.5 + i * 0.1,
            low=99.5 + i * 0.1,
            close=100.2 + i * 0.1,
            bid=100.0 + i * 0.1,
            ask=100.4 + i * 0.1,  # spread = 0.4
            status=BarStatus.VALID
        )
        bars.append(bar)
    return bars


@pytest.fixture
def spike_spread_bars():
    """Cria barras com spike de spread."""
    bars = []
    for i in range(21):
        ts = 1704067200000 + i * 1800000
        if i == 20:
            # Spike: spread = 50
            bar = ValidatedBar(
                timestamp=ts,
                open=100.0,
                high=149.5,
                low=99.0,
                close=149.0,
                bid=100.0,
                ask=150.0,  # spread = 50
                status=BarStatus.VALID
            )
        else:
            # Spread normal de 0.4
            bar = ValidatedBar(
                timestamp=ts,
                open=100.0,
                high=100.5,
                low=99.5,
                close=100.2,
                bid=100.0,
                ask=100.4,
                status=BarStatus.VALID
            )
        bars.append(bar)
    return bars


class TestUS1SpreadFilter:
    """Testes para US1: Filtro de spread anômalo."""
    
    def test_warm_up_neutro_with_less_than_20_bars(self, normal_spread_bars):
        """Warm-up < 20 barras → NEUTRO automático."""
        # Usa apenas 15 barras (menos de 20)
        short_series = normal_spread_bars[:15]
        
        filtro = FilterSpread(short_series)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO
        assert resultado.reason == "warm_up_infeasible"
    
    def test_spread_normal_pass(self, normal_spread_bars):
        """Spread normal ≤ 2× média(20) → PASS."""
        filtro = FilterSpread(normal_spread_bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.PASS
        assert resultado.spread == pytest.approx(0.4, rel=1e-9)
        assert resultado.spread_ma20 == pytest.approx(0.4, rel=1e-9)
        assert resultado.threshold == pytest.approx(0.8, rel=1e-9)  # 2.0 * 0.4
    
    def test_spread_spike_neutro(self, spike_spread_bars):
        """Spread spike > 2× média(20) → NEUTRO."""
        filtro = FilterSpread(spike_spread_bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO
        assert resultado.reason == "spread_above_threshold"
        assert resultado.spread == pytest.approx(50.0, rel=1e-9)
    
    def test_from_fixture_spread_normal(self, spread_fixtures):
        """Teste com fixture spread normal."""
        test_case = next(tc for tc in spread_fixtures["test_cases"] 
                        if tc["name"] == "spread_normal")
        
        bars = []
        for bar_data in test_case["bars"]:
            bar = ValidatedBar(
                timestamp=bar_data[0],
                open=bar_data[1],
                high=bar_data[2],
                low=bar_data[3],
                close=bar_data[4],
                bid=bar_data[5],
                ask=bar_data[6],
                status=BarStatus.VALID
            )
            bars.append(bar)
        
        filtro = FilterSpread(bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.PASS
    
    def test_from_fixture_spread_spike(self, spread_fixtures):
        """Teste com fixture spread spike."""
        test_case = next(tc for tc in spread_fixtures["test_cases"] 
                        if tc["name"] == "spread_spike")
        
        bars = []
        for bar_data in test_case["bars"]:
            bar = ValidatedBar(
                timestamp=bar_data[0],
                open=bar_data[1],
                high=bar_data[2],
                low=bar_data[3],
                close=bar_data[4],
                bid=bar_data[5],
                ask=bar_data[6],
                status=BarStatus.VALID
            )
            bars.append(bar)
        
        filtro = FilterSpread(bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO