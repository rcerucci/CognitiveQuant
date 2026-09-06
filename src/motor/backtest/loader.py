"""Loader para dados históricos CSV/parquet do backtest motor-only (US2).

Consuming CSV/parquet files from data/ohlc/ directory.
No provider SDK (Polygon/OANDA/QC/Broker) - adapter external to runner.

Spec F6 §10.1 - US2, T010
"""

from __future__ import annotations

import os
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Union

import pandas as pd
import numpy as np

# Import constants from package
from motor.backtest import F6_INSTRUMENTS


class LoaderStatus(str, Enum):
    """Status do loader."""
    SUCCESS = "SUCCESS"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    INVALID_FORMAT = "INVALID_FORMAT"
    NO_DATA = "NO_DATA"
    INSTRUMENT_NOT_IN_UNIVERSE = "INSTRUMENT_NOT_IN_UNIVERSE"


@dataclass
class InstrumentBars:
    """Barras de um instrumento carregado."""
    instrumento: str
    timeframe: str = "M30"
    bars: List[List[float]] = field(default_factory=list)
    status: LoaderStatus = LoaderStatus.SUCCESS
    message: Optional[str] = None


@dataclass
class LoaderResult:
    """Resultado do loader para múltiplos instrumentos."""
    instruments: List[InstrumentBars] = field(default_factory=list)
    status: LoaderStatus = LoaderStatus.SUCCESS
    loaded_count: int = 0
    rejected_count: int = 0
    rejections: List[str] = field(default_factory=list)
    message: Optional[str] = None


class BacktestLoader:
    """Loader para dados históricos CSV/parquet do backtest motor-only.
    
    Carrega dados no formato F1: [timestamp, open, high, low, close, bid, ask]
    Apenas carrega de arquivos já materializados em data/ohlc/
    """
    
    # M30 interval in milliseconds
    M30_MS = 1800000
    
    def __init__(self, data_dir: str = "data/ohlc", seed: int = 42):
        """Inicializa o loader.
        
        Args:
            data_dir: Diretório base para dados (padrão: data/ohlc)
            seed: Seed para reprodutibilidade
        """
        self.data_dir = data_dir
        self.seed = seed
        np.random.seed(seed)
        
    def _get_instrument_filepath(self, instrumento: str) -> str:
        """Obtém o caminho do arquivo para um instrumento.
        
        Args:
            instrumento: Símbolo do instrumento
            
        Returns:
            Caminho para o arquivo CSV ou parquet
        """
        # Map instrument names to file names
        # EUR/USD -> eur_usd.csv, US500 -> us500.csv, etc.
        file_name = instrumento.replace("/", "_").lower()
        
        # Try parquet first, then CSV
        parquet_path = os.path.join(self.data_dir, f"{file_name}.parquet")
        csv_path = os.path.join(self.data_dir, f"{file_name}.csv")
        
        if os.path.exists(parquet_path):
            return parquet_path
        elif os.path.exists(csv_path):
            return csv_path
        else:
            return ""
    
    def _load_csv(self, filepath: str) -> pd.DataFrame:
        """Carrega dados de CSV."""
        df = pd.read_csv(filepath)
        
        # Normalize column names
        column_mapping = {
            'timestamp': 'timestamp',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'bid': 'bid',
            'ask': 'ask',
            'time': 'timestamp',  # Some CSVs use 'time' instead of 'timestamp'
        }
        
        # Rename columns if needed
        df.columns = [column_mapping.get(col, col) for col in df.columns]
        
        # Ensure correct column order
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'bid', 'ask']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Missing required columns in CSV: {filepath}")
        
        return df[required_cols]
    
    def _load_parquet(self, filepath: str) -> pd.DataFrame:
        """Carrega dados de Parquet."""
        df = pd.read_parquet(filepath)
        
        # Ensure correct column order
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'bid', 'ask']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Missing required columns in parquet: {filepath}")
        
        return df[required_cols]
    
    def _validate_bar(self, row: pd.Series, bar_idx: int) -> Optional[str]:
        """Valida uma única barra.
        
        Args:
            row: Série do DataFrame
            bar_idx: Índice da barra (para logging)
            
        Returns:
            Mensagem de erro se inválido, None se válido
        """
        # Check for NaNs
        if pd.isna(row['open']) or pd.isna(row['high']) or pd.isna(row['low']) or pd.isna(row['close']):
            return f"NaN price at bar {bar_idx}"
        
        if pd.isna(row['bid']) or pd.isna(row['ask']):
            return f"NaN bid/ask at bar {bar_idx}"
        
        # Check finite values
        for col in ['open', 'high', 'low', 'close', 'bid', 'ask']:
            if not math.isfinite(row[col]):
                return f"Non-finite {col} at bar {bar_idx}"
        
        # Check price integrity
        if row['high'] < max(row['open'], row['close']):
            return f"Price integrity violation: high < open/close at bar {bar_idx}"
        
        if row['low'] > min(row['open'], row['close']):
            return f"Price integrity violation: low > open/close at bar {bar_idx}"
        
        if row['bid'] <= 0 or row['ask'] <= 0:
            return f"Invalid bid/ask at bar {bar_idx}"
        
        return None
    
    def load_instrument(self, instrumento: str) -> InstrumentBars:
        """Carrega dados de um instrumento específico.
        
        Args:
            instrumento: Símbolo do instrumento (ex: "EUR/USD")
            
        Returns:
            InstrumentBars com dados carregados
        """
        # Check if instrument is in the universe
        if instrumento not in F6_INSTRUMENTS:
            return InstrumentBars(
                instrumento=instrumento,
                status=LoaderStatus.INSTRUMENT_NOT_IN_UNIVERSE,
                message=f"Instrument {instrumento} not in F6 universe §9.2",
                bars=[],
            )
        
        # Get file path
        filepath = self._get_instrument_filepath(instrumento)
        
        if not filepath or not os.path.exists(filepath):
            return InstrumentBars(
                instrumento=instrumento,
                status=LoaderStatus.FILE_NOT_FOUND,
                message=f"File not found for {instrumento}: {filepath}",
                bars=[],
            )
        
        try:
            # Load data based on file extension
            if filepath.endswith('.parquet'):
                df = self._load_parquet(filepath)
            else:
                df = self._load_csv(filepath)
        except Exception as e:
            return InstrumentBars(
                instrumento=instrumento,
                status=LoaderStatus.INVALID_FORMAT,
                message=f"Error loading {filepath}: {str(e)}",
                bars=[],
            )
        
        # Check for empty data
        if len(df) == 0:
            return InstrumentBars(
                instrumento=instrumento,
                status=LoaderStatus.NO_DATA,
                message=f"No data in file: {filepath}",
                bars=[],
            )
        
        # Validate bars
        bars = []
        for idx, row in df.iterrows():
            error = self._validate_bar(row, idx)
            if error:
                # Log error but continue (don't abort like F1)
                continue
            
            bars.append([
                float(row['timestamp']),
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['bid']),
                float(row['ask']),
            ])
        
        return InstrumentBars(
            instrumento=instrumento,
            bars=bars,
            status=LoaderStatus.SUCCESS,
            message=f"Loaded {len(bars)} bars from {filepath}",
        )
    
    def load_universe(self) -> LoaderResult:
        """Carrega dados de todos os instrumentos do universo F6 §9.2.
        
        Returns:
            LoaderResult com todos os instrumentos carregados
        """
        loaded = []
        rejected = []
        
        for instrumento in F6_INSTRUMENTS:
            result = self.load_instrument(instrumento)
            
            if result.status == LoaderStatus.SUCCESS and len(result.bars) > 0:
                loaded.append(result)
            else:
                rejected.append(result)
        
        return LoaderResult(
            instruments=loaded,
            status=LoaderStatus.SUCCESS if loaded else LoaderStatus.NO_DATA,
            loaded_count=len(loaded),
            rejected_count=len(rejected),
            rejections=[r.message for r in rejected if r.message],
        )
    
    def load_from_fixture(self, fixture_path: str) -> LoaderResult:
        """Carrega dados de um arquivo fixture (para testes).
        
        Args:
            fixture_path: Caminho para o arquivo fixture
            
        Returns:
            LoaderResult com dados carregados
        """
        if not os.path.exists(fixture_path):
            return LoaderResult(
                status=LoaderStatus.FILE_NOT_FOUND,
                message=f"Fixture not found: {fixture_path}",
            )
        
        try:
            if fixture_path.endswith('.parquet'):
                df = self._load_parquet(fixture_path)
            else:
                df = self._load_csv(fixture_path)
        except Exception as e:
            return LoaderResult(
                status=LoaderStatus.INVALID_FORMAT,
                message=f"Error loading fixture: {str(e)}",
            )
        
        # Process as single instrument for fixtures
        instrument_name = os.path.basename(fixture_path).split('.')[0]
        
        bars = []
        for idx, row in df.iterrows():
            error = self._validate_bar(row, idx)
            if error:
                continue
            
            bars.append([
                float(row['timestamp']),
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['bid']),
                float(row['ask']),
            ])
        
        instrument = InstrumentBars(
            instrumento=instrument_name,
            bars=bars,
            status=LoaderStatus.SUCCESS,
        )
        
        return LoaderResult(
            instruments=[instrument],
            status=LoaderStatus.SUCCESS,
            loaded_count=1,
            rejected_count=0,
        )


def load_historical_data(
    data_dir: str = "data/ohlc",
    seed: int = 42,
    instruments: Optional[List[str]] = None,
) -> LoaderResult:
    """Função de conveniência para carregar dados históricos.
    
    Args:
        data_dir: Diretório base para dados
        seed: Seed para reprodutibilidade
        instruments: Lista opcional de instrumentos (padrão: universo F6)
        
    Returns:
        LoaderResult com dados carregados
    """
    loader = BacktestLoader(data_dir=data_dir, seed=seed)
    
    if instruments:
        loaded = []
        rejected = []
        for inst in instruments:
            result = loader.load_instrument(inst)
            if result.status == LoaderStatus.SUCCESS and len(result.bars) > 0:
                loaded.append(result)
            else:
                rejected.append(result)
        
        return LoaderResult(
            instruments=loaded,
            status=LoaderStatus.SUCCESS if loaded else LoaderStatus.NO_DATA,
            loaded_count=len(loaded),
            rejected_count=len(rejected),
            rejections=[r.message for r in rejected if r.message],
        )
    else:
        return loader.load_universe()


# Convenience function for tests
def load_fixture_data(fixture_path: str) -> LoaderResult:
    """Load data from a test fixture file."""
    loader = BacktestLoader()
    return loader.load_from_fixture(fixture_path)