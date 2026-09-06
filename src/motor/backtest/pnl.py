"""Calculo PnL motor-only para backtest (US3).

Entry mid-close da barra do sinal → Exit validade_ate / tau, sem flip, custo zero.

Spec F6 §10.1 - US3, T015
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
import logging

import numpy as np

logger = logging.getLogger(__name__)


class Direction(str, Enum):
    """Direcao do trade."""
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRO = "NEUTRO"


class TradeStatus(str, Enum):
    """Status do trade."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    TRUNCATED = "TRUNCATED"


@dataclass
class Trade:
    """Representa um trade individual.
    
    Entry: mid (bid+ask)/2 no close da barra do sinal
    Exit: mid-close na barra de validade_ate / meia_vida_barras
    Sem flip: nao inverte posicao por sinal oposto
    """
    instrumento: str
    direction: str  # LONG or SHORT
    entry_bar_index: int
    entry_timestamp: int
    entry_price: float  # mid price no close
    entry_mid: float    # same as entry_price
    tau: Optional[int] = None  # meia_vida_barras
    
    # Exit info
    exit_bar_idx: Optional[int] = None
    exit_timestamp: Optional[int] = None
    exit_price: Optional[float] = None
    exit_mid: Optional[float] = None
    status: TradeStatus = TradeStatus.OPEN
    
    # PnL
    retorno: Optional[float] = None
    flipped: bool = False
    
    def close(self, idx: int, exit_price: float, exit_timestamp: int):
        """Fecha o trade."""
        self.exit_bar_idx = idx
        self.exit_timestamp = exit_timestamp
        self.exit_price = exit_price
        self.exit_mid = exit_price
        
        # Calcula retorno
        if self.direction == "LONG":
            self.retorno = (exit_price - self.entry_price) / self.entry_price
        else:  # SHORT
            self.retorno = (self.entry_price - exit_price) / self.entry_price
        
        self.status = TradeStatus.CLOSED
    
    def force_close(self, idx: int, exit_price: float, exit_timestamp: int):
        """Forca fechamento (ex: fim de serie)."""
        self.close(idx, exit_price, exit_timestamp)
        self.status = TradeStatus.TRUNCATED


@dataclass
class Position:
    """Posicao aberta/fechada.
    
    Mantem estado da posicao para aplicar no-flip.
    """
    direction: str
    entry_idx: int
    tau: Optional[int] = None  # meia_vida_barras
    entry_bar: Optional[List[float]] = None
    exit_bar_idx: Optional[int] = None
    exit_bar: Optional[List[float]] = None
    is_open: bool = True
    is_closed: bool = False
    exit_price: Optional[float] = None
    current_bar_index: int = 0
    
    def update(self, current_idx: int):
        """Atualiza indice atual da posicao."""
        self.current_bar_index = current_idx
    
    def close(self, idx: int, exit_price: float):
        """Fecha a posicao."""
        self.exit_bar_idx = idx
        self.exit_price = exit_price
        self.is_open = False
        self.is_closed = True
    
    def get_exit_bar_index(self) -> int:
        """Retorna o indice da barra de exit calculado."""
        return self.entry_idx + (self.tau or 10)


@dataclass
class PnLResult:
    """Resultado da simulacao de PnL."""
    instrumento: str
    trades: List[Trade] = field(default_factory=list)
    position: Optional[Position] = None
    equity_curve: List[float] = field(default_factory=list)
    daily_equity: List[Dict[str, Any]] = field(default_factory=list)
    total_return: float = 0.0
    num_trades: int = 0
    num_wins: int = 0
    num_losses: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_dd: float = 0.0
    warnings: List[str] = field(default_factory=list)


class PnLCalculator:
    """Calculadora de PnL para backtest motor-only.
    
    Entry: mid (bid+ask)/2 no close da barra do sinal
    Exit: mid-close na barra de validade_ate / meia_vida_barras (tau)
    Sem flip: nenhum sinal oposto inverte posicao existente
    Custo zero: usa mid-price sem spread/comissao adicional
    """
    
    def __init__(self, seed: int = 42):
        """Inicializa o calculador."""
        self.seed = seed
        np.random.seed(seed)
        self.trades: List[Trade] = []
        self.position: Optional[Position] = None
        self.equity = 1.0  # Equity inicial
        self.equity_curve: List[float] = []
        self.daily_equity: Dict[str, float] = {}  # date -> equity
        self.last_date: Optional[str] = None
        self.tau_values: List[int] = []
        self.warnings_list: List[str] = []
    
    def _get_mid_price(self, bar: List[float]) -> float:
        """Calcula mid-price P_t = (Bid_t + Ask_t) / 2."""
        return (bar[5] + bar[6]) / 2.0
    
    def _timestamp_to_date(self, ts: int) -> str:
        """Converte timestamp para data UTC."""
        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    
    def _update_daily_equity(self, ts: int):
        """Atualiza equity diario."""
        date = self._timestamp_to_date(ts)
        if date != self.last_date:
            self.daily_equity[date] = self.equity
            self.last_date = date
    
    def can_open_trade(self, direction: str) -> bool:
        """Verifica se pode abrir trade (nao ha posicao aberta).
        
        Sem flip: se ha posicao aberta, nao abre nova.
        """
        if self.position is None:
            return True
        if self.position.is_open:
            return False  # Nao flip
        return True
    
    def process_signal(
        self,
        bar: List[float],
        bar_index: int,
        direction: str,
        force: float,
        tau: Optional[float],
    ):
        """Processa um sinal de entrada.
        
        Args:
            bar: Barra atual [timestamp, open, high, low, close, bid, ask]
            bar_index: Indice da barra
            direction: LONG, SHORT, ou NEUTRO
            force: Forca do sinal (0-1)
            tau: Meia-vida em barras
        """
        if direction == "NEUTRO":
            return
        
        if not self.can_open_trade(direction):
            return
        
        # Calcula mid-price de entrada
        entry_mid = self._get_mid_price(bar)
        timestamp = int(bar[0])
        
        # Cria trade
        trade = Trade(
            instrumento="",  # Set by caller
            direction=direction,
            entry_bar_index=bar_index,
            entry_timestamp=timestamp,
            entry_price=entry_mid,
            entry_mid=entry_mid,
            tau=int(tau) if tau else 10,
        )
        
        self.trades.append(trade)
        self.position = Position(
            direction=direction,
            entry_idx=bar_index,
            tau=int(tau) if tau else 10,
            entry_bar=bar,
        )
        
        logger.debug(f"Trade abierto: {direction} em barra {bar_index} ({timestamp})")
    
    def check_exit(self, bar: List[float], bar_index: int, tau: Optional[float] = None):
        """Verifica se deve sair da posicao.
        
        Exit: mid-close na barra de validade_ate / tau
        """
        if self.position is None or not self.position.is_open:
            return
        
        # Calcular indice de exit esperado
        tau_val = int(tau) if tau else None
        expected_exit_idx = self.position.entry_idx + (tau_val or self.position.tau or 10)
        
        if bar_index >= expected_exit_idx:
            # Sair nesta barra
            exit_mid = self._get_mid_price(bar)
            timestamp = int(bar[0])
            
            # Fechar trade aberto
            if self.trades:
                trade = self.trades[-1]  # O mais recente
                trade.close(bar_index, exit_mid, timestamp)
                self.tau_values.append(trade.tau or 10)
                
                # Atualizar equity
                if trade.retorno:
                    self.equity *= (1 + trade.retorno)
            
            # Fechar posicao
            self.position.close(bar_index, exit_mid)
            
            self._update_daily_equity(timestamp)
            self.warnings_list.append(f"Trade fechado em barra {bar_index}")
    
    def force_close_all(self, last_bar: List[float], last_index: int):
        """Forca fechamento de todas posicoes abertas no fim da serie."""
        if self.position is None or not self.position.is_open:
            return
        
        exit_mid = self._get_mid_price(last_bar)
        timestamp = int(last_bar[0])
        
        if self.trades:
            trade = self.trades[-1]
            trade.force_close(last_index, exit_mid, timestamp)
            self.tau_values.append(trade.tau or 10)
            
            # Atualizar equity
            if trade.retorno:
                self.equity *= (1 + trade.retorno)
        
        self.position.close(last_index, exit_mid)
        self._update_daily_equity(timestamp)
        self.warnings_list.append(f"Posicao truncada no fim da serie - barra {last_index}")
    
    def get_result(self, instrumento: str) -> PnLResult:
        """Retorna resultado final da simulacao."""
        # Calcular metricas
        num_trades = len(self.trades)
        num_wins = sum(1 for t in self.trades if t.retorno and t.retorno > 0)
        num_losses = num_trades - num_wins
        
        win_rate = num_wins / num_trades if num_trades > 0 else 0.0
        
        gross_wins = sum(t.retorno for t in self.trades if t.retorno and t.retorno > 0)
        gross_losses = abs(sum(t.retorno for t in self.trades if t.retorno and t.retorno < 0))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')
        
        # Max Drawdown - sobre equity curve
        equity_array = np.array(self.equity_curve + [self.equity])
        if len(equity_array) > 0:
            peak = np.maximum.accumulate(equity_array)
            drawdowns = (peak - equity_array) / peak
            max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        else:
            max_dd = 0.0
        
        # Total return
        total_return = self.equity - 1.0
        
        # Tau median
        tau_median = int(np.median(self.tau_values)) if self.tau_values else 0
        
        return PnLResult(
            instrumento=instrumento,
            trades=self.trades,
            position=self.position,
            equity_curve=self.equity_curve,
            daily_equity=[
                {"date": date, "equity": equity}
                for date, equity in sorted(self.daily_equity.items())
            ],
            total_return=total_return,
            num_trades=num_trades,
            num_wins=num_wins,
            num_losses=num_losses,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_dd=max_dd,
            warnings=self.warnings_list,
        )


def calculate_pnl(
    entry_price: float,
    exit_price: float,
    direction: str = "LONG",
) -> float:
    """Calcula retorno de um trade.
    
    Args:
        entry_price: Preco de entrada (mid)
        exit_price: Preco de saida (mid)
        direction: LONG ou SHORT
        
    Returns:
        Retorno como fracao (ex: 0.02 = 2%)
    """
    if direction == "LONG":
        return (exit_price - entry_price) / entry_price
    else:  # SHORT
        return (entry_price - exit_price) / entry_price


def run_pnl_simulation(
    bars: List[List[float]],
    instrumento: str,
    seed: int = 42,
) -> PnLResult:
    """Executa simulacao PnL completa.
    
    Args:
        bars: Serie de barras OHLC
        instrumento: Símbolo do instrumento
        seed: Seed para reprodutibilidade
        
    Returns:
        PnLResult com trades e metricas
    """
    calculator = PnLCalculator(seed=seed)
    
    # Processar cada barra
    for i, bar in enumerate(bars):
        # Atualizar equity curve
        calculator.equity_curve.append(calculator.equity)
        
        # Verificar exit
        calculator.check_exit(bar, i)
        
        # Atualizar daily equity
        ts = int(bar[0])
        calculator._update_daily_equity(ts)
    
    # Forcar fechamento de posicoes abertas
    if len(bars) > 0:
        calculator.force_close_all(bars[-1], len(bars) - 1)
    
    return calculator.get_result(instrumento)


# Funcao utilitaria para adicionar trade a partir de payload
def add_trade_from_payload(
    calculator: PnLCalculator,
    bar: List[float],
    bar_index: int,
    payload: Any,  # PayloadMotor
) -> bool:
    """Adiciona trade a partir de payload F5.
    
    Args:
        calculator: PnLCalculator
        bar: Barra atual
        bar_index: Indice da barra
        payload: PayloadMotor com sinal_quantitativo
        
    Returns:
        True se trade foi adicionado, False caso contrario
    """
    if payload is None:
        return False
    
    sq = payload.sinal_quantitativo
    direction = sq.direcao
    
    # F6 trigger: ALTA ou MÉDIA (force >= 0.60)
    # NEUTRO ou forca < 0.60 nao gera trade
    if direction == "NEUTRO":
        return False
    
    if sq.forca < 0.60:
        return False
    
    tau = sq.meia_vida_barras
    calculator.process_signal(bar, bar_index, direction, sq.forca, tau)
    
    return True