"""Independent Test US3: Filtro TR anômalo."""

import json
import pytest
import math
from pathlib import Path
from motor.filters.tr import FilterTR, FilterTRResult, FilterStatus
from motor.ohlc.validation import ValidatedBar, BarStatus

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/filters/tr.json"


@pytest.fixture
def tr_fixtures():
    """Carrega fixtures de TR."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


@pytest.fixture
def normal_tr_bars():
    """Cria barras com TR normal para testes."""
    bars = []
    for i in range(25):
        ts = 1704067200000 + i * 1800000
        # TR simples: H-L = 0.5, e sem gaps significativos
        bar = ValidatedBar(
            timestamp=ts,
            open=100.0 + i * 0.1,
            high=100.5 + i * 0.1,
            low=99.5 + i * 0.1,
            close=100.2 + i * 0.1,
            bid=100.0 + i * 0.1,
            ask=100.4 + i * 0.1,
            status=BarStatus.VALID
        )
        bars.append(bar)
    return bars


@pytest.fixture
def spike_tr_bars():
    """Cria barras com TR spike."""
    bars = []
    for i in range(21):
        ts = 1704067200000 + i * 1800000
        if i == 20:
            # Spike: gap muito grande
            bar = ValidatedBar(
                timestamp=ts,
                open=100.0,
                high=500.0,
                low=99.0,
                close=499.5,
                bid=100.0,
                ask=500.0,
                status=BarStatus.VALID
            )
        else:
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


@pytest.fixture
def weekend_fill_bars():
    """Cria barras incluindo weekend_fill."""
    bars = []
    for i in range(25):
        ts = 1704067200000 + i * 1800000
        
        # Barra de exemplo
        bar = ValidatedBar(
            timestamp=ts,
            open=100.0 + i * 0.1,
            high=100.5 + i * 0.1,
            low=99.5 + i * 0.1,
            close=100.2 + i * 0.1,
            bid=100.0 + i * 0.1,
            ask=100.4 + i * 0.1,
            status=BarStatus.VALID,
            flags=[] if i != 15 else ["weekend_fill"]  # Barra 15 é weekend_fill
        )
        bars.append(bar)
    return bars


class TestUS3TRFilter:
    """Testes para US3: Filtro TR anômalo."""
    
    def test_warm_up_neutro_with_less_than_20_tr_values(self, normal_tr_bars):
        """Warm-up < 20 TRs → NEUTRO automático."""
        # Usa apenas 15 barras (menos de 20)
        short_series = normal_tr_bars[:15]
        
        filtro = FilterTR(short_series)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO
        assert resultado.reason == "warm_up_infeasible"
    
    def test_tr_normal_pass(self, normal_tr_bars):
        """TR normal ≤ 2.5× média(20) → PASS."""
        filtro = FilterTR(normal_tr_bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.PASS
        assert resultado.TR is not None
        assert resultado.TR_ma20 is not None
        assert resultado.threshold is not None
    
    def test_tr_spike_neutro(self, spike_tr_bars):
        """TR spike > 2.5× média(20) → NEUTRO."""
        filtro = FilterTR(spike_tr_bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO
        assert resultado.reason == "tr_above_threshold"
        # Verificar que o spike foi detectado
        assert resultado.TR is not None
        assert resultado.TR_ma20 is not None
    
    def test_weekend_fill_not_counted_as_tr(self, weekend_fill_bars):
        """weekend_fill do F1 NÃO conta como TR observado."""
        filtro = FilterTR(weekend_fill_bars)
        resultado = filtro.run()
        
        # O filtro deve passar porque o TR foi calculado corretamente
        # excluindo o weekend_fill
        assert resultado.status in [FilterStatus.PASS, FilterStatus.NEUTRO]
    
    def test_from_fixture_tr_normal(self, tr_fixtures):
        """Teste com fixture TR normal."""
        test_case = next(tc for tc in tr_fixtures["test_cases"] 
                        if tc["name"] == "tr_normal")
        
        bars = []
        for bar_data in test_case["bars"]:
            # Verifica se tem flags
            flags = []
            # Para simplificar, não adicionamos flags aqui
            bar = ValidatedBar(
                timestamp=bar_data[0],
                open=bar_data[1],
                high=bar_data[2],
                low=bar_data[3],
                close=bar_data[4],
                bid=bar_data[5],
                ask=bar_data[6],
                status=BarStatus.VALID,
                flags=flags
            )
            bars.append(bar)
        
        filtro = FilterTR(bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.PASS
    
    def test_from_fixture_tr_spike(self, tr_fixtures):
        """Teste com fixture TR spike."""
        test_case = next(tc for tc in tr_fixtures["test_cases"] 
                        if tc["name"] == "tr_spike")
        
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
        
        filtro = FilterTR(bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO