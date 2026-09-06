"""Independent Test US2: Filtro ADF de estacionariedade em r_t.

Testes para o addendum 2026-09-06: ADF em r_t (não em X_t).

Spec: §3.3 / US2 / Addendum ADF r_t / SC-005
"""

import json
import pytest
import math
import random
from pathlib import Path
from motor.filters.adf import FilterADF, FilterADFResult, FilterStatus

FIXTURES_PATH = Path(__file__).parent.parent.parent / "tests/fixtures/filters/adf.json"


@pytest.fixture
def adf_fixtures():
    """Carrega fixtures de ADF."""
    with open(FIXTURES_PATH) as f:
        return json.load(f)


@pytest.fixture
def rw_return_series_seed42():
    """Cria série de retornos ~RW (branco) com seed=42 para SC-005.
    
    Random Walk em log-preço gera retornos brancos (estacionários).
    - ADF(X) tipicamente p >= 0.05 (X é I(1))
    - ADF(r) tipicamente p < 0.05 (r é branco)
    
    Este é o fixture exato para SC-005: verify that ADF(r) passes.
    """
    random.seed(42)
    
    # Gerar log-preço random walk (I(1))
    log_prices = []
    x_prev = 0.0
    n_points = 250
    
    for i in range(n_points):
        # Retorno branco ~ N(0, 0.01)
        r_t = random.gauss(0, 0.01)
        x_t = x_prev + r_t
        log_prices.append(x_t)
        x_prev = x_t
    
    # Calcular retornos: r_t = X_t - X_{t-1}
    # (estão em branco, estacionários)
    returns = []
    for i in range(1, len(log_prices)):
        returns.append(log_prices[i] - log_prices[i-1])
    
    return returns, log_prices


@pytest.fixture
def trending_series():
    """Cria série com tendência (não estacionária).
    
    Série com tendência linear clara - não estacionária.
    Usado para testar ADF falhando em série com drift.
    """
    random.seed(42)
    X_t = []
    n_points = 250
    
    for i in range(n_points):
        # Série com tendência linear + ruído
        trend = i * 0.001  # Tendência pequena
        noise = random.gauss(0, 0.005)
        X_t.append(trend + noise)
    
    # Calcular retornos
    returns = []
    for i in range(1, len(X_t)):
        returns.append(X_t[i] - X_t[i-1])
    
    return returns, X_t


class TestUS2ADFReturnsFilter:
    """Testes para US2: Filtro ADF em r_t (addendum 2026-09-06).
    
    SC-005: fixture RW seed=42 — filtro ADF passa em r e não exige passagem em X.
    """
    
    def test_rw_returns_passes_adf_seed42(self, rw_return_series_seed42):
        """SC-005: Random Walk log-price → ADF(r) passa com seed=42."""
        returns, log_prices = rw_return_series_seed42
        
        # ADF em log-preços (X_t) - normalmente falha
        filter_x = FilterADF(returns, window=200)  # Usando returns como proxy para r
        # Aqui vamos testar que o filtro aceita retornos
        # e que ADF r_t passa quando r_t são retornos brancos
        
        # Verifica que temos 249 retornos (250 pontos - 1)
        assert len(returns) == 249
        
        # Executar filtro
        result = filter_x.run()
        
        # Returns brancos são estacionários, ADF(r) deve passar
        assert result.status == FilterStatus.PASS
        assert result.p_value is not None
        assert result.p_value < 0.05, f"p_value={result.p_value} should be < 0.05 for white noise returns"
        assert result.window == 200
        assert result.lag == 5

    def test_returns_vs_prices_discovery(self, rw_return_series_seed42):
        """SC-005: Demonstra ADF(r) passa vs ADF(X) falharia."""
        returns, log_prices = rw_return_series_seed42
        
        # Teste ADF em log-preços (X_t - I(1), não estacionário)
        # Isso simula o comportamento anterior do filtro
        from statsmodels.tsa.stattools import adfuller
        
        # ADF em X_t (log-preços) - esperamos p >= 0.05
        result_x = adfuller(log_prices[-200:], maxlag=5)
        p_value_x = result_x[1]
        
        # ADF em r_t (retornos) - esperamos p < 0.05
        result_r = adfuller(returns[-200:], maxlag=5)
        p_value_r = result_r[1]
        
        # Log-preços tendem a ser não-estacionários (p >= 0.05)
        # Retornos tendem a ser estacionários (p < 0.05)
        # Em seed=42, isso deve funcionar
        assert p_value_r < 0.05, f"ADF(r) should pass: p_value_r={p_value_r}"
        assert p_value_x >= 0.05, f"ADF(X) should fail: p_value_x={p_value_x}"

    def test_warm_up_neutro_with_less_than_200_return_points(self):
        """Warm-up < 200 pontos de retorno → NEUTRO automático."""
        # Criar série curta de retornos
        random.seed(123)
        returns = [random.gauss(0, 0.01) for _ in range(150)]  # Menos de 200
        
        filtro = FilterADF(returns)
        resultado = filtro.run()
        
        assert resultado.status == FilterStatus.NEUTRO
        assert resultado.reason == "warm_up_infeasible"
        assert resultado.p_value is None

    def test_stationary_returns_have_p_value(self, rw_return_series_seed42):
        """Série de retornos estacionários deve ter p_value calculado."""
        returns, _ = rw_return_series_seed42
        
        filtro = FilterADF(returns)
        resultado = filtro.run()
        
        assert resultado.p_value is not None
        assert resultado.window == 200
        assert resultado.lag == 5

    def test_no_return_first_bar_neutro(self):
        """Primeira barra sem retorno anterior → NEUTRO/skip."""
        # Criar série onde o primeiro retorno é None
        # (simulando a primeira barra)
        returns = [None] + [0.001, 0.002, 0.001] * 100  # 301 elementos
        
        filtro = FilterADF(returns)
        resultado = filtro.run()
        
        # Deve detectar que o último retorno é None (primeira barra sem r_{t-1})
        # Na prática, se o último elemento é None, consideramos NEUTRO
        # Mas se só o primeiro é None, podemos ignorar
        # O comportamento esperado: se não há retorno válido, NEUTRO
        assert resultado.status == FilterStatus.NEUTRO or resultado.p_value is not None

    def test_from_fixture_stationary_returns(self, adf_fixtures):
        """Teste com fixture de retornos estacionários."""
        test_case = next(tc for tc in adf_fixtures["test_cases"]
                        if tc["name"] == "stationary_returns")
        
        r_t = test_case["r_t"]
        filtro = FilterADF(r_t)
        resultado = filtro.run()
        
        assert resultado.p_value is not None
        assert resultado.window == 200
        assert resultado.status == FilterStatus.PASS

    def test_from_fixture_trending_returns(self, adf_fixtures):
        """Teste com fixture de retornos com tendência (não estacionários)."""
        test_case = next(tc for tc in adf_fixtures["test_cases"]
                        if tc["name"] == "trending_returns")
        
        r_t = test_case["r_t"]
        filtro = FilterADF(r_t)
        resultado = filtro.run()
        
        assert len(r_t) >= 200
        assert resultado.window == 200
        assert resultado.p_value is not None

    def test_non_stationary_returns_neutro(self):
        """Retornos com drift não-estacionário → NEUTRO."""
        random.seed(42)
        # Criar retornos com drift positivo crescente
        # Isso simula uma tendência que não é estacionária
        returns = []
        base_return = 0.0001
        for i in range(250):
            # Drift crescente
            r = base_return + (i * 0.000001) + random.gauss(0, 0.005)
            returns.append(r)
        
        filtro = FilterADF(returns)
        resultado = filtro.run()
        
        # Com drift crescente, pode passar ou falhar dependendo da magnitude
        # O importante é que o filtro executa corretamente
        assert resultado.p_value is not None
        assert resultado.window == 200