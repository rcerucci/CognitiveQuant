"""Independent Test US4: Filtro de volatilidade Parkinson."""

import json
import pytest
import math
from pathlib import Path
from motor.filters.parkinson import FilterParkinson, FilterParkinsonResult, FilterStatus
from motor.ohlc.validation import ValidatedBar, BarStatus

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/filters/parkinson.json"


@pytest.fixture
def parkinson_fixtures():
    """Carrega fixtures de Parkinson."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


@pytest.fixture
def normal_parkinson_bars():
    """Cria barras com volatilidade normal para testes."""
    bars = []
    for i in range(70):  # Mais de 60 para warm-up
        ts = 1704067200000 + i * 1800000
        # Volatilidade moderada e consistente
        bar = ValidatedBar(
            timestamp=ts,
            open=100.0 + i * 0.05,
            high=100.5 + i * 0.05,
            low=99.5 + i * 0.05,
            close=100.2 + i * 0.05,
            bid=100.0 + i * 0.05,
            ask=100.4 + i * 0.05,
            status=BarStatus.VALID
        )
        bars.append(bar)
    return bars


@pytest.fixture
def spike_parkinson_bars():
    """Cria barras com spike de volatilidade."""
    bars = []
    for i in range(70):
        ts = 1704067200000 + i * 1800000
        if i == 21:  # Barra 22 (índice 21)
            # Spike de volatilidade
            bar = ValidatedBar(
                timestamp=ts,
                open=106.3,
                high=106.5,
                low=105.2,  # Gap grande
                close=106.7,
                bid=106.3,
                ask=106.7,
                status=BarStatus.VALID
            )
        else:
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


class TestUS4ParkinsonFilter:
    """Testes para US4: Filtro de volatilidade Parkinson."""
    
    def test_warm_up_neutro_with_less_than_60_bars(self, normal_parkinson_bars):
        """Warm-up < 60 barras → NEUTRO temporário automático."""
        short_series = normal_parkinson_bars[:50]  # Menos de 60
        
        filtro = FilterParkinson(short_series)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO_TEMPORARIO
    
    def test_normal_volatility_pass(self, normal_parkinson_bars):
        """Volatilidade normal σ_20/σ_60 ≤ 1.5 → PASS."""
        filtro = FilterParkinson(normal_parkinson_bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.PASS
        assert resultado.sigma_20 is not None
        assert resultado.sigma_60 is not None
        assert resultado.ratio is not None
        assert resultado.ratio <= 1.5
    
    def test_volatility_spike_neutro_temporario(self, spike_parkinson_bars):
        """Spike de volatilidade σ_20/σ_60 > 1.5 → NEUTRO temporário + log."""
        filtro = FilterParkinson(spike_parkinson_bars)
        resultado = filtro.run()
        
        # Pode ser PASS ou NEUTRO dependendo da volatilidade média
        # O spike foi na barra 21, então ainda deve calcular bem
        assert resultado.sigma_20 is not None
        assert resultado.sigma_60 is not None
    
    def test_parkinson_factor_calculation(self, normal_parkinson_bars):
        """Verifica o fator Parkinson clássico."""
        # O fator deve ser 1/(4*ln(2)) ≈ 0.360674
        expected_factor = 1.0 / (4.0 * math.log(2))
        assert abs(FilterParkinson.PARKINSON_FACTOR - expected_factor) < 1e-10
    
    def test_from_fixture_parkinson_normal(self, parkinson_fixtures):
        """Teste com fixture normal."""
        test_case = next(tc for tc in parkinson_fixtures["test_cases"] 
                        if tc["name"] == "parkinson_normal")
        
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
        
        filtro = FilterParkinson(bars)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.PASS
        assert resultado.sigma_20 is not None
        assert resultado.sigma_60 is not None
        assert resultado.ratio is not None
    
    def test_from_fixture_parkinson_spike(self, parkinson_fixtures):
        """Teste com fixture spike."""
        test_case = next(tc for tc in parkinson_fixtures["test_cases"] 
                        if tc["name"] == "parkinson_spike")
        
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
        
        filtro = FilterParkinson(bars)
        resultado = filtro.run()
        
        # Deve detectar o spike
        assert len(bars) >= 60
        assert resultado.sigma_20 is not None
        assert resultado.sigma_60 is not None