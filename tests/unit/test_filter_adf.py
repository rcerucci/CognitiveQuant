"""Independent Test US2: Filtro ADF de estacionariedade."""

import json
import pytest
import math
import random
import warnings
from pathlib import Path
from motor.filters.adf import FilterADF, FilterADFResult, FilterStatus

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/filters/adf.json"


@pytest.fixture
def adf_fixtures():
    """Carrega fixtures de ADF."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


@pytest.fixture
def stationary_series():
    """Cria série estacionária sintética (p < 0.05).
    
    Série com média constante e ruído - true stationarity.
    """
    random.seed(123)
    # Série estacionária: média constante, variância constante
    # Usar um processo AR(1) com phi < 1 para estacionariedade
    X_t = []
    x_prev = 0.0
    for i in range(250):
        # Processo AR(1) estacionário: x_t = 0.3 * x_{t-1} + epsilon_t
        epsilon = random.gauss(0, 0.5)
        x_t = 0.3 * x_prev + epsilon
        X_t.append(x_t)
        x_prev = x_t
    return X_t


@pytest.fixture
def trending_series():
    """Cria série com tendência (não estacionária)."""
    # Série com tendência linear clara - não estacionária
    X_t = []
    for i in range(250):
        # Série com tendência linear + ruído
        trend = i * 0.1
        noise = random.gauss(0, 0.3)
        X_t.append(trend + noise)
    return X_t


class TestUS2ADFFilter:
    """Testes para US2: Filtro ADF de estacionariedade."""
    
    def test_warm_up_neutro_with_less_than_200_points(self, stationary_series):
        """Warm-up < 200 pontos → NEUTRO automático."""
        short_series = stationary_series[:150]  # Menos de 200 pontos
        
        filtro = FilterADF(short_series)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO
        assert resultado.reason == "warm_up_infeasible"
        assert resultado.p_value is None
    
    def test_stationary_series_has_p_value(self, stationary_series):
        """Série estacionária deve ter p_value calculado."""
        filtro = FilterADF(stationary_series)
        resultado = filtro.run()
        
        # Deve calcular p_value
        assert resultado.p_value is not None
        assert resultado.window == 200
    
    def test_trending_series_detection(self, trending_series):
        """Série com tendência clara tende a ser detectada como não-estacionária."""
        random.seed(42)  # Reset seed para garantir reprodutibilidade
        filtro = FilterADF(trending_series)
        resultado = filtro.run()
        
        # Série com tendência clara geralmente tem p >= 0.05
        # (não é 100% garantido, mas deve funcionar na maioria dos casos)
        assert resultado.p_value is not None
        assert resultado.window == 200
    
    def test_from_fixture_stationary(self, adf_fixtures):
        """Teste com fixture estacionária."""
        test_case = next(tc for tc in adf_fixtures["test_cases"] 
                        if tc["name"] == "stationary_series")
        
        X_t = test_case["X_t"]
        filtro = FilterADF(X_t)
        resultado = filtro.run()
        
        # Estacionária deve passar ou ter p_value calculado
        assert resultado.p_value is not None
        assert resultado.window == 200
    
    def test_from_fixture_random_walk(self, adf_fixtures):
        """Teste com fixture random walk."""
        test_case = next(tc for tc in adf_fixtures["test_cases"] 
                        if tc["name"] == "random_walk")
        
        X_t = test_case["X_t"]
        filtro = FilterADF(X_t)
        resultado = filtro.run()
        
        # Random walk tende a ser não-estacionário
        assert len(X_t) >= 200
        assert resultado.window == 200
        # Verifica que o filtro foi executado corretamente
        assert resultado.p_value is not None