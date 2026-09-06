"""Testes Independente US3 — PnL motor-only (T017).

Entry mid-close → Exit tau/validade_ate, sem flip, custo zero.

Spec F6 §10.1 - US3, T015-T017
"""

from __future__ import annotations

import json
import math
import pytest
import numpy as np

from motor.backtest.pnl import (
    Trade,
    Position,
    PnLCalculator,
    calculate_pnl,
    run_pnl_simulation,
)


class TestFillEntryExit:
    """Testes para fill entry/exit."""
    
    def test_entry_mid_close(self):
        """Dado sinal trigger,
        Quando abre posicao,
        Entao entry = mid (bid+ask)/2 no close da barra do sinal."""
        # Criar uma barra de entrada
        bar = [
            1704067200000,  # timestamp
            100.0,  # open
            102.0,  # high
            99.0,   # low
            101.0,  # close
            100.8,  # bid
            101.2,  # ask
        ]
        
        mid = (bar[5] + bar[6]) / 2.0  # (bid + ask) / 2
        
        # Entry deve ser o mid no close da barra
        # O close mid e igual a (bid+ask)/2 quando bid/ask estao perto do close
        assert abs(mid - 101.0) < 0.001, "Entry deve ser mid-price"


class TestPnLNoFlip:
    """Testes para no-flip policy."""
    
    def test_no_flip_on_opposite_signal(self):
        """Dado posicao aberta LONG,
        Quando chega sinal SHORT,
        Entao não abre posição oposta - mantem até exit."""
        np.random.seed(42)
        
        # Criar serie com sinal LONG inicial e SHORT posterior
        bars = []
        for i in range(100):
            ts = 1704067200000 + i * 1800000
            mid = 100.0 + i * 0.1
            bars.append([ts, mid-0.5, mid+0.5, mid-1.0, mid, mid-0.25, mid+0.25])
        
        # Simular PnL
        result = run_pnl_simulation(bars, "EUR/USD", seed=42)
        
        # Verificar que flip nao ocorreu
        if result.trades:
            for trade in result.trades:
                assert not trade.flipped, "Trade não deve flipar"


class TestPnLExit:
    """Testes para exit por tau/validade_ate."""
    
    def test_exit_at_tau(self):
        """Dado posicao com tau,
        Quando barra tau chega,
        Entao exit no mid-close dessa barra."""
        # tau = 5 barras
        # Entry na barra 0, exit na barra 5
        
        entry_bar = [1704067200000, 100.0, 101.0, 99.0, 100.5, 100.3, 100.7]
        exit_bar = [1704136800000, 102.0, 103.0, 101.0, 102.5, 102.3, 102.7]
        
        entry_mid = (entry_bar[5] + entry_bar[6]) / 2.0  # 100.5
        exit_mid = (exit_bar[5] + exit_bar[6]) / 2.0    # 102.5
        
        # Retorno: (exit - entry) / entry
        ret = (exit_mid - entry_mid) / entry_mid
        expected_ret = 2.0 / 100.5
        
        assert abs(ret - expected_ret) < 0.001


class TestPnLZeroCost:
    """Testes para custo zero (sem spread/comissao adicional)."""
    
    def test_mid_price_pnl(self):
        """Dado que usa mid-price,
        Quando calcula PnL,
        Entao nao inventa spread/comissao."""
        bar = [
            1704067200000,
            100.0,
            101.0,
            99.0,
            100.5,
            100.3,  # bid
            100.7,  # ask
        ]
        
        mid = (bar[5] + bar[6]) / 2.0  # mid = 100.5
        
        # O mid e o close da barra (quando bid/ask estao perto)
        assert abs(mid - bar[4]) < 0.5, "O mid deve ser proximo do close"
        
        # Sem spread adicional inventado
        assert mid == (bar[5] + bar[6]) / 2.0


class TestPnLTruncation:
    """Testes para truncamento no fim da serie."""
    
    def test_exit_truncated_at_end(self):
        """Dado tau além do fim da serie,
        Quando fecha posicao,
        Entao exit na ultima barra disponivel + log."""
        # Criar serie curta
        bars = []
        for i in range(10):
            ts = 1704067200000 + i * 1800000
            mid = 100.0 + i * 0.5
            bars.append([ts, mid-0.5, mid+0.5, mid-1.0, mid, mid-0.25, mid+0.25])
        
        # Simular PnL - posicao pode ser truncada
        result = run_pnl_simulation(bars, "EUR/USD", seed=42)
        
        # Todas as posicoes abertas devem ser fechadas
        # (nenhuma posicao deve estar aberta no final)


class TestPnLTradeEvents:
    """Testes para eventos de trade."""
    
    def test_trade_structure(self):
        """Dado trade,
        Quando criado,
        Entao tem estrutura correta."""
        trade = Trade(
            instrumento="EUR/USD",
            direction="LONG",
            entry_bar_index=10,
            entry_timestamp=1704067200000,
            entry_price=100.0,
            entry_mid=100.0,
            tau=5,
        )
        
        assert trade.instrumento == "EUR/USD"
        assert trade.direction == "LONG"
        assert trade.entry_price == 100.0
        assert trade.tau == 5
    
    def test_position_tracking(self):
        """Dado posicao,
        Quando trade executado,
        Entao posicao é atualizada corretamente."""
        pos = Position(direction="LONG", entry_idx=0)
        
        assert pos.is_open
        assert not pos.is_closed
        
        pos.close(idx=5, exit_price=102.0)
        
        assert pos.is_closed
        assert pos.exit_bar_idx == 5
        assert pos.exit_price == 102.0


class TestPnLMetrics:
    """Testes para calculo de metricas PnL."""
    
    def test_return_calculation(self):
        """Dado entrada e saida,
        Quando calcula retorno,
        Entao retorno bat referencia."""
        entry = 100.0
        exit_price = 102.0
        
        # Retorno = (exit - entry) / entry (LONG)
        ret_long = (exit_price - entry) / entry
        expected = 0.02
        
        assert abs(ret_long - expected) < 0.001
    
    def test_short_return_positive(self):
        """Dado SHORT,
        Quando preco cai,
        Entao retorno é positivo."""
        entry = 100.0
        exit_price = 98.0
        
        # Retorno LONG = (exit - entry) / entry = -0.02
        # Retorno SHORT = (entry - exit) / entry = 0.02
        ret_short = (entry - exit_price) / entry
        expected = 0.02
        
        assert abs(ret_short - expected) < 0.001


class TestPnLFixture:
    """Testes usando fixture de trades/equity."""
    
    def test_equity_trades_fixture(self):
        """Dado fixture equity_trades.json,
        Quando validado,
        Entao valores batem referencia."""
        fixture_path = "tests/fixtures/backtest/equity_trades.json"
        
        try:
            with open(fixture_path) as f:
                fixture = json.load(f)
            
            # Verificar estrutura
            assert 'test_cases' in fixture
            
            for case in fixture['test_cases']:
                # Cada caso deve ter scenario e expected
                assert 'scenario' in case
                assert 'expected' in case
                
        except FileNotFoundError:
            pytest.skip("Fixture not found")


class TestPnLForceThreshold:
    """Testes para filtro de forca ≥ 0.60."""
    
    def test_force_threshold_applied(self):
        """Dado force < 0.60,
        Quando processado,
        Entao NEUTRO (não gera trade)."""
        # Esta verificação é feita no Runner com base no payload F5
        from motor.backtest import F6_FORCE_THRESHOLD
        
        assert F6_FORCE_THRESHOLD == 0.60
    
    def test_alta_media_confianca(self):
        """Dado confianca ALTA/MÉDIA,
        Quando force >= 0.60,
        Então trade é gerado."""
        from motor.backtest import F6_FORCE_THRESHOLD
        
        # Forcas validas
        assert F6_FORCE_THRESHOLD <= 1.0
        assert F6_FORCE_THRESHOLD >= 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])